#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod backend_health;

use tauri::{Manager, Runtime};

use crate::backend::{
    bootstrap_backend, get_backend_connection_info, log_single_instance_event, ManagedBackendState,
};

fn focus_existing_window<R: Runtime>(app: &tauri::AppHandle<R>) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            log_single_instance_event(
                app,
                "single-instance relaunch detected, focus existing window",
            );
            focus_existing_window(app);
        }))
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let backend_state = bootstrap_backend(app);
            app.manage(backend_state);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_backend_connection_info])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                let state = app_handle.state::<ManagedBackendState>();
                state.kill_owned_child();
            }
        });
}
