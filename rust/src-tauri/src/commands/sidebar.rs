use crate::config::{load_app_config, ConfigDir};
use crate::db::MessageDb;
use crate::sidebar_window::{SidebarWindowState, WindowMode};
use crate::task_manager::TaskManager;
use crate::translator::{AiTranslator, DeepLXTranslator, Translator};
use std::sync::Arc;
use std::time::Duration;

#[tauri::command]
pub async fn sidebar_start(
    config_dir: tauri::State<'_, ConfigDir>,
    manager: tauri::State<'_, TaskManager>,
    targets: Option<Vec<String>>,
    translate_enabled: Option<bool>,
    provider: Option<String>,
    deeplx_url: Option<String>,
    ai_provider_id: Option<String>,
    ai_model_id: Option<String>,
    ai_api_key: Option<String>,
    ai_base_url: Option<String>,
    source_lang: Option<String>,
    target_lang: Option<String>,
    timeout_seconds: Option<f64>,
    max_concurrency: Option<usize>,
    max_requests_per_second: Option<usize>,
    image_capture: Option<bool>,
) -> Result<serde_json::Value, String> {
    let config = load_app_config(&config_dir.0).map_err(|e| e.to_string())?;
    manager
        .set_use_right_panel_details(config.listen.use_right_panel_details)
        .await;

    let translate_enabled = translate_enabled.unwrap_or(config.translate.enabled);
    let provider = provider.unwrap_or_else(|| config.translate.provider.clone());
    let deeplx_url = deeplx_url.unwrap_or_else(|| config.translate.deeplx_url.clone());
    let ai_provider_id = ai_provider_id.unwrap_or_else(|| config.translate.ai_provider_id.clone());
    let ai_model_id = ai_model_id.unwrap_or_else(|| config.translate.ai_model_id.clone());
    let ai_api_key = ai_api_key.unwrap_or_else(|| config.translate.ai_api_key.clone());
    let ai_base_url = ai_base_url.unwrap_or_else(|| config.translate.ai_base_url.clone());

    manager
        .enable_sidebar(
            targets.unwrap_or_default(),
            translate_enabled,
            provider,
            deeplx_url,
            ai_provider_id,
            ai_model_id,
            ai_api_key,
            ai_base_url,
            source_lang.unwrap_or_else(|| config.translate.source_lang.clone()),
            target_lang.unwrap_or_else(|| config.translate.target_lang.clone()),
            timeout_seconds.unwrap_or(config.translate.timeout_seconds),
            max_concurrency.unwrap_or(config.translate.max_concurrency),
            max_requests_per_second.unwrap_or(config.translate.max_requests_per_second),
            image_capture.unwrap_or(false),
        )
        .await
        .map_err(|e| e.to_string())?;

    Ok(serde_json::json!({ "ok": true, "message": "sidebar enabled" }))
}

#[tauri::command]
pub async fn sidebar_stop(
    app: tauri::AppHandle,
    manager: tauri::State<'_, TaskManager>,
    sidebar_state: tauri::State<'_, Arc<SidebarWindowState>>,
) -> Result<serde_json::Value, String> {
    manager.disable_sidebar().await.map_err(|e| e.to_string())?;
    let _ = sidebar_state.close(&app).await;
    Ok(serde_json::json!({ "ok": true, "message": "sidebar disabled" }))
}

#[tauri::command]
pub async fn live_start(
    app: tauri::AppHandle,
    config_dir: tauri::State<'_, ConfigDir>,
    manager: tauri::State<'_, TaskManager>,
    sidebar_state: tauri::State<'_, Arc<SidebarWindowState>>,
    translate_enabled: Option<bool>,
    provider: Option<String>,
    deeplx_url: Option<String>,
    ai_provider_id: Option<String>,
    ai_model_id: Option<String>,
    ai_api_key: Option<String>,
    ai_base_url: Option<String>,
    source_lang: Option<String>,
    target_lang: Option<String>,
    interval_seconds: Option<f64>,
    timeout_seconds: Option<f64>,
    max_concurrency: Option<usize>,
    max_requests_per_second: Option<usize>,
    image_capture: Option<bool>,
    window_mode: Option<String>,
) -> Result<serde_json::Value, String> {
    let mode = WindowMode::from_str_opt(window_mode.as_deref());
    let config = load_app_config(&config_dir.0).map_err(|e| e.to_string())?;
    manager
        .set_use_right_panel_details(config.listen.use_right_panel_details)
        .await;

    let translate_enabled = translate_enabled.unwrap_or(config.translate.enabled);
    let provider = provider.unwrap_or_else(|| config.translate.provider.clone());
    let deeplx_url = deeplx_url.unwrap_or_else(|| config.translate.deeplx_url.clone());
    let ai_provider_id = ai_provider_id.unwrap_or_else(|| config.translate.ai_provider_id.clone());
    let ai_model_id = ai_model_id.unwrap_or_else(|| config.translate.ai_model_id.clone());
    let ai_api_key = ai_api_key.unwrap_or_else(|| config.translate.ai_api_key.clone());
    let ai_base_url = ai_base_url.unwrap_or_else(|| config.translate.ai_base_url.clone());

    let state = manager.get_task_state();
    if !state.monitoring {
        let interval = interval_seconds.unwrap_or(1.0);
        manager
            .start_monitoring(interval)
            .await
            .map_err(|e| e.to_string())?;
    }

    manager
        .enable_sidebar(
            vec![],
            translate_enabled,
            provider,
            deeplx_url,
            ai_provider_id,
            ai_model_id,
            ai_api_key,
            ai_base_url,
            source_lang.unwrap_or_else(|| config.translate.source_lang.clone()),
            target_lang.unwrap_or_else(|| config.translate.target_lang.clone()),
            timeout_seconds.unwrap_or(config.translate.timeout_seconds),
            max_concurrency.unwrap_or(config.translate.max_concurrency),
            max_requests_per_second.unwrap_or(config.translate.max_requests_per_second),
            image_capture.unwrap_or(false),
        )
        .await
        .map_err(|e| e.to_string())?;

    // 等待监听循环首次 poll 完成后再打开窗口
    // 确保 SidebarRuntime.current_chat 已经被设置，避免显示错误数据
    let first_chat = manager
        .wait_first_poll(Duration::from_secs(5))
        .await;

    if let Some(chat_name) = first_chat {
        // 确保 sidebar_runtime 的 current_chat 已设置
        let runtime = manager.get_sidebar_runtime();
        if runtime.get_current_chat().is_empty() {
            runtime.set_current_chat(&chat_name);
        }
    }

    let _ = sidebar_state
        .open(
            &app,
            Some(config.display.width as f64),
            mode,
            Some(config.display.collapsed_display_count),
            Some(config.display.ghost_mode),
            Some(config.display.sidebar_appearance.clone()),
        )
        .await;

    Ok(serde_json::json!({ "ok": true, "message": "live started" }))
}

#[tauri::command]
pub async fn sidebar_window_open(
    app: tauri::AppHandle,
    config_dir: tauri::State<'_, ConfigDir>,
    state: tauri::State<'_, Arc<SidebarWindowState>>,
    width: Option<f64>,
    window_mode: Option<String>,
) -> Result<serde_json::Value, String> {
    let mode = WindowMode::from_str_opt(window_mode.as_deref());
    let config = load_app_config(&config_dir.0).map_err(|e| e.to_string())?;
    state
        .open(
            &app,
            width.or(Some(config.display.width as f64)),
            mode,
            Some(config.display.collapsed_display_count),
            Some(config.display.ghost_mode),
            Some(config.display.sidebar_appearance.clone()),
        )
        .await
        .map_err(|e| e.to_string())?;
    Ok(serde_json::json!({ "ok": true, "message": "sidebar window opened" }))
}

#[tauri::command]
pub async fn sidebar_window_close(
    app: tauri::AppHandle,
    state: tauri::State<'_, Arc<SidebarWindowState>>,
) -> Result<serde_json::Value, String> {
    state.close(&app).await.map_err(|e| e.to_string())?;
    Ok(serde_json::json!({ "ok": true, "message": "sidebar window closed" }))
}

#[tauri::command]
pub async fn sidebar_snapshot_get(
    db: tauri::State<'_, Arc<MessageDb>>,
    manager: tauri::State<'_, TaskManager>,
    chat_name: Option<String>,
    limit: Option<i64>,
) -> Result<serde_json::Value, String> {
    let runtime = manager.get_sidebar_runtime();
    let runtime_chat = runtime.get_current_chat();
    let refresh_version = runtime.get_refresh_version();

    // 优先使用后端运行态的 current_chat，前端传入的 chat_name 作为备选
    let selected_chat = if !runtime_chat.is_empty() {
        Some(runtime_chat)
    } else {
        match chat_name.as_deref().map(str::trim).filter(|name| !name.is_empty()) {
            Some(name) => Some(name.to_string()),
            None => db.latest_chat_name().map_err(|e| e.to_string())?,
        }
    };

    let messages = if let Some(chat) = selected_chat.as_deref() {
        db.query_messages(Some(chat), None, None, limit.unwrap_or(50), 0)
            .map_err(|e| e.to_string())?
    } else {
        Vec::new()
    };

    let translator_status = manager.get_translator_status().await;
    Ok(serde_json::json!({
        "ok": true,
        "data": {
            "current_chat": selected_chat,
            "messages": messages,
            "translator": translator_status,
            "refresh_version": refresh_version,
        }
    }))
}

#[tauri::command]
pub async fn translate_test(
    provider: Option<String>,
    deeplx_url: Option<String>,
    ai_provider_id: Option<String>,
    ai_model_id: Option<String>,
    ai_api_key: Option<String>,
    ai_base_url: Option<String>,
    source_lang: Option<String>,
    target_lang: Option<String>,
    timeout_seconds: Option<f64>,
) -> Result<serde_json::Value, String> {
    let source = source_lang.unwrap_or_else(|| "auto".to_string());
    let target = target_lang.unwrap_or_else(|| "EN".to_string());
    let timeout = timeout_seconds.unwrap_or(8.0);
    let provider = provider.unwrap_or_else(|| "deeplx".to_string());

    let translator: Box<dyn Translator + Send + Sync> = match provider.as_str() {
        "ai" => {
            let api_key = ai_api_key.unwrap_or_default();
            let base_url = ai_base_url.unwrap_or_default();
            let model_id = ai_model_id.unwrap_or_default();
            let provider_id = ai_provider_id.unwrap_or_default();

            if api_key.is_empty() {
                return Err("API Key 不能为空".to_string());
            }
            if model_id.is_empty() {
                return Err("请选择模型".to_string());
            }

            Box::new(
                AiTranslator::new(
                    &provider_id,
                    &model_id,
                    &api_key,
                    if base_url.is_empty() { None } else { Some(&base_url) },
                    &source,
                    &target,
                    timeout,
                )
                .map_err(|e| e.to_string())?,
            )
        }
        _ => {
            let url = deeplx_url.unwrap_or_default();
            if url.is_empty() {
                return Err("DeepLX 地址不能为空".to_string());
            }
            Box::new(DeepLXTranslator::new(&url, &source, &target, timeout))
        }
    };

    match translator.translate("你好，世界", &source, &target).await {
        Ok(result) => Ok(serde_json::json!({ "ok": true, "data": result })),
        Err(e) => Err(format!("{}", e)),
    }
}

/// 手动翻译侧边栏消息
/// 翻译完成后更新数据库并发送刷新事件
#[tauri::command]
pub async fn translate_sidebar_message(
    app: tauri::AppHandle,
    manager: tauri::State<'_, TaskManager>,
    message_id: u64,
    chat_name: String,
    sender: String,
    content: String,
    detected_at: String,
) -> Result<(), String> {
    log::info!(
        "[Sidebar] 收到手动翻译请求: message_id={}, chat_name={}, content={}",
        message_id,
        chat_name,
        &content[..content.len().min(50)]
    );
    let result = manager
        .translate_message_manually(
            app,
            message_id,
            chat_name,
            sender,
            content,
            detected_at,
        )
        .await;
    if let Err(ref e) = result {
        log::error!("[Sidebar] 手动翻译失败: {}", e);
    } else {
        log::info!("[Sidebar] 手动翻译请求已提交");
    }
    result
}
