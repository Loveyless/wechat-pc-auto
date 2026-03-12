pub mod applescript;
pub mod ax_reader;

use anyhow::Result;
use std::sync::atomic::{AtomicBool, Ordering};

pub struct MacOSAdapter {
    ui_paused: AtomicBool,
}

impl MacOSAdapter {
    pub fn new() -> Self {
        Self {
            ui_paused: AtomicBool::new(false),
        }
    }

    pub fn is_ui_paused(&self) -> bool {
        self.ui_paused.load(Ordering::SeqCst)
    }

    pub fn is_supported(&self) -> bool {
        cfg!(target_os = "macos")
    }

    pub fn support_reason(&self) -> String {
        if self.is_supported() {
            "ok".to_string()
        } else {
            "当前不是 macOS 环境".to_string()
        }
    }

    fn ensure_supported(&self) -> Result<()> {
        if !self.is_supported() {
            anyhow::bail!("{}", self.support_reason());
        }
        Ok(())
    }

    pub fn get_current_sessions(&self) -> Result<Vec<String>> {
        self.ensure_supported()?;
        ax_reader::get_current_sessions()
    }

    pub fn read_latest_message(&self) -> Result<String> {
        self.ensure_supported()?;
        ax_reader::read_latest_message()
    }

    pub fn read_active_chat_name(&self) -> Result<String> {
        self.ensure_supported()?;
        ax_reader::read_active_chat_name()
    }

    pub fn read_active_chat_member_count(&self) -> Result<Option<u32>> {
        self.ensure_supported()?;
        ax_reader::read_active_chat_member_count()
    }

    pub fn read_chat_messages_rich(&self) -> Result<Vec<ax_reader::ChatMessage>> {
        self.ensure_supported()?;
        ax_reader::read_chat_messages_rich()
    }

    pub fn read_session_snapshots(&self) -> Result<Vec<ax_reader::SessionItemSnapshot>> {
        self.ensure_supported()?;
        ax_reader::read_session_snapshots()
    }

    pub fn read_session_preview_for_chat(&self, chat_name: &str) -> Result<Option<String>> {
        self.ensure_supported()?;
        ax_reader::read_session_preview_for_chat(chat_name)
    }

    pub fn has_popup_or_menu(&self) -> bool {
        self.is_supported() && ax_reader::has_popup_or_menu()
    }
}
