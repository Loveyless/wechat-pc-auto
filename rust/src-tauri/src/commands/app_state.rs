use crate::app_state;
use crate::config::{self as app_config, ConfigDir};
use crate::task_manager::TaskManager;
use crate::CloseToTray;

pub async fn save_settings(
    app: &tauri::AppHandle,
    config_dir: &ConfigDir,
    manager: &TaskManager,
    close_to_tray: &CloseToTray,
    settings: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let (errors, path) = app_config::validate_and_write_config(&config_dir.0, &settings)
        .map_err(|error| error.to_string())?;

    if !errors.is_empty() {
        return Ok(serde_json::json!({ "ok": false, "errors": errors }));
    }

    let settings = app_config::load_app_config(&config_dir.0).map_err(|error| error.to_string())?;
    manager.apply_runtime_config(&settings).await;
    app_state::emit_settings_updated(app, &settings);
    app_state::emit_runtime_updated(app, manager);

    let snapshot = app_state::snapshot(settings, manager, close_to_tray).await;
    Ok(serde_json::json!({
        "ok": true,
        "message": "settings saved",
        "path": path,
        "data": snapshot,
    }))
}

#[tauri::command]
pub async fn app_state_get(
    config_dir: tauri::State<'_, ConfigDir>,
    manager: tauri::State<'_, TaskManager>,
    close_to_tray: tauri::State<'_, CloseToTray>,
) -> Result<serde_json::Value, String> {
    let snapshot = app_state::load_snapshot(&config_dir, &manager, &close_to_tray).await?;
    Ok(serde_json::json!({ "ok": true, "data": snapshot }))
}

#[tauri::command]
pub async fn settings_update(
    app: tauri::AppHandle,
    config_dir: tauri::State<'_, ConfigDir>,
    manager: tauri::State<'_, TaskManager>,
    close_to_tray: tauri::State<'_, CloseToTray>,
    settings: serde_json::Value,
) -> Result<serde_json::Value, String> {
    save_settings(&app, &config_dir, &manager, &close_to_tray, settings).await
}
