use crate::config::{load_app_config, ConfigDir};
use crate::task_manager::TaskManager;

#[tauri::command]
pub async fn listen_start(
    config_dir: tauri::State<'_, ConfigDir>,
    manager: tauri::State<'_, TaskManager>,
    interval_seconds: Option<f64>,
) -> Result<serde_json::Value, String> {
    let config = load_app_config(&config_dir.0).map_err(|e| e.to_string())?;
    manager
        .set_use_right_panel_details(config.listen.use_right_panel_details)
        .await;
    let interval = interval_seconds.unwrap_or(1.0);
    manager
        .start_monitoring(interval)
        .await
        .map_err(|e| e.to_string())?;

    Ok(serde_json::json!({ "ok": true, "message": "monitoring started" }))
}

#[tauri::command]
pub async fn listen_stop(
    manager: tauri::State<'_, TaskManager>,
) -> Result<serde_json::Value, String> {
    manager.stop_monitoring().await.map_err(|e| e.to_string())?;
    Ok(serde_json::json!({ "ok": true, "message": "monitoring stopped" }))
}

#[tauri::command]
pub async fn get_task_status(
    manager: tauri::State<'_, TaskManager>,
) -> Result<serde_json::Value, String> {
    let status = manager.service_status().await;
    Ok(serde_json::json!({ "ok": true, "data": status }))
}

#[tauri::command]
pub async fn health_check(
    manager: tauri::State<'_, TaskManager>,
) -> Result<serde_json::Value, String> {
    let status = manager.service_status().await;
    Ok(serde_json::json!({ "status": "ok", "service_status": status }))
}
