pub mod adapter;
mod app_state;
mod audio_cache;
mod commands;
mod config;
pub mod db;
pub mod dictionary;
mod events;
mod image_cache;
pub mod sidebar_window;
mod task_manager;
pub mod translator;

use adapter::MacOSAdapter;
use config::{load_app_config, ConfigDir};
use db::MessageDb;
use events::EventStore;
use image_cache::WeChatImageCache;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use task_manager::TaskManager;
use translator::TranslationService;
use tauri::menu::{CheckMenuItemBuilder, Menu, MenuBuilder, MenuItemBuilder, SubmenuBuilder};
use tauri::tray::TrayIconBuilder;
use tauri::Manager;
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};

pub struct CloseToTray(pub Arc<AtomicBool>);

pub struct TrayMenuState {
    pub translate_enabled_check: Option<tauri::menu::CheckMenuItem<tauri::Wry>>,
    pub sidebar_status: tauri::menu::MenuItem<tauri::Wry>,
    pub listen_status: tauri::menu::MenuItem<tauri::Wry>,
    pub translate_status: tauri::menu::MenuItem<tauri::Wry>,
    pub sidebar_toggle: tauri::menu::MenuItem<tauri::Wry>,
    pub listen_toggle: tauri::menu::MenuItem<tauri::Wry>,
    pub translate_toggle: tauri::menu::CheckMenuItem<tauri::Wry>,
    pub ghost_mode_toggle: tauri::menu::CheckMenuItem<tauri::Wry>,
    pub close_to_tray_check: tauri::menu::CheckMenuItem<tauri::Wry>,
}

#[cfg(debug_assertions)]
fn open_main_window_devtools<M: Manager<tauri::Wry>>(manager: &M) {
    if let Some(window) = manager.get_webview_window("main") {
        if !window.is_devtools_open() {
            window.open_devtools();
        }
    }
}

fn sync_translate_enabled_menu(app: &tauri::AppHandle, enabled: bool) {
    if let Some(menu_state) = app.try_state::<TrayMenuState>() {
        if let Some(toggle) = &menu_state.translate_enabled_check {
            let _ = toggle.set_checked(enabled);
        }
    }
}

fn show_app_message(
    app: &tauri::AppHandle,
    title: &str,
    message: impl Into<String>,
    kind: MessageDialogKind,
) {
    let mut dialog = app
        .dialog()
        .message(message.into())
        .title(title)
        .kind(kind)
        .buttons(MessageDialogButtons::Ok);

    if let Some(window) = app.get_webview_window("main") {
        dialog = dialog.parent(&window);
    }

    dialog.show(|_| {});
}

fn handle_tray_toggle_translate(app: &tauri::AppHandle) {
    let desired_enabled = app
        .try_state::<TrayMenuState>()
        .and_then(|tray| tray.translate_toggle.is_checked().ok())
        .unwrap_or(false);
    let app_handle = app.clone();

    tauri::async_runtime::spawn(async move {
        let config_dir = ConfigDir(app_handle.state::<ConfigDir>().0.clone());
        let manager = app_handle.state::<TaskManager>().inner().clone();
        let close_to_tray = CloseToTray(app_handle.state::<CloseToTray>().0.clone());

        let snapshot = match app_state::load_snapshot_sync(&config_dir, &manager, &close_to_tray) {
            Ok(snapshot) => snapshot,
            Err(error) => {
                sync_tray_translate_toggle(&app_handle, false);
                show_app_message(
                    &app_handle,
                    "更新翻译设置失败",
                    format!("读取当前配置失败：{error}"),
                    MessageDialogKind::Error,
                );
                return;
            }
        };

        let mut new_settings = serde_json::to_value(&snapshot.settings).unwrap_or_default();
        if let Some(translate) = new_settings.get_mut("translate") {
            translate["enabled"] = serde_json::Value::Bool(desired_enabled);
        }

        match commands::app_state::save_settings(
            &app_handle,
            &config_dir,
            &manager,
            &close_to_tray,
            new_settings,
        )
        .await
        {
            Ok(_) => {
                sync_tray_translate_toggle(&app_handle, desired_enabled);
                sync_translate_enabled_menu(&app_handle, desired_enabled);
            }
            Err(error) => {
                sync_tray_translate_toggle(&app_handle, !desired_enabled);
                show_app_message(
                    &app_handle,
                    "更新翻译设置失败",
                    format!("保存配置失败：{error}"),
                    MessageDialogKind::Error,
                );
            }
        }
    });
}

fn sync_tray_translate_toggle(app: &tauri::AppHandle, enabled: bool) {
    if let Some(tray) = app.try_state::<TrayMenuState>() {
        let _ = tray.translate_toggle.set_checked(enabled);
    }
}

fn handle_toggle_translate_enabled_menu(app: &tauri::AppHandle) {
    let desired_enabled = app
        .try_state::<TrayMenuState>()
        .and_then(|menu_state| {
            menu_state
                .translate_enabled_check
                .as_ref()
                .and_then(|toggle| toggle.is_checked().ok())
        })
        .unwrap_or(false);
    let app_handle = app.clone();

    tauri::async_runtime::spawn(async move {
        let config_dir = ConfigDir(app_handle.state::<ConfigDir>().0.clone());
        let manager = app_handle.state::<TaskManager>().inner().clone();
        let close_to_tray = CloseToTray(app_handle.state::<CloseToTray>().0.clone());

        let snapshot = match app_state::load_snapshot_sync(&config_dir, &manager, &close_to_tray) {
            Ok(snapshot) => snapshot,
            Err(error) => {
                sync_translate_enabled_menu(&app_handle, false);
                show_app_message(
                    &app_handle,
                    "更新翻译设置失败",
                    format!("读取当前配置失败：{error}"),
                    MessageDialogKind::Error,
                );
                return;
            }
        };

        let previous_enabled = snapshot.settings.translate.enabled;
        if desired_enabled && snapshot.settings.translate.deeplx_url.trim().is_empty() {
            sync_translate_enabled_menu(&app_handle, previous_enabled);
            show_app_message(
                &app_handle,
                "翻译未配置",
                "请先在设置页配置 DeepLX 地址",
                MessageDialogKind::Warning,
            );
            return;
        }

        let mut settings = snapshot.settings;
        settings.translate.enabled = desired_enabled;
        let settings_value = match serde_json::to_value(&settings) {
            Ok(value) => value,
            Err(error) => {
                sync_translate_enabled_menu(&app_handle, previous_enabled);
                show_app_message(
                    &app_handle,
                    "更新翻译设置失败",
                    format!("序列化设置失败：{error}"),
                    MessageDialogKind::Error,
                );
                return;
            }
        };

        match commands::app_state::save_settings(
            &app_handle,
            &config_dir,
            &manager,
            &close_to_tray,
            settings_value,
        )
        .await
        {
            Ok(result) => {
                if !result
                    .get("ok")
                    .and_then(|value| value.as_bool())
                    .unwrap_or(false)
                {
                    sync_translate_enabled_menu(&app_handle, previous_enabled);
                    sync_tray_translate_toggle(&app_handle, previous_enabled);
                    let detail = result
                        .get("errors")
                        .cloned()
                        .unwrap_or_else(|| serde_json::json!(["未知错误"]));
                    show_app_message(
                        &app_handle,
                        "更新翻译设置失败",
                        format!("保存设置失败：{detail}"),
                        MessageDialogKind::Warning,
                    );
                } else {
                    sync_tray_translate_toggle(&app_handle, desired_enabled);
                }
            }
            Err(error) => {
                sync_translate_enabled_menu(&app_handle, previous_enabled);
                sync_tray_translate_toggle(&app_handle, previous_enabled);
                show_app_message(
                    &app_handle,
                    "更新翻译设置失败",
                    format!("保存设置失败：{error}"),
                    MessageDialogKind::Error,
                );
            }
        }
    });
}

fn build_macos_app_menu(
    app: &tauri::App<tauri::Wry>,
    translate_enabled: bool,
) -> tauri::Result<(Menu<tauri::Wry>, tauri::menu::CheckMenuItem<tauri::Wry>)> {
    let menu = Menu::default(app.handle())?;
    let translate_enabled_check =
        CheckMenuItemBuilder::with_id("toggle_translate_enabled", "启用翻译")
            .checked(translate_enabled)
            .build(app)?;
    let translate_menu = SubmenuBuilder::with_id(app, "translate_menu", "翻译")
        .item(&translate_enabled_check)
        .build()?;
    let data_menu = SubmenuBuilder::with_id(app, "data_menu", "数据")
        .text("clear_db_restart", "清空数据库并重启")
        .build()?;
    let dev_menu = SubmenuBuilder::with_id(app, "dev_menu", "开发")
        .text("open_devtools", "打开主窗口开发者工具")
        .text("open_sidebar_devtools", "打开侧边栏开发者工具")
        .build()?;
    menu.append(&translate_menu)?;
    menu.append(&data_menu)?;
    menu.append(&dev_menu)?;
    Ok((menu, translate_enabled_check))
}

fn handle_clear_db_restart_menu(app: &tauri::AppHandle) {
    let app_handle = app.clone();
    let mut dialog = app
        .dialog()
        .message("此操作将删除所有消息记录并重启监听服务，数据不可恢复。")
        .title("清空数据库")
        .kind(MessageDialogKind::Warning)
        .buttons(MessageDialogButtons::OkCancelCustom(
            "清空并重启".into(),
            "取消".into(),
        ));

    if let Some(window) = app.get_webview_window("main") {
        dialog = dialog.parent(&window);
    }

    dialog.show(move |confirmed| {
        if !confirmed {
            return;
        }

        let app = app_handle.clone();
        tauri::async_runtime::spawn(async move {
            let db = app.state::<Arc<MessageDb>>().inner().clone();
            let manager = app.state::<TaskManager>().inner().clone();
            if let Err(error) = commands::db::clear_restart(app.clone(), db, manager).await {
                let mut error_dialog = app
                    .dialog()
                    .message(format!("清空失败: {error}"))
                    .title("清空数据库失败")
                    .kind(MessageDialogKind::Error)
                    .buttons(MessageDialogButtons::Ok);
                if let Some(window) = app.get_webview_window("main") {
                    error_dialog = error_dialog.parent(&window);
                }
                error_dialog.show(|_| {});
            }
        });
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let adapter = Arc::new(MacOSAdapter::new());
    let event_store = Arc::new(EventStore::new());
    let close_to_tray = CloseToTray(Arc::new(AtomicBool::new(true)));

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .manage(adapter.clone())
        .manage(event_store.clone())
        .manage(close_to_tray)
        .setup(move |app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);

            let data_dir = app.path().app_data_dir().unwrap_or_else(|_| {
                std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."))
            });
            let startup_config = load_app_config(&data_dir).ok();

            #[cfg(target_os = "macos")]
            let translate_enabled_check = {
                let (app_menu, toggle) = build_macos_app_menu(
                    app,
                    startup_config
                        .as_ref()
                        .map(|config| config.translate.enabled)
                        .unwrap_or_default(),
                )?;
                let _ = app.set_menu(app_menu)?;
                Some(toggle)
            };

            #[cfg(not(target_os = "macos"))]
            let translate_enabled_check = None;

            let db_path = data_dir.join("messages.db");
            let message_db =
                Arc::new(MessageDb::new(&db_path).expect("failed to open message database"));

            let dict_db_path = data_dir.join("dictionary.db");
            let dict_db = Arc::new(
                dictionary::DictionaryDb::open(&dict_db_path)
                    .expect("failed to open dictionary database"),
            );

            // 初始化词典路由器
            let cambridge_db_path = app
                .path()
                .resolve("dictionaries/cambridge.sqlite", tauri::path::BaseDirectory::Resource)
                .ok();
            let dict_router = Arc::new(
                dictionary::DictionaryRouter::new(cambridge_db_path)
                    .expect("failed to create dictionary router"),
            );

            // 初始化音频缓存管理器
            let audio_cache = Arc::new(
                audio_cache::AudioCache::new(&data_dir)
                    .expect("failed to create audio cache"),
            );

            let image_cache = Arc::new(std::sync::Mutex::new(WeChatImageCache::new()));
            let translation_service = Arc::new(TranslationService::new());

            let manager = TaskManager::new(
                adapter.clone(),
                event_store.clone(),
                message_db.clone(),
                image_cache.clone(),
                translation_service.clone(),
            );
            let sidebar_state = sidebar_window::create_state();

            app.manage(ConfigDir(data_dir.clone()));
            app.manage(message_db);
            app.manage(dict_db);
            app.manage(dict_router);
            app.manage(audio_cache);
            app.manage(image_cache);
            app.manage(translation_service);
            app.manage(manager.clone());
            app.manage(sidebar_state);

            #[cfg(debug_assertions)]
            open_main_window_devtools(app);

            let handle = app.handle().clone();
            let startup_config_for_runtime = startup_config.clone();
            tauri::async_runtime::spawn(async move {
                manager.set_app_handle(handle).await;
                if let Some(config) = startup_config_for_runtime {
                    manager
                        .set_use_right_panel_details(config.listen.use_right_panel_details)
                        .await;
                    manager.apply_runtime_config(&config).await;
                    let _ = manager
                        .start_monitoring(config.listen.interval_seconds)
                        .await;
                } else {
                    let _ = manager.start_monitoring(1.0).await;
                }
            });

            // -- Tray menu items --
            let title_item = MenuItemBuilder::with_id("title", "WeChat PC Auto")
                .enabled(false)
                .build(app)?;

            let sidebar_status = MenuItemBuilder::with_id("sidebar_status", "○ 浮窗未运行")
                .enabled(false)
                .build(app)?;
            let listen_status = MenuItemBuilder::with_id("listen_status", "○ 监听未运行")
                .enabled(false)
                .build(app)?;
            let translate_status = MenuItemBuilder::with_id("translate_status", "○ 翻译未启用")
                .enabled(false)
                .build(app)?;

            let sidebar_toggle =
                MenuItemBuilder::with_id("toggle_sidebar", "开启实时浮窗").build(app)?;
            let listen_toggle = MenuItemBuilder::with_id("toggle_listen", "开启监听").build(app)?;
            let translate_toggle = CheckMenuItemBuilder::with_id(
                "tray_toggle_translate",
                "启用翻译服务",
            )
            .checked(
                startup_config
                    .as_ref()
                    .map(|c| c.translate.enabled)
                    .unwrap_or(false),
            )
            .build(app)?;

            let show_item = MenuItemBuilder::with_id("show", "设置").build(app)?;
            let ghost_mode_toggle =
                CheckMenuItemBuilder::with_id("toggle_ghost_mode", "浮窗隐身模式")
                    .checked(
                        startup_config
                            .as_ref()
                            .map(|c| c.display.ghost_mode)
                            .unwrap_or(false),
                    )
                    .build(app)?;
            let close_to_tray_check =
                CheckMenuItemBuilder::with_id("toggle_close_to_tray", "关闭时最小化到托盘")
                    .checked(true)
                    .build(app)?;
            let quit_item = MenuItemBuilder::with_id("quit", "退出").build(app)?;

            let menu = MenuBuilder::new(app)
                .item(&title_item)
                .separator()
                .item(&sidebar_status)
                .item(&listen_status)
                .item(&translate_status)
                .separator()
                .item(&sidebar_toggle)
                .item(&listen_toggle)
                .item(&translate_toggle)
                .separator()
                .item(&show_item)
                .item(&ghost_mode_toggle)
                .item(&close_to_tray_check)
                .separator()
                .item(&quit_item)
                .build()?;

            app.manage(TrayMenuState {
                translate_enabled_check,
                sidebar_status,
                listen_status,
                translate_status,
                sidebar_toggle,
                listen_toggle,
                translate_toggle,
                ghost_mode_toggle,
                close_to_tray_check,
            });

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .tooltip("WeChat PC Auto")
                .on_menu_event(|app, event| match event.id().as_ref() {
                    #[cfg(debug_assertions)]
                    "open_devtools" => {
                        if let Some(window) = app.get_webview_window("main") {
                            window.open_devtools();
                        }
                    }
                    #[cfg(debug_assertions)]
                    "open_sidebar_devtools" => {
                        if let Some(window) = app.get_webview_window("sidebar") {
                            window.open_devtools();
                        }
                    }
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                        #[cfg(debug_assertions)]
                        open_main_window_devtools(app);
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    "toggle_sidebar" => {
                        let app = app.clone();
                        tauri::async_runtime::spawn(async move {
                            let manager = app.state::<TaskManager>();
                            let state = manager.get_task_state();
                            if state.sidebar {
                                let _ = manager.disable_sidebar().await;
                                let sidebar_ws =
                                    app.state::<Arc<sidebar_window::SidebarWindowState>>();
                                let _ = sidebar_ws.close(&app).await;
                            } else {
                                let config_dir = app.state::<ConfigDir>();
                                let config = load_app_config(&config_dir.0).unwrap_or_default();
                                if !state.monitoring {
                                    let _ = manager
                                        .start_monitoring(config.listen.interval_seconds)
                                        .await;
                                }
                                let _ = manager
                                    .enable_sidebar(
                                        vec![],
                                        config.translate.enabled,
                                        config.translate.provider.clone(),
                                        config.translate.deeplx_url.clone(),
                                        config.translate.ai_provider_id.clone(),
                                        config.translate.ai_model_id.clone(),
                                        config.translate.ai_api_key.clone(),
                                        config.translate.ai_base_url.clone(),
                                        config.translate.source_lang.clone(),
                                        config.translate.target_lang.clone(),
                                        config.translate.timeout_seconds,
                                        config.translate.max_concurrency,
                                        config.translate.max_requests_per_second,
                                        false,
                                    )
                                    .await;
                                let sidebar_ws =
                                    app.state::<Arc<sidebar_window::SidebarWindowState>>();
                                let _ = sidebar_ws
                                    .open(
                                        &app,
                                        Some(config.display.width as f64),
                                        sidebar_window::WindowMode::default(),
                                        Some(config.display.collapsed_display_count),
                                        Some(config.display.ghost_mode),
                                        Some(config.display.sidebar_appearance.clone()),
                                    )
                                    .await;
                            }
                        });
                    }
                    "toggle_listen" => {
                        let app = app.clone();
                        tauri::async_runtime::spawn(async move {
                            let manager = app.state::<TaskManager>();
                            let state = manager.get_task_state();
                            if state.monitoring {
                                let _ = manager.stop_monitoring().await;
                            } else {
                                let config_dir = app.state::<ConfigDir>();
                                let config = load_app_config(&config_dir.0).unwrap_or_default();
                                let _ = manager
                                    .start_monitoring(config.listen.interval_seconds)
                                    .await;
                            }
                        });
                    }
                    "toggle_translate_enabled" => {
                        handle_toggle_translate_enabled_menu(app);
                    }
                    "tray_toggle_translate" => {
                        handle_tray_toggle_translate(app);
                    }
                    "toggle_ghost_mode" => {
                        let tray = app.state::<TrayMenuState>();
                        let ghost_enabled = tray.ghost_mode_toggle.is_checked().unwrap_or(false);
                        if let Some(sidebar) = app.get_webview_window("sidebar") {
                            let _ = sidebar.set_ignore_cursor_events(ghost_enabled);
                        }
                    }
                    "toggle_close_to_tray" => {
                        let close = app.state::<CloseToTray>();
                        let manager = app.state::<TaskManager>();
                        let tray = app.state::<TrayMenuState>();
                        let checked = tray.close_to_tray_check.is_checked().unwrap_or(true);
                        close.0.store(checked, Ordering::Relaxed);
                        app_state::emit_runtime_updated(app, &manager);
                    }
                    "clear_db_restart" => {
                        handle_clear_db_restart_menu(app);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let tauri::tray::TrayIconEvent::DoubleClick { .. } = event {
                        if let Some(window) = tray.app_handle().get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                        #[cfg(debug_assertions)]
                        open_main_window_devtools(tray.app_handle());
                    }
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "main" {
                    let close_to_tray = window.state::<CloseToTray>();
                    if close_to_tray.0.load(Ordering::Relaxed) {
                        let _ = window.hide();
                        api.prevent_close();
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::app_state::app_state_get,
            commands::app_state::settings_update,
            commands::sessions::get_sessions,
            commands::listen::listen_start,
            commands::listen::listen_stop,
            commands::listen::get_task_status,
            commands::listen::health_check,
            commands::sidebar::sidebar_start,
            commands::sidebar::sidebar_stop,
            commands::sidebar::live_start,
            commands::sidebar::sidebar_window_open,
            commands::sidebar::sidebar_window_close,
            commands::sidebar::sidebar_snapshot_get,
            commands::sidebar::translate_test,
            commands::sidebar::translate_sidebar_message,
            commands::config::config_get,
            commands::config::config_put,
            commands::config::config_default,
            commands::db::db_clear_restart,
            commands::db::db_query_messages,
            commands::db::db_get_chats,
            commands::db::db_get_stats,
            commands::tray::get_close_to_tray,
            commands::tray::set_close_to_tray,
            commands::preflight::preflight_check,
            commands::preflight::accessibility_request_access,
            commands::preflight::accessibility_open_settings,
            commands::dictionary::word_lookup,
            commands::dictionary::list_dict_providers,
            commands::dictionary::get_dict_provider,
            commands::dictionary::translate_cached,
            commands::dictionary::translate_batch,
            commands::dictionary::toggle_favorite,
            commands::dictionary::is_word_favorited,
            commands::dictionary::get_favorites_batch,
            commands::dictionary::list_favorites,
            commands::dictionary::update_favorite_note,
            commands::dictionary::record_review,
            commands::dictionary::count_favorites,
            commands::dictionary::get_words_for_review,
            commands::dictionary::start_review_session,
            commands::dictionary::record_review_feedback,
            commands::dictionary::finish_review_session,
            commands::dictionary::get_review_stats,
            commands::audio::audio_get_url,
            commands::audio::audio_is_cached,
            commands::audio::audio_get_stats,
            commands::audio::audio_clear_cache,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
