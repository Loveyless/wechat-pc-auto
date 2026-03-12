use crate::adapter::ax_reader::{self, ChatMessage};
use crate::adapter::MacOSAdapter;
use crate::app_state;
use crate::config::AppConfig;
use crate::db::MessageDb;
use crate::events::{EventStore, EventType};
use crate::image_cache::{self, WeChatImageCache};
use crate::translator::{
    TranslateConfig, TranslateProviderConfig, TranslationLimiter, TranslationService,
    TranslatorServiceStatus,
};
use anyhow::Result;
use log::debug;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Manager};
use tokio::sync::{watch, Mutex};
use tokio_util::sync::CancellationToken;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskState {
    pub monitoring: bool,
    pub sidebar: bool,
}


struct SidebarConfig {
    translator: Option<Arc<dyn crate::translator::Translator>>,
    limiter: Option<Arc<TranslationLimiter>>,
    target_set: HashSet<String>,
    image_capture: bool,
}

/// 悬浮窗运行态：统一维护当前聊天和刷新版本号
/// 解决"标题切换但内容空"问题的核心状态
pub struct SidebarRuntime {
    /// 后端确认的当前聊天名称
    current_chat: std::sync::Mutex<String>,
    /// 刷新版本号，每次消息入库或译文写回后递增
    refresh_version: AtomicU64,
}

impl SidebarRuntime {
    fn new() -> Self {
        Self {
            current_chat: std::sync::Mutex::new(String::new()),
            refresh_version: AtomicU64::new(0),
        }
    }
}

/// 监听循环首次 poll 完成信号
/// 用于 live_start 等待监听就绪后再打开窗口
pub struct FirstPollSignal {
    tx: watch::Sender<Option<String>>,
    rx: watch::Receiver<Option<String>>,
}

impl FirstPollSignal {
    fn new() -> Self {
        let (tx, rx) = watch::channel(None);
        Self { tx, rx }
    }

    /// 监听循环调用：标记首次 poll 完成，并传递当前聊天名称
    fn signal_ready(&self, chat_name: &str) {
        let _ = self.tx.send(Some(chat_name.to_string()));
    }

    /// 重置信号（监听重启时调用）
    fn reset(&self) {
        let _ = self.tx.send(None);
    }

    /// 等待首次 poll 完成，返回当前聊天名称
    /// 带超时保护，避免无限等待
    pub async fn wait_ready(&self, timeout: Duration) -> Option<String> {
        let mut rx = self.rx.clone();
        tokio::select! {
            result = async {
                loop {
                    if let Some(chat_name) = rx.borrow().clone() {
                        return Some(chat_name);
                    }
                    if rx.changed().await.is_err() {
                        return None;
                    }
                }
            } => result,
            _ = tokio::time::sleep(timeout) => None,
        }
    }
}

impl SidebarRuntime {
    pub fn get_current_chat(&self) -> String {
        self.current_chat.lock().unwrap().clone()
    }

    pub fn set_current_chat(&self, chat_name: &str) {
        *self.current_chat.lock().unwrap() = chat_name.to_string();
    }

    pub fn get_refresh_version(&self) -> u64 {
        self.refresh_version.load(Ordering::Relaxed)
    }

    /// 递增刷新版本号并返回新值
    pub fn increment_refresh_version(&self) -> u64 {
        self.refresh_version.fetch_add(1, Ordering::Relaxed) + 1
    }

    /// 更新当前聊天并递增刷新版本号
    pub fn update_chat_and_version(&self, chat_name: &str) -> u64 {
        self.set_current_chat(chat_name);
        self.increment_refresh_version()
    }

    pub fn clear(&self) {
        *self.current_chat.lock().unwrap() = String::new();
        self.refresh_version.store(0, Ordering::Relaxed);
    }
}

#[derive(Debug, Clone, Copy)]
struct MonitorConfig {
    use_right_panel_details: bool,
}


#[derive(Clone)]
pub struct TaskManager {
    adapter: Arc<MacOSAdapter>,
    events: Arc<EventStore>,
    db: Arc<MessageDb>,
    image_cache: Arc<std::sync::Mutex<WeChatImageCache>>,
    translation_service: Arc<TranslationService>,
    monitor_token: Arc<Mutex<Option<CancellationToken>>>,
    monitoring_active: Arc<AtomicBool>,
    monitor_config: Arc<Mutex<MonitorConfig>>,
    first_poll_signal: Arc<FirstPollSignal>,
    sidebar_enabled: Arc<AtomicBool>,
    sidebar_config: Arc<Mutex<SidebarConfig>>,
    sidebar_runtime: Arc<SidebarRuntime>,
    translator_generation: Arc<AtomicU64>,
    app_handle: Arc<Mutex<Option<AppHandle>>>,
}

impl TaskManager {
    pub fn new(
        adapter: Arc<MacOSAdapter>,
        events: Arc<EventStore>,
        db: Arc<MessageDb>,
        image_cache: Arc<std::sync::Mutex<WeChatImageCache>>,
        translation_service: Arc<TranslationService>,
    ) -> Self {
        Self {
            adapter,
            events,
            db,
            image_cache,
            translation_service,
            monitor_token: Arc::new(Mutex::new(None)),
            monitoring_active: Arc::new(AtomicBool::new(false)),
            monitor_config: Arc::new(Mutex::new(MonitorConfig {
                use_right_panel_details: false,
            })),
            first_poll_signal: Arc::new(FirstPollSignal::new()),
            sidebar_enabled: Arc::new(AtomicBool::new(false)),
            sidebar_config: Arc::new(Mutex::new(SidebarConfig {
                translator: None,
                limiter: None,
                target_set: HashSet::new(),
                image_capture: false,
            })),
            sidebar_runtime: Arc::new(SidebarRuntime::new()),
            translator_generation: Arc::new(AtomicU64::new(0)),
            app_handle: Arc::new(Mutex::new(None)),
        }
    }

    pub async fn set_app_handle(&self, handle: AppHandle) {
        *self.app_handle.lock().await = Some(handle);
    }

    pub async fn set_use_right_panel_details(&self, enabled: bool) {
        self.monitor_config.lock().await.use_right_panel_details = enabled;
    }

    async fn get_app_handle(&self) -> Result<AppHandle> {
        self.app_handle
            .lock()
            .await
            .clone()
            .ok_or_else(|| anyhow::anyhow!("AppHandle not set"))
    }

    pub fn get_task_state(&self) -> TaskState {
        TaskState {
            monitoring: self.monitoring_active.load(Ordering::Relaxed),
            sidebar: self.sidebar_enabled.load(Ordering::Relaxed),
        }
    }

    pub async fn get_translator_status(&self) -> TranslatorServiceStatus {
        self.translation_service.get_status().await
    }

    pub fn get_sidebar_runtime(&self) -> &Arc<SidebarRuntime> {
        &self.sidebar_runtime
    }

    /// 等待监听循环首次 poll 完成
    /// 返回当前聊天名称，超时返回 None
    pub async fn wait_first_poll(&self, timeout: Duration) -> Option<String> {
        self.first_poll_signal.wait_ready(timeout).await
    }

    /// 获取翻译服务是否可用
    pub async fn is_translator_available(&self) -> bool {
        self.translation_service.is_available().await
    }

    /// 获取翻译服务
    pub fn get_translation_service(&self) -> Arc<TranslationService> {
        self.translation_service.clone()
    }

    /// 手动翻译消息（用于点击翻译按钮）
    pub async fn translate_message_manually(
        &self,
        app: tauri::AppHandle,
        message_id: u64,
        chat_name: String,
        sender: String,
        content: String,
        detected_at: String,
    ) -> Result<(), String> {
        log::info!("[TaskManager] translate_message_manually 开始");
        let config = self.translation_service.get_config().await;
        log::info!("[TaskManager] 翻译配置: enabled={}", config.enabled);
        if !config.enabled {
            return Err("翻译服务未启用".to_string());
        }

        let (translator, limiter) = self.translation_service.get_translator_and_limiter().await;
        log::info!("[TaskManager] translator={}, limiter={}", translator.is_some(), limiter.is_some());
        let translator = translator.ok_or_else(|| "翻译服务未配置".to_string())?;
        let limiter = limiter.ok_or_else(|| "翻译限流器未配置".to_string())?;

        let source_lang = config.source_lang.clone();
        let target_lang = config.target_lang.clone();

        log::info!("[TaskManager] 准备启动翻译任务: {}→{}", source_lang, target_lang);
        // 复用已有的翻译更新逻辑
        spawn_sidebar_translation_update(
            self.clone(),
            self.events.clone(),
            app,
            self.db.clone(),
            translator,
            limiter,
            source_lang,
            target_lang,
            message_id,
            chat_name,
            sender,
            content,
            detected_at,
        );

        log::info!("[TaskManager] translate_message_manually 完成");
        Ok(())
    }

    pub async fn service_status(&self) -> serde_json::Value {
        let state = self.get_task_state();
        let translator_status = self.get_translator_status().await;
        serde_json::json!({
            "adapter": {
                "platform": self.adapter.is_supported().then_some("macos").unwrap_or("unsupported"),
                "supported": self.adapter.is_supported(),
                "reason": self.adapter.support_reason(),
            },
            "tasks": state,
            "translator": translator_status.as_json(),
        })
    }

    async fn publish_task_state_event(
        &self,
        task: &str,
        running: bool,
        state: &TaskState,
        translator_status: &TranslatorServiceStatus,
    ) {
        if let Ok(app) = self.get_app_handle().await {
            self.events.publish(
                &app,
                EventType::TaskState,
                "task_manager",
                serde_json::json!({
                    "task": task,
                    "running": running,
                    "state": state,
                    "translator": translator_status.as_json(),
                }),
            );
        }
    }

    fn next_translator_generation(&self) -> u64 {
        self.translator_generation.fetch_add(1, Ordering::Relaxed) + 1
    }

    fn spawn_translator_health_check(&self, translator_generation: u64) {
        let manager = self.clone();
        tokio::spawn(async move {
            let config = manager.translation_service.get_config().await;
            let provider = config.provider_name().to_string();
            let next_status = match manager.translation_service.check_health().await {
                Ok(_) => TranslatorServiceStatus::healthy(&provider),
                Err(error) => TranslatorServiceStatus::error(&provider, error.to_string()),
            };
            manager
                .set_translator_status_if_current(translator_generation, next_status)
                .await;
        });
    }

    pub async fn apply_runtime_config(&self, config: &AppConfig) {
        self.set_use_right_panel_details(config.listen.use_right_panel_details)
            .await;

        let translator_generation = self.next_translator_generation();

        // 根据 provider 类型构建对应的配置
        let provider_config = if config.translate.provider == "ai" {
            TranslateProviderConfig::Ai {
                provider_id: config.translate.ai_provider_id.clone(),
                model_id: config.translate.ai_model_id.clone(),
                api_key: config.translate.ai_api_key.clone(),
                base_url: if config.translate.ai_base_url.is_empty() {
                    None
                } else {
                    Some(config.translate.ai_base_url.clone())
                },
            }
        } else {
            TranslateProviderConfig::Deeplx {
                url: config.translate.deeplx_url.clone(),
            }
        };

        // 更新全局翻译服务配置
        let translate_config = TranslateConfig {
            enabled: config.translate.enabled,
            provider_config,
            source_lang: config.translate.source_lang.clone(),
            target_lang: config.translate.target_lang.clone(),
            timeout_seconds: config.translate.timeout_seconds,
            max_concurrency: config.translate.max_concurrency,
            max_requests_per_second: config.translate.max_requests_per_second,
        };

        let translator_status = self.translation_service.update_config(translate_config).await;

        // 更新侧边栏配置（使用全局翻译服务的 translator 和 limiter）
        if self.sidebar_enabled.load(Ordering::Relaxed) {
            let (translator, limiter) = self.translation_service.get_translator_and_limiter().await;
            let mut sidebar_config = self.sidebar_config.lock().await;
            sidebar_config.translator = translator;
            sidebar_config.limiter = limiter;
        }

        if let Ok(app) = self.get_app_handle().await {
            let state = self.get_task_state();
            update_tray_menu(&app, &state, &translator_status);
            app_state::emit_runtime_updated(&app, self);
        }

        // 如果翻译服务已配置，启动健康检查
        if translator_status.configured {
            self.spawn_translator_health_check(translator_generation);
        }
    }

    async fn set_translator_status_if_current(
        &self,
        generation: u64,
        status: TranslatorServiceStatus,
    ) {
        if self.translator_generation.load(Ordering::Relaxed) != generation {
            return;
        }

        self.translation_service.set_status(status.clone()).await;

        if self.translator_generation.load(Ordering::Relaxed) != generation {
            return;
        }

        let task_state = self.get_task_state();
        self.publish_task_state_event("translator", status.enabled, &task_state, &status)
            .await;

        if let Ok(app) = self.get_app_handle().await {
            if self.translator_generation.load(Ordering::Relaxed) != generation {
                return;
            }
            update_tray_menu(&app, &task_state, &status);
            app_state::emit_runtime_updated(&app, self);
        }
    }

    pub async fn start_monitoring(&self, interval_seconds: f64) -> Result<()> {
        {
            let existing = self.monitor_token.lock().await;
            if existing.is_some() {
                anyhow::bail!("监听已在运行中");
            }
        }

        let token = CancellationToken::new();
        *self.monitor_token.lock().await = Some(token.clone());
        self.monitoring_active.store(true, Ordering::Relaxed);
        self.first_poll_signal.reset();

        let app = self.get_app_handle().await?;
        let state = self.get_task_state();
        let translator_status = self.get_translator_status().await;
        self.publish_task_state_event("monitoring", true, &state, &translator_status)
            .await;
        update_tray_menu(&app, &state, &translator_status);
        app_state::emit_runtime_updated(&app, self);

        let adapter = self.adapter.clone();
        let events = self.events.clone();
        let db = self.db.clone();
        let image_cache = self.image_cache.clone();
        let monitor_token_ref = self.monitor_token.clone();
        let monitoring_active = self.monitoring_active.clone();
        let monitor_config = self.monitor_config.clone();
        let first_poll_signal = self.first_poll_signal.clone();
        let sidebar_enabled = self.sidebar_enabled.clone();
        let sidebar_config = self.sidebar_config.clone();
        let sidebar_runtime = self.sidebar_runtime.clone();
        let app_handle = app.clone();
        let manager = self.clone();
        let poll_interval = interval_seconds.max(0.4);

        tokio::spawn(async move {
            let mut session_state: HashMap<String, SessionListenState> = HashMap::new();
            let mut chat_baselines: HashMap<String, Vec<ChatMessage>> = HashMap::new();
            let mut chat_kinds: HashMap<String, ChatKind> = HashMap::new();
            let mut preview_sender_hints: HashMap<String, PreviewSenderHint> = HashMap::new();
            let mut active_chat_name = String::new();
            let mut pending_chat_name: Option<String> = None;
            let mut pending_count: u32 = 0;
            let mut last_use_right_panel_details: Option<bool> = None;
            let mut first_poll_signaled = false;
            const DEBOUNCE_THRESHOLD: u32 = 2;
            const SESSION_CORRECTION_WINDOW_SECONDS: i64 = 15;

            loop {
                if token.is_cancelled() {
                    break;
                }

                if adapter.is_ui_paused() {
                    tokio::select! {
                        _ = token.cancelled() => break,
                        _ = tokio::time::sleep(std::time::Duration::from_millis(200)) => {}
                    }
                    continue;
                }

                let use_right_panel_details = monitor_config.lock().await.use_right_panel_details;
                if last_use_right_panel_details != Some(use_right_panel_details) {
                    chat_baselines.clear();
                    last_use_right_panel_details = Some(use_right_panel_details);
                }

                let poll_result = tokio::task::spawn_blocking({
                    let adapter = adapter.clone();
                    move || -> Result<(
                        String,
                        Vec<ax_reader::SessionItemSnapshot>,
                        Vec<ChatMessage>,
                        Option<u32>,
                    )> {
                        if adapter.is_ui_paused() || adapter.has_popup_or_menu() {
                            anyhow::bail!("ui paused or popup detected, skip");
                        }
                        let chat_name = adapter.read_active_chat_name()?;
                        let snapshots = adapter.read_session_snapshots()?;
                        let member_count = adapter.read_active_chat_member_count().unwrap_or(None);
                        let messages = if use_right_panel_details {
                            adapter.read_chat_messages_rich().unwrap_or_default()
                        } else {
                            Vec::new()
                        };
                        Ok((chat_name, snapshots, messages, member_count))
                    }
                })
                .await;

                if let Ok(Ok((chat_name, snapshots, mut messages, member_count))) = poll_result {
                    // 首次成功读取微信状态后发出信号
                    if !first_poll_signaled {
                        first_poll_signal.signal_ready(&chat_name);
                        first_poll_signaled = true;
                    }

                    let now_instant = Instant::now();
                    cleanup_preview_sender_hints(&mut preview_sender_hints, now_instant);
                    let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
                    let prev_unread_counts: HashMap<String, u32> = session_state
                        .iter()
                        .map(|(name, state)| (name.clone(), state.last_unread))
                        .collect();
                    let snapshot_map: HashMap<String, ax_reader::SessionItemSnapshot> = snapshots
                        .iter()
                        .cloned()
                        .map(|item| (item.chat_name.clone(), item))
                        .collect();

                    for snapshot in &snapshots {
                        let state = session_state.entry(snapshot.chat_name.clone()).or_default();
                        if should_emit_session_snapshot(snapshot, state) {
                            let mut chat_kind = chat_kinds
                                .get(&snapshot.chat_name)
                                .copied()
                                .unwrap_or(ChatKind::Unknown);

                            // Use member_count for the active chat (highest priority signal)
                            if snapshot.chat_name == chat_name && member_count.is_some() {
                                chat_kind = ChatKind::Group;
                            } else if snapshot.is_group {
                                chat_kind = ChatKind::Group;
                            } else if chat_kind == ChatKind::Unknown {
                                chat_kind = ChatKind::Private;
                            }
                            chat_kinds.insert(snapshot.chat_name.clone(), chat_kind);
                            remember_preview_sender_hint(
                                &mut preview_sender_hints,
                                snapshot,
                                now_instant,
                            );

                            let mut sender = snapshot.sender_hint.clone().unwrap_or_default();
                            let prev_unread = prev_unread_counts
                                .get(&snapshot.chat_name)
                                .copied()
                                .unwrap_or(0);
                            let unread_increased = snapshot.unread_count > prev_unread;
                            let is_self = if snapshot.has_sender_prefix {
                                false // group chat with sender prefix → other person
                            } else if unread_increased {
                                false // unread count grew → must be from other person
                            } else if matches!(chat_kind, ChatKind::Group) {
                                sender.clear();
                                true // group, no prefix, unread didn't grow → self
                            } else {
                                // private chat, no prefix, unread didn't grow → likely self
                                true
                            };
                            if !is_self && sender.is_empty() {
                                sender = snapshot.chat_name.clone();
                            }

                            events.publish(
                                &app_handle,
                                EventType::Message,
                                "monitor",
                                serde_json::json!({
                                    "chat_name": snapshot.chat_name,
                                    "chat_type": chat_kind.as_str(),
                                    "self_source": if snapshot.has_sender_prefix { "prefix" } else if unread_increased { "unread" } else if matches!(chat_kind, ChatKind::Group) { "group_no_prefix" } else { "unread_stable" },
                                    "source": "session_preview",
                                    "quality": "low",
                                    "sender": sender,
                                    "text": snapshot.preview_body,
                                    "is_self": is_self,
                                }),
                            );

                            if should_forward_session_preview(
                                use_right_panel_details,
                                &snapshot.chat_name,
                                &chat_name,
                            ) {
                                let _ = db.insert_message_with_meta(
                                    &snapshot.chat_name,
                                    Some(chat_kind.as_str()),
                                    &sender,
                                    &snapshot.preview_body,
                                    "",
                                    is_self,
                                    &now,
                                    None,
                                    "session_preview",
                                    "low",
                                );

                                // 会话预览消息入库后：
                                // - 只有当消息属于当前聊天时才刷新悬浮窗
                                // - 避免其他聊天的新消息导致悬浮窗切换
                                if sidebar_enabled.load(Ordering::Relaxed)
                                    && should_forward_sidebar_chat(&snapshot.chat_name)
                                    && snapshot.chat_name == chat_name
                                {
                                    let refresh_version =
                                        sidebar_runtime.update_chat_and_version(&snapshot.chat_name);
                                    events.publish(
                                        &app_handle,
                                        EventType::Status,
                                        "sidebar",
                                        serde_json::json!({
                                            "type": "sidebar-refresh",
                                            "chat_name": snapshot.chat_name,
                                            "refresh_version": refresh_version,
                                        }),
                                    );

                                    // 触发翻译任务
                                    let (translator, limiter) = {
                                        let config = sidebar_config.lock().await;
                                        (config.translator.clone(), config.limiter.clone())
                                    };
                                    let translate_config = manager.translation_service.get_config().await;
                                    if let (Some(translator), Some(limiter)) =
                                        (translator, limiter)
                                    {
                                        spawn_sidebar_translation_update(
                                            manager.clone(),
                                            events.clone(),
                                            app_handle.clone(),
                                            db.clone(),
                                            translator,
                                            limiter,
                                            translate_config.source_lang.clone(),
                                            translate_config.target_lang.clone(),
                                            0, // 会话预览消息没有事件ID
                                            snapshot.chat_name.clone(),
                                            sender.clone(),
                                            snapshot.preview_body.clone(),
                                            now.clone(),
                                        );
                                    }
                                }
                            }
                        }

                        if !snapshot.preview_body.is_empty() {
                            state.last_preview_body = snapshot.preview_body.clone();
                        }
                        state.last_unread = snapshot.unread_count;
                    }

                    if chat_name != active_chat_name {
                        match &pending_chat_name {
                            Some(pending) if *pending == chat_name => {
                                pending_count += 1;
                                if pending_count >= DEBOUNCE_THRESHOLD {
                                    active_chat_name = chat_name.clone();
                                    pending_chat_name = None;
                                    pending_count = 0;
                                    events.publish(
                                        &app_handle,
                                        EventType::Status,
                                        "monitor",
                                        serde_json::json!({
                                            "type": "chat_switched",
                                            "chat_name": chat_name,
                                        }),
                                    );

                                    // 切换聊天时也需要刷新悬浮窗内容（拉取新聊天历史）
                                    if sidebar_enabled.load(Ordering::Relaxed)
                                        && should_forward_sidebar_chat(&chat_name)
                                    {
                                        let refresh_version =
                                            sidebar_runtime.update_chat_and_version(&chat_name);
                                        events.publish(
                                            &app_handle,
                                            EventType::Status,
                                            "sidebar",
                                            serde_json::json!({
                                                "type": "sidebar-refresh",
                                                "chat_name": chat_name,
                                                "refresh_version": refresh_version,
                                            }),
                                        );
                                    }
                                }
                            }
                            _ => {
                                pending_chat_name = Some(chat_name.clone());
                                pending_count = 1;
                            }
                        }
                    } else {
                        pending_chat_name = None;
                        pending_count = 0;
                    }

                    if use_right_panel_details && !messages.is_empty() {
                        let mut chat_kind = chat_kinds
                            .get(&chat_name)
                            .copied()
                            .unwrap_or(ChatKind::Unknown);

                        // Highest priority: member_count from current_chat_count_label
                        // Group chats have this element, private chats don't
                        if member_count.is_some() {
                            chat_kind = ChatKind::Group;
                        }

                        if let Some(baseline) = chat_baselines.get(&chat_name) {
                            inherit_sender_from_reference(&mut messages, baseline);
                        }

                        if let Some(snapshot) = snapshot_map.get(&chat_name) {
                            let prev_unread =
                                prev_unread_counts.get(&chat_name).copied().unwrap_or(0);
                            let unread_increased = snapshot.unread_count > prev_unread;
                            apply_session_preview_sender_hint(
                                &mut messages,
                                &snapshot.raw_preview,
                                &mut chat_kind,
                                unread_increased,
                            );
                        } else if chat_kind == ChatKind::Unknown {
                            chat_kind = ChatKind::Private;
                        }
                        apply_sender_defaults(&mut messages, &chat_name, chat_kind);
                        chat_kinds.insert(chat_name.clone(), chat_kind);
                        let mut chat_type_label = chat_kind.as_str().to_string();

                        if let Some(last) = messages.last() {
                            debug!(
                                "infer_state chat='{}' kind={} total={} latest='{}' is_self={} sender='{}' source={}",
                                chat_name,
                                chat_kind.as_str(),
                                messages.len(),
                                trim_for_log(&last.content, 24),
                                last.is_self,
                                last.sender,
                                self_source_label(last),
                            );
                        }

                        let baseline = chat_baselines.entry(chat_name.clone()).or_default();
                        if baseline.is_empty() {
                            *baseline = messages;
                        } else {
                            let diff_result = diff_messages(baseline, &messages);
                            if diff_result.anchor_failed && !diff_result.new_messages.is_empty() {
                                events.publish(
                                    &app_handle,
                                    EventType::Log,
                                    "monitor",
                                    serde_json::json!({
                                        "message": format!(
                                            "锚点匹配失败，bag diff 兜底检测到 {} 条新消息",
                                            diff_result.new_messages.len()
                                        ),
                                    }),
                                );
                            }
                            let mut new_msgs = diff_result.new_messages;
                            if apply_cached_preview_sender_hint(
                                &chat_name,
                                &mut new_msgs,
                                &mut chat_kind,
                                &mut preview_sender_hints,
                                now_instant,
                            ) {
                                chat_type_label = chat_kind.as_str().to_string();
                                chat_kinds.insert(chat_name.clone(), chat_kind);
                            }
                            for msg in &new_msgs {
                                let content_en = String::new();
                                let mut found_image_path: Option<String> = None;
                                events.publish(
                                    &app_handle,
                                    EventType::Log,
                                    "monitor_infer",
                                    serde_json::json!({
                                        "type": "message_inferred",
                                        "chat_name": chat_name,
                                        "chat_type": chat_type_label.clone(),
                                        "self_source": self_source_label(msg),
                                        "is_self": msg.is_self,
                                        "sender": msg.sender,
                                        "text_preview": trim_for_log(&msg.content, 24),
                                    }),
                                );

                                events.publish(
                                    &app_handle,
                                    EventType::Message,
                                    "monitor",
                                    serde_json::json!({
                                        "chat_name": chat_name,
                                        "chat_type": chat_type_label.clone(),
                                        "self_source": self_source_label(msg),
                                        "source": "chat",
                                        "quality": "high",
                                        "sender": msg.sender,
                                        "text": msg.content,
                                        "is_self": msg.is_self,
                                    }),
                                );

                                if sidebar_enabled.load(Ordering::Relaxed) {
                                    let (_translator, _target_set, image_capture) = {
                                        let config = sidebar_config.lock().await;
                                        (
                                            config.translator.clone(),
                                            config.target_set.clone(),
                                            config.image_capture,
                                        )
                                    };

                                    if image_capture
                                        && image_cache::is_image_placeholder(&msg.content)
                                    {
                                        let now_ts = std::time::SystemTime::now()
                                            .duration_since(std::time::UNIX_EPOCH)
                                            .unwrap()
                                            .as_secs()
                                            as i64;
                                        let cn = chat_name.clone();
                                        if let Ok(mut cache) = image_cache.lock() {
                                            if let Some(path) =
                                                cache.find_image_for_message(&cn, now_ts)
                                            {
                                                found_image_path =
                                                    Some(path.to_string_lossy().to_string());
                                            }
                                        }
                                    }
                                }

                                let corrected = db
                                    .try_correct_preview_row(
                                        &chat_name,
                                        Some(&chat_type_label),
                                        &msg.content,
                                        &msg.sender,
                                        &content_en,
                                        msg.is_self,
                                        found_image_path.as_deref(),
                                        &now,
                                        SESSION_CORRECTION_WINDOW_SECONDS,
                                    )
                                    .unwrap_or(false);

                                if !corrected {
                                    let _ = db.insert_message_with_meta(
                                        &chat_name,
                                        Some(&chat_type_label),
                                        &msg.sender,
                                        &msg.content,
                                        &content_en,
                                        msg.is_self,
                                        &now,
                                        found_image_path.as_deref(),
                                        "chat",
                                        "high",
                                    );
                                } else {
                                    events.publish(
                                        &app_handle,
                                        EventType::Log,
                                        "monitor_infer",
                                        serde_json::json!({
                                            "type": "preview_corrected",
                                            "chat_name": chat_name,
                                            "text_preview": trim_for_log(&msg.content, 24),
                                        }),
                                    );
                                }

                                if sidebar_enabled.load(Ordering::Relaxed)
                                    && should_forward_sidebar_chat(&chat_name)
                                {
                                    // 更新后端运行态并获取刷新版本号
                                    let refresh_version =
                                        sidebar_runtime.update_chat_and_version(&chat_name);

                                    // 发布 chat_switched 事件（保持兼容）
                                    events.publish(
                                        &app_handle,
                                        EventType::Status,
                                        "monitor",
                                        serde_json::json!({
                                            "type": "chat_switched",
                                            "chat_name": chat_name,
                                        }),
                                    );

                                    // 发布 sidebar-refresh 事件（数据库提交成功后）
                                    events.publish(
                                        &app_handle,
                                        EventType::Status,
                                        "sidebar",
                                        serde_json::json!({
                                            "type": "sidebar-refresh",
                                            "chat_name": chat_name,
                                            "refresh_version": refresh_version,
                                        }),
                                    );

                                    let (translator, limiter) = {
                                        let config = sidebar_config.lock().await;
                                        (config.translator.clone(), config.limiter.clone())
                                    };
                                    let translate_config = manager.translation_service.get_config().await;

                                    let sidebar_event = publish_sidebar_append(
                                        &events,
                                        &app_handle,
                                        &chat_name,
                                        &chat_type_label,
                                        self_source_label(msg),
                                        "chat",
                                        "high",
                                        &msg.sender,
                                        &msg.content,
                                        msg.is_self,
                                        found_image_path.as_deref(),
                                    );

                                    if let (Some(translator), Some(limiter)) = (translator, limiter)
                                    {
                                        spawn_sidebar_translation_update(
                                            manager.clone(),
                                            events.clone(),
                                            app_handle.clone(),
                                            db.clone(),
                                            translator,
                                            limiter,
                                            translate_config.source_lang.clone(),
                                            translate_config.target_lang.clone(),
                                            sidebar_event.id,
                                            chat_name.clone(),
                                            msg.sender.clone(),
                                            msg.content.clone(),
                                            now.clone(),
                                        );
                                    }
                                }
                            }

                            *baseline = messages;
                        }
                    }
                }

                tokio::select! {
                    _ = token.cancelled() => break,
                    _ = tokio::time::sleep(std::time::Duration::from_secs_f64(poll_interval)) => {}
                }
            }

            *monitor_token_ref.lock().await = None;
            monitoring_active.store(false, Ordering::Relaxed);

            let next_state = TaskState {
                monitoring: false,
                sidebar: sidebar_enabled.load(Ordering::Relaxed),
            };

            if !next_state.sidebar {
                manager.next_translator_generation();
                manager.translation_service.set_status(TranslatorServiceStatus::disabled()).await;
            }

            let translator_status = manager.get_translator_status().await;
            manager
                .publish_task_state_event("monitoring", false, &next_state, &translator_status)
                .await;
            update_tray_menu(&app_handle, &next_state, &translator_status);
            app_state::emit_runtime_updated(&app_handle, &manager);
        });

        Ok(())
    }

    pub async fn stop_monitoring(&self) -> Result<()> {
        let token = self.monitor_token.lock().await.clone();
        if let Some(token) = token {
            token.cancel();
        }
        Ok(())
    }

    pub async fn enable_sidebar(
        &self,
        targets: Vec<String>,
        translate_enabled: bool,
        provider: String,
        deeplx_url: String,
        ai_provider_id: String,
        ai_model_id: String,
        ai_api_key: String,
        ai_base_url: String,
        source_lang: String,
        target_lang: String,
        timeout_seconds: f64,
        max_concurrency: usize,
        max_requests_per_second: usize,
        image_capture: bool,
    ) -> Result<()> {
        let translator_generation = self.next_translator_generation();

        // 根据 provider 创建对应的配置
        let provider_config = match provider.as_str() {
            "ai" => TranslateProviderConfig::Ai {
                provider_id: ai_provider_id,
                model_id: ai_model_id,
                api_key: ai_api_key,
                base_url: if ai_base_url.is_empty() { None } else { Some(ai_base_url) },
            },
            _ => TranslateProviderConfig::Deeplx {
                url: deeplx_url,
            },
        };

        let translate_config = TranslateConfig {
            enabled: translate_enabled,
            provider_config,
            source_lang,
            target_lang,
            timeout_seconds,
            max_concurrency,
            max_requests_per_second,
        };

        let translator_status = self.translation_service.update_config(translate_config).await;

        let target_set: HashSet<String> = targets.into_iter().filter(|t| !t.is_empty()).collect();

        // 从 TranslationService 获取内部状态用于 sidebar
        let (translator, limiter) = self.translation_service.get_translator_and_limiter().await;

        {
            let mut config = self.sidebar_config.lock().await;
            config.translator = translator;
            config.limiter = limiter;
            config.target_set = target_set;
            config.image_capture = image_capture;
        }

        self.sidebar_enabled.store(true, Ordering::Relaxed);

        let app = self.get_app_handle().await?;
        let state = self.get_task_state();
        self.publish_task_state_event("sidebar", true, &state, &translator_status)
            .await;
        update_tray_menu(&app, &state, &translator_status);
        app_state::emit_runtime_updated(&app, self);

        // 如果翻译服务已配置，启动健康检查
        if translator_status.configured {
            self.spawn_translator_health_check(translator_generation);
        }

        Ok(())
    }

    pub async fn disable_sidebar(&self) -> Result<()> {
        self.next_translator_generation();
        self.sidebar_enabled.store(false, Ordering::Relaxed);

        {
            let mut config = self.sidebar_config.lock().await;
            config.translator = None;
            config.limiter = None;
            config.target_set.clear();
            config.image_capture = false;
        }

        self.sidebar_runtime.clear();

        self.translation_service.set_status(TranslatorServiceStatus::disabled()).await;

        let app = self.get_app_handle().await?;
        let state = self.get_task_state();
        let translator_status = self.get_translator_status().await;
        self.publish_task_state_event("sidebar", false, &state, &translator_status)
            .await;
        update_tray_menu(&app, &state, &translator_status);
        app_state::emit_runtime_updated(&app, self);

        Ok(())
    }

    pub async fn stop_all(&self) {
        let _ = self.stop_monitoring().await;
        let _ = self.disable_sidebar().await;
    }
}

struct DiffResult {
    new_messages: Vec<ChatMessage>,
    anchor_failed: bool,
}

#[derive(Debug, Clone)]
struct PreviewSenderHint {
    sender: String,
    preview_body: String,
    preview_body_key: String,
    unread_count: u32,
    updated_at: Instant,
    consumed: bool,
}

#[derive(Debug, Clone, Default)]
struct SessionListenState {
    last_preview_body: String,
    last_unread: u32,
}

const PREVIEW_SENDER_HINT_TTL: Duration = Duration::from_secs(12);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ChatKind {
    Group,
    Private,
    Unknown,
}

impl ChatKind {
    fn as_str(self) -> &'static str {
        match self {
            ChatKind::Group => "group",
            ChatKind::Private => "private",
            ChatKind::Unknown => "unknown",
        }
    }
}

fn self_source_label(msg: &ChatMessage) -> &'static str {
    if !msg.sender.is_empty() {
        "prefix"
    } else {
        "fallback"
    }
}

fn should_emit_session_snapshot(
    snapshot: &ax_reader::SessionItemSnapshot,
    state: &SessionListenState,
) -> bool {
    if snapshot.preview_body.is_empty() {
        return false;
    }
    // Only emit when preview text actually changes.
    // Previously also checked `unread_count > last_unread`, but for the active chat
    // the unread count oscillates (0→1→0→1…) as messages arrive and are "read",
    // causing the same preview to be emitted and inserted into DB repeatedly.
    snapshot.preview_body != state.last_preview_body
}

fn apply_sender_defaults(messages: &mut [ChatMessage], chat_name: &str, chat_kind: ChatKind) {
    if matches!(chat_kind, ChatKind::Group) {
        return;
    }
    for msg in messages {
        if !msg.is_self && msg.sender.is_empty() {
            msg.sender = chat_name.to_string();
        }
    }
}

fn trim_for_log(text: &str, max_chars: usize) -> String {
    let normalized = ax_reader::normalize_for_match(text);
    let mut out = normalized.chars().take(max_chars).collect::<String>();
    if normalized.chars().count() > max_chars {
        out.push('…');
    }
    out
}

fn preview_body_matches_message(
    preview_body: &str,
    message_content: &str,
    preview_body_key: Option<&str>,
) -> bool {
    let normalized_preview = ax_reader::normalize_for_match(preview_body);
    let normalized_message = ax_reader::normalize_for_match(message_content);
    if normalized_preview.is_empty() || normalized_message.is_empty() {
        return false;
    }

    if let Some(key) = preview_body_key {
        if !key.is_empty() && key == ax_reader::prefix8_key(&normalized_message) {
            return true;
        }
    } else if ax_reader::is_same_message_prefix8(&normalized_preview, &normalized_message) {
        return true;
    }

    let preview_len = normalized_preview.chars().count();
    let message_len = normalized_message.chars().count();
    (preview_len < 8 && normalized_message.starts_with(&normalized_preview))
        || (message_len < 8 && normalized_preview.starts_with(&normalized_message))
}

fn apply_session_preview_sender_hint(
    messages: &mut [ChatMessage],
    preview_text: &str,
    chat_kind: &mut ChatKind,
    unread_increased: bool,
) {
    if messages.is_empty() {
        return;
    }
    let (sender, preview_body) = ax_reader::parse_session_preview_line(preview_text);
    let Some(preview_body) = preview_body else {
        return;
    };
    if let Some(last) = messages.last_mut() {
        let text_matched = preview_body_matches_message(&preview_body, &last.content, None);
        let image_equivalent =
            is_image_placeholder_like(&preview_body) && is_image_placeholder_like(&last.content);
        let matched = text_matched || image_equivalent;

        match sender {
            Some(sender) if !sender.is_empty() => {
                *chat_kind = ChatKind::Group;
                if matched {
                    last.sender = sender;
                    last.is_self = false;
                    debug!(
                        "preview_hint matched(group) body='{}' latest='{}' -> sender='{}'",
                        trim_for_log(&preview_body, 24),
                        trim_for_log(&last.content, 24),
                        last.sender,
                    );
                }
            }
            _ => {
                if *chat_kind != ChatKind::Group {
                    *chat_kind = ChatKind::Private;
                }
                if matched {
                    // For private chats (no sender prefix), use unread signal:
                    // unread grew → other person; unread stable → likely self
                    let is_self_hint = if matches!(*chat_kind, ChatKind::Group) {
                        true // group without prefix → self (unchanged)
                    } else if unread_increased {
                        false // private, unread grew → other person
                    } else {
                        true // private, unread stable → likely self
                    };
                    last.sender.clear();
                    last.is_self = is_self_hint;
                    debug!(
                        "preview_hint no_sender kind={} matched={} unread_inc={} body='{}' latest='{}' -> is_self={}",
                        chat_kind.as_str(),
                        matched,
                        unread_increased,
                        trim_for_log(&preview_body, 24),
                        trim_for_log(&last.content, 24),
                        last.is_self,
                    );
                }
            }
        }
    }
}

fn cleanup_preview_sender_hints(cache: &mut HashMap<String, PreviewSenderHint>, now: Instant) {
    cache.retain(|_, hint| {
        !hint.consumed && now.duration_since(hint.updated_at) <= PREVIEW_SENDER_HINT_TTL
    });
}

fn remember_preview_sender_hint(
    cache: &mut HashMap<String, PreviewSenderHint>,
    snapshot: &ax_reader::SessionItemSnapshot,
    now: Instant,
) {
    if !snapshot.has_sender_prefix {
        return;
    }

    let Some(sender) = snapshot
        .sender_hint
        .as_ref()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
    else {
        return;
    };

    let preview_body = snapshot.preview_body.trim();
    if preview_body.is_empty() {
        return;
    }

    cache.insert(
        snapshot.chat_name.clone(),
        PreviewSenderHint {
            sender: sender.to_string(),
            preview_body: preview_body.to_string(),
            preview_body_key: ax_reader::prefix8_key(preview_body),
            unread_count: snapshot.unread_count,
            updated_at: now,
            consumed: false,
        },
    );
}

fn apply_cached_preview_sender_hint(
    chat_name: &str,
    new_messages: &mut [ChatMessage],
    chat_kind: &mut ChatKind,
    cache: &mut HashMap<String, PreviewSenderHint>,
    now: Instant,
) -> bool {
    let Some(hint) = cache.get_mut(chat_name) else {
        return false;
    };

    if hint.consumed || now.duration_since(hint.updated_at) > PREVIEW_SENDER_HINT_TTL {
        return false;
    }

    for msg in new_messages.iter_mut().rev() {
        let text_matched = preview_body_matches_message(
            &hint.preview_body,
            &msg.content,
            Some(&hint.preview_body_key),
        );
        let image_equivalent = is_image_placeholder_like(&hint.preview_body)
            && is_image_placeholder_like(&msg.content);
        if !text_matched && !image_equivalent {
            continue;
        }

        *chat_kind = ChatKind::Group;
        msg.sender = hint.sender.clone();
        msg.is_self = false;
        hint.consumed = true;
        debug!(
            "preview_hint cache matched chat='{}' unread={} body='{}' latest='{}' -> sender='{}'",
            chat_name,
            hint.unread_count,
            trim_for_log(&hint.preview_body, 24),
            trim_for_log(&msg.content, 24),
            msg.sender,
        );
        return true;
    }

    false
}

fn is_image_placeholder_like(text: &str) -> bool {
    let normalized = ax_reader::normalize_for_match(text);
    if normalized.is_empty() {
        return false;
    }
    let stripped = normalized
        .trim_matches(|c| matches!(c, '[' | ']' | '【' | '】' | '(' | ')'))
        .to_lowercase();
    matches!(
        stripped.as_str(),
        "图片" | "image" | "images" | "photo" | "photos" | "照片"
    )
}

/// Reuse known sender labels from a previous visible slice by matching content.
/// We consume from the tail first so the newest repeated texts are aligned first.
fn inherit_sender_from_reference(current: &mut [ChatMessage], reference: &[ChatMessage]) {
    if current.is_empty() || reference.is_empty() {
        return;
    }

    let mut sender_bag: HashMap<String, Vec<String>> = HashMap::new();
    for msg in reference.iter().rev() {
        if !msg.sender.is_empty() {
            sender_bag
                .entry(msg.content.clone())
                .or_default()
                .push(msg.sender.clone());
        }
    }

    for msg in current.iter_mut().rev() {
        if !msg.sender.is_empty() {
            continue;
        }
        if let Some(candidates) = sender_bag.get_mut(&msg.content) {
            if let Some(sender) = candidates.pop() {
                msg.sender = sender;
            }
        }
    }
}

/// Find new messages by comparing old and new message lists.
/// Strategy: tail-append → progressive anchor (3→2→1) → bag diff fallback.
fn diff_messages(old: &[ChatMessage], new: &[ChatMessage]) -> DiffResult {
    if old.is_empty() || new.is_empty() {
        return DiffResult {
            new_messages: vec![],
            anchor_failed: false,
        };
    }

    if new.len() == old.len() && contents_match(old, new) {
        return DiffResult {
            new_messages: vec![],
            anchor_failed: false,
        };
    }

    if new.len() > old.len() {
        let old_len = old.len();
        if contents_match(&new[..old_len], old) {
            return DiffResult {
                new_messages: new[old_len..].to_vec(),
                anchor_failed: false,
            };
        }
    }

    if let Some(result) = anchor_diff_progressive(old, new) {
        return DiffResult {
            new_messages: result,
            anchor_failed: false,
        };
    }

    DiffResult {
        new_messages: bag_diff(old, new),
        anchor_failed: true,
    }
}

fn msg_identity_content(m: &ChatMessage) -> &str {
    &m.content
}

fn contents_match(a: &[ChatMessage], b: &[ChatMessage]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter()
        .zip(b.iter())
        .all(|(x, y)| msg_identity_content(x) == msg_identity_content(y))
}

/// Try anchor matching with progressively smaller anchor sizes (3→2→1).
/// Returns Some(new_messages) on success, None if no anchor matched.
fn anchor_diff_progressive(old: &[ChatMessage], new: &[ChatMessage]) -> Option<Vec<ChatMessage>> {
    if old.is_empty() || new.is_empty() {
        return Some(vec![]);
    }

    let max_anchor = 3.min(old.len());
    for anchor_size in (1..=max_anchor).rev() {
        let anchor: Vec<&str> = old[old.len() - anchor_size..]
            .iter()
            .map(msg_identity_content)
            .collect();

        for i in 0..new.len() {
            if i + anchor_size > new.len() {
                break;
            }
            let window: Vec<&str> = new[i..i + anchor_size]
                .iter()
                .map(msg_identity_content)
                .collect();
            if window == anchor {
                let after = i + anchor_size;
                if after < new.len() {
                    return Some(new[after..].to_vec());
                }
                return Some(vec![]);
            }
        }
    }

    None
}

/// Bag (multiset) diff: find messages in `new` not present in `old`.
/// Handles cases where the view scrolled significantly and anchor is lost.
fn bag_diff(old: &[ChatMessage], new: &[ChatMessage]) -> Vec<ChatMessage> {
    let mut bag: HashMap<&str, usize> = HashMap::new();
    for m in old {
        *bag.entry(msg_identity_content(m)).or_default() += 1;
    }
    let mut result = Vec::new();
    for m in new {
        let key = msg_identity_content(m);
        match bag.get_mut(&key) {
            Some(count) if *count > 0 => {
                *count -= 1;
            }
            _ => {
                result.push(m.clone());
            }
        }
    }
    result
}

fn should_forward_session_preview(
    use_right_panel_details: bool,
    snapshot_chat_name: &str,
    active_chat_name: &str,
) -> bool {
    !use_right_panel_details || snapshot_chat_name != active_chat_name
}

fn should_forward_sidebar_chat(event_chat_name: &str) -> bool {
    !event_chat_name.is_empty()
}

fn publish_sidebar_append(
    events: &EventStore,
    app_handle: &AppHandle,
    chat_name: &str,
    chat_type: &str,
    self_source: &str,
    source: &str,
    quality: &str,
    sender: &str,
    text_cn: &str,
    is_self: bool,
    image_path: Option<&str>,
) -> crate::events::ServiceEvent {
    let mut payload = serde_json::json!({
        "kind": "append",
        "chat_name": chat_name,
        "chat_type": chat_type,
        "self_source": self_source,
        "source": source,
        "quality": quality,
        "sender": sender,
        "text_cn": text_cn,
        "text_en": "",
        "translate_error": "",
        "is_self": is_self,
    });
    if let Some(path) = image_path {
        payload["image_path"] = serde_json::Value::String(path.to_string());
    }

    events.publish(app_handle, EventType::Message, "sidebar", payload)
}

fn spawn_sidebar_translation_update(
    manager: TaskManager,
    events: Arc<EventStore>,
    app_handle: AppHandle,
    db: Arc<MessageDb>,
    translator: Arc<dyn crate::translator::Translator>,
    limiter: Arc<TranslationLimiter>,
    source_lang: String,
    target_lang: String,
    message_id: u64,
    chat_name: String,
    sender: String,
    content: String,
    detected_at: String,
) {
    tokio::spawn(async move {
        log::info!("[spawn_sidebar_translation_update] 翻译任务启动: message_id={}", message_id);
        let translator_generation = manager.translator_generation.load(Ordering::Relaxed);

        if let Ok(Some(cached)) = db.get_cached_translation(&content, &source_lang, &target_lang) {
            log::info!("[spawn_sidebar_translation_update] 使用缓存翻译: {}", &cached.translated_text[..cached.translated_text.len().min(50)]);
            let _ = db.update_message_translation(
                &chat_name,
                &sender,
                &content,
                &detected_at,
                &cached.translated_text,
            );

            // 译文写回成功后，递增刷新版本并发布 sidebar-refresh 事件
            let refresh_version = manager.sidebar_runtime.increment_refresh_version();
            events.publish(
                &app_handle,
                EventType::Status,
                "sidebar",
                serde_json::json!({
                    "type": "sidebar-refresh",
                    "chat_name": chat_name,
                    "refresh_version": refresh_version,
                }),
            );

            events.publish(
                &app_handle,
                EventType::Message,
                "sidebar",
                serde_json::json!({
                    "kind": "update",
                    "message_id": message_id,
                    "chat_name": chat_name,
                    "text_en": cached.translated_text,
                    "translate_error": "",
                }),
            );
            return;
        }

        log::info!("[spawn_sidebar_translation_update] 开始实际翻译");
        let _permit = limiter.acquire().await;
        log::info!("[spawn_sidebar_translation_update] 获得限流许可");
        match translator.translate(&content, &source_lang, &target_lang).await {
            Ok(translated) => {
                log::info!("[spawn_sidebar_translation_update] 翻译成功: {}", &translated[..translated.len().min(50)]);
                let _ =
                    db.upsert_cached_translation(&content, &source_lang, &target_lang, &translated);
                let _ = db.update_message_translation(
                    &chat_name,
                    &sender,
                    &content,
                    &detected_at,
                    &translated,
                );
                let provider = translator.provider_id().to_string();
                manager
                    .set_translator_status_if_current(
                        translator_generation,
                        TranslatorServiceStatus::healthy(&provider),
                    )
                    .await;

                // 译文写回成功后，递增刷新版本并发布 sidebar-refresh 事件
                let refresh_version = manager.sidebar_runtime.increment_refresh_version();
                events.publish(
                    &app_handle,
                    EventType::Status,
                    "sidebar",
                    serde_json::json!({
                        "type": "sidebar-refresh",
                        "chat_name": chat_name,
                        "refresh_version": refresh_version,
                    }),
                );

                events.publish(
                    &app_handle,
                    EventType::Message,
                    "sidebar",
                    serde_json::json!({
                        "kind": "update",
                        "message_id": message_id,
                        "chat_name": chat_name,
                        "text_en": translated,
                        "translate_error": "",
                    }),
                );
            }
            Err(error) => {
                let translate_error = error.to_string();
                let provider = translator.provider_id().to_string();
                manager
                    .set_translator_status_if_current(
                        translator_generation,
                        TranslatorServiceStatus::error(&provider, &translate_error),
                    )
                    .await;
                events.publish(
                    &app_handle,
                    EventType::Message,
                    "sidebar",
                    serde_json::json!({
                        "kind": "update",
                        "message_id": message_id,
                        "chat_name": chat_name,
                        "text_en": "",
                        "translate_error": translate_error,
                    }),
                );
            }
        }
    });
}

fn short_error_text(message: &str) -> String {
    const MAX_CHARS: usize = 120;
    let shortened: String = message.chars().take(MAX_CHARS).collect();
    if message.chars().count() > MAX_CHARS {
        format!("{shortened}...")
    } else {
        shortened
    }
}

fn update_tray_menu(
    app: &AppHandle,
    state: &TaskState,
    translator_status: &TranslatorServiceStatus,
) {
    if let Some(tray) = app.try_state::<crate::TrayMenuState>() {
        let _ = tray.sidebar_status.set_text(if state.sidebar {
            "● 浮窗运行中"
        } else {
            "○ 浮窗未运行"
        });
        let _ = tray.sidebar_toggle.set_text(if state.sidebar {
            "关闭浮窗"
        } else {
            "开启实时浮窗"
        });

        let _ = tray.listen_status.set_text(if state.monitoring {
            "● 监听运行中"
        } else {
            "○ 监听未运行"
        });
        let _ = tray.listen_toggle.set_text(if state.monitoring {
            "暂停监听"
        } else {
            "开启监听"
        });
        let _ = tray
            .translate_status
            .set_text(translator_status.menu_text());
    }
}

#[cfg(test)]
mod tests {
    use super::{
        short_error_text, should_forward_session_preview, should_forward_sidebar_chat,
        TranslatorServiceStatus,
    };

    #[test]
    fn translator_status_menu_text_matches_state() {
        assert_eq!(
            TranslatorServiceStatus::disabled().menu_text(),
            "○ 翻译未启用"
        );
        assert_eq!(
            TranslatorServiceStatus::unconfigured("deeplx").menu_text(),
            "○ 翻译未配置"
        );
        assert_eq!(
            TranslatorServiceStatus::checking("deeplx").menu_text(),
            "◐ 翻译检测中"
        );
        assert_eq!(
            TranslatorServiceStatus::healthy("deeplx").menu_text(),
            "● 翻译服务可用"
        );
        assert_eq!(
            TranslatorServiceStatus::error("deeplx", "boom").menu_text(),
            "⚠ 翻译服务异常"
        );
    }

    #[test]
    fn translator_status_json_contains_expected_fields() {
        let status = TranslatorServiceStatus::error("deeplx", "request failed");
        let json = status.as_json();

        assert_eq!(json["enabled"], true);
        assert_eq!(json["configured"], true);
        assert_eq!(json["checking"], false);
        assert_eq!(json["healthy"], false);
        assert_eq!(json["last_error"], "request failed");
    }

    #[test]
    fn short_error_text_truncates_long_messages() {
        let message = "x".repeat(140);
        let shortened = short_error_text(&message);

        assert_eq!(shortened.len(), 123);
        assert!(shortened.ends_with("..."));
    }

    #[test]
    fn session_preview_forwarding_skips_active_chat_when_right_panel_enabled() {
        assert!(should_forward_session_preview(false, "项目群", "项目群"));
        assert!(should_forward_session_preview(true, "另一个群", "项目群"));
        assert!(!should_forward_session_preview(true, "项目群", "项目群"));
    }

    #[test]
    fn sidebar_forwarding_requires_non_empty_chat_name() {
        assert!(should_forward_sidebar_chat("项目群"));
        assert!(should_forward_sidebar_chat("另一个群"));
        assert!(!should_forward_sidebar_chat(""));
    }
}
