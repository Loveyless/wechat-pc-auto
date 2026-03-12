use crate::app_state;
use crate::config::{self as app_config, ConfigDir};
use crate::task_manager::TaskManager;
use tauri::Emitter;

#[tauri::command]
pub async fn config_get(
    config_dir: tauri::State<'_, ConfigDir>,
) -> Result<serde_json::Value, String> {
    let config = app_config::read_config(&config_dir.0).map_err(|e| e.to_string())?;
    Ok(serde_json::json!({ "ok": true, "data": config }))
}

#[tauri::command]
pub async fn config_put(
    app: tauri::AppHandle,
    config_dir: tauri::State<'_, ConfigDir>,
    manager: tauri::State<'_, TaskManager>,
    config: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let (errors, path) =
        app_config::validate_and_write_config(&config_dir.0, &config).map_err(|e| e.to_string())?;

    if !errors.is_empty() {
        return Ok(serde_json::json!({ "ok": false, "errors": errors }));
    }

    let app_config = app_config::load_app_config(&config_dir.0).map_err(|e| e.to_string())?;
    manager.apply_runtime_config(&app_config).await;
    app_state::emit_settings_updated(&app, &app_config);
    app_state::emit_runtime_updated(&app, &manager);
    let _ = app.emit(
        "config-updated",
        serde_json::to_value(&app_config).unwrap_or_default(),
    );

    Ok(serde_json::json!({ "ok": true, "message": "config saved", "path": path }))
}

#[tauri::command]
pub async fn config_default() -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({ "ok": true, "data": app_config::default_config_value() }))
}
