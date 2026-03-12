use crate::adapter::MacOSAdapter;
use std::sync::Arc;

#[tauri::command]
pub async fn get_sessions(
    adapter: tauri::State<'_, Arc<MacOSAdapter>>,
) -> Result<serde_json::Value, String> {
    let adapter = adapter.inner().clone();
    let sessions = tokio::task::spawn_blocking(move || adapter.get_current_sessions())
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())?;

    Ok(serde_json::json!({ "ok": true, "data": sessions }))
}
