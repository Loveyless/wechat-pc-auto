use anyhow::Result;
use base64::Engine;
use serde::Deserialize;
use std::sync::Arc;

use crate::config::SidebarAppearance;
use std::time::Instant;
use tauri::webview::WebviewWindowBuilder;
use tauri::{AppHandle, Emitter, LogicalPosition, LogicalSize, Manager, WebviewUrl};
use tokio::sync::Mutex;
use tokio_util::sync::CancellationToken;

use crate::adapter::applescript::{
    get_wechat_window_frame, is_wechat_frontmost, query_wechat_window,
};

const DEFAULT_WIDTH: f64 = 380.0;
const DEFAULT_INDEPENDENT_HEIGHT: f64 = 600.0;
const INDEPENDENT_MARGIN: f64 = 20.0;

const TITLE_BAR_H: f64 = 40.0;
const MSG_CARD_H: f64 = 62.0;
const MSG_GAP: f64 = 6.0;
const CONTAINER_PAD: f64 = 12.0;

fn calc_collapsed_height(count: u32) -> f64 {
    if count == 0 {
        return TITLE_BAR_H;
    }
    TITLE_BAR_H + CONTAINER_PAD + (count as f64) * MSG_CARD_H + ((count - 1) as f64) * MSG_GAP
}
const SIDEBAR_LABEL: &str = "sidebar";
const POLL_INTERVAL_MS: u64 = 300;
const ANIMATION_DURATION_MS: u64 = 350;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WindowMode {
    Follow,
    Independent,
}

impl Default for WindowMode {
    fn default() -> Self {
        Self::Follow
    }
}

impl WindowMode {
    pub fn from_str_opt(s: Option<&str>) -> Self {
        match s.map(|v| v.trim().to_lowercase()).as_deref() {
            Some("independent") => Self::Independent,
            _ => Self::Follow,
        }
    }
}

enum SidebarVisibility {
    Visible,
    AnimatingOut(Instant),
    Hidden,
}

pub struct SidebarWindowState {
    cancel: Mutex<Option<CancellationToken>>,
}

impl SidebarWindowState {
    pub fn new() -> Self {
        Self {
            cancel: Mutex::new(None),
        }
    }

    pub async fn open(
        &self,
        app: &AppHandle,
        width: Option<f64>,
        mode: WindowMode,
        collapsed_display_count: Option<u32>,
        ghost_mode: Option<bool>,
        appearance: Option<SidebarAppearance>,
    ) -> Result<()> {
        let width = width.unwrap_or(DEFAULT_WIDTH);
        let count = collapsed_display_count.unwrap_or(3).max(1);
        let ghost = ghost_mode.unwrap_or(false);
        let appearance = appearance.unwrap_or_default();

        if let Some(existing) = app.webview_windows().get(SIDEBAR_LABEL) {
            existing.set_focus().ok();
            return Ok(());
        }

        let (pos_x, pos_y, win_height) = match mode {
            WindowMode::Follow => {
                let (wx, wy, ww, wh) =
                    get_wechat_window_frame().unwrap_or((100.0, 100.0, 800.0, 600.0));
                (wx + ww, wy, wh)
            }
            WindowMode::Independent => {
                let (screen_w, _screen_h) = get_screen_size(app);
                let x = screen_w - width - INDEPENDENT_MARGIN;
                let y = INDEPENDENT_MARGIN;
                let h = calc_collapsed_height(count);
                (x, y, h)
            }
        };

        let appearance_json = serde_json::to_string(&appearance).unwrap_or_default();
        let appearance_b64 = base64::engine::general_purpose::STANDARD.encode(&appearance_json);
        
        let url_query = match mode {
            WindowMode::Follow => format!("index.html?view=sidebar&mode=follow&appearance={}", appearance_b64),
            WindowMode::Independent => format!("index.html?view=sidebar&mode=independent&count={}&ghost={}&appearance={}", count, ghost, appearance_b64),
        };

        let win = WebviewWindowBuilder::new(app, SIDEBAR_LABEL, WebviewUrl::App(url_query.into()))
            .title("Sidebar")
            .inner_size(width, win_height)
            .position(pos_x, pos_y)
            .always_on_top(true)
            .decorations(false)
            .skip_taskbar(true)
            .transparent(true)
            .shadow(true)
            .build()?;

        // 开发模式下自动打开开发者工具
        #[cfg(debug_assertions)]
        win.open_devtools();

        if ghost && mode == WindowMode::Independent {
            win.set_ignore_cursor_events(true).ok();
        }

        let token = CancellationToken::new();
        {
            let mut guard = self.cancel.lock().await;
            if let Some(old) = guard.take() {
                old.cancel();
            }
            *guard = Some(token.clone());
        }

        if mode == WindowMode::Follow {
            let app_handle = app.clone();
            tokio::spawn(position_tracker(app_handle, token, width));
        }

        Ok(())
    }

    pub async fn close(&self, app: &AppHandle) -> Result<()> {
        {
            let mut guard = self.cancel.lock().await;
            if let Some(token) = guard.take() {
                token.cancel();
            }
        }
        if let Some(win) = app.webview_windows().get(SIDEBAR_LABEL) {
            win.close()?;
        }
        Ok(())
    }
}

fn get_screen_size(app: &AppHandle) -> (f64, f64) {
    if let Some(monitor) = app.primary_monitor().ok().flatten() {
        let size = monitor.size();
        let scale = monitor.scale_factor();
        (size.width as f64 / scale, size.height as f64 / scale)
    } else {
        (1920.0, 1080.0)
    }
}

async fn position_tracker(app: AppHandle, token: CancellationToken, width: f64) {
    let mut last_frame: Option<(f64, f64, f64, f64)> = None;
    let mut state = SidebarVisibility::Visible;
    let mut last_on_top = true;

    loop {
        if token.is_cancelled() {
            break;
        }

        let win = match app.webview_windows().get(SIDEBAR_LABEL) {
            Some(w) => w.clone(),
            None => break,
        };

        let result = tokio::task::spawn_blocking(query_wechat_window).await;

        match result {
            Ok(Ok(Some((wx, wy, ww, wh)))) => {
                match state {
                    SidebarVisibility::Hidden => {
                        log::debug!("WeChat restored, showing sidebar");
                        win.show().ok();
                        win.set_always_on_top(true).ok();
                        last_on_top = true;
                        win.set_focus().ok();
                        win.emit("sidebar-visibility", true).ok();
                        state = SidebarVisibility::Visible;
                    }
                    SidebarVisibility::AnimatingOut(_) => {
                        log::debug!("WeChat back during exit animation, cancelling hide");
                        win.emit("sidebar-visibility", true).ok();
                        state = SidebarVisibility::Visible;
                    }
                    SidebarVisibility::Visible => {}
                }

                let new_frame = (wx, wy, ww, wh);
                let changed = last_frame.map_or(true, |old| {
                    (old.0 - new_frame.0).abs() > 0.5
                        || (old.1 - new_frame.1).abs() > 0.5
                        || (old.2 - new_frame.2).abs() > 0.5
                        || (old.3 - new_frame.3).abs() > 0.5
                });

                if changed {
                    win.set_position(LogicalPosition::new(wx + ww, wy)).ok();
                    win.set_size(LogicalSize::new(width, wh)).ok();
                    last_frame = Some(new_frame);
                }

                let frontmost = is_wechat_frontmost();
                if frontmost != last_on_top {
                    win.set_always_on_top(frontmost).ok();
                    last_on_top = frontmost;
                }
            }
            _ => {
                match state {
                    SidebarVisibility::Visible => {
                        log::debug!("WeChat not visible, starting exit animation");
                        win.emit("sidebar-visibility", false).ok();
                        state = SidebarVisibility::AnimatingOut(Instant::now());
                    }
                    SidebarVisibility::AnimatingOut(t) => {
                        if t.elapsed() >= std::time::Duration::from_millis(ANIMATION_DURATION_MS) {
                            log::debug!("Exit animation done, hiding sidebar window");
                            win.hide().ok();
                            state = SidebarVisibility::Hidden;
                        }
                    }
                    SidebarVisibility::Hidden => {}
                }
                last_frame = None;
            }
        }

        tokio::select! {
            _ = token.cancelled() => break,
            _ = tokio::time::sleep(std::time::Duration::from_millis(POLL_INTERVAL_MS)) => {}
        }
    }
}

pub fn create_state() -> Arc<SidebarWindowState> {
    Arc::new(SidebarWindowState::new())
}
