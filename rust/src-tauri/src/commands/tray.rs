use crate::app_state;
use crate::CloseToTray;
use std::sync::atomic::Ordering;
use tauri::{AppHandle, Manager, State};

#[tauri::command]
pub fn get_close_to_tray(state: State<'_, CloseToTray>) -> bool {
    state.0.load(Ordering::Relaxed)
}

#[tauri::command]
pub fn set_close_to_tray(
    app: AppHandle,
    state: State<'_, CloseToTray>,
    manager: State<'_, crate::task_manager::TaskManager>,
    enabled: bool,
) {
    state.0.store(enabled, Ordering::Relaxed);
    if let Some(tray) = app.try_state::<crate::TrayMenuState>() {
        let _ = tray.close_to_tray_check.set_checked(enabled);
    }
    app_state::emit_runtime_updated(&app, &manager);
}
