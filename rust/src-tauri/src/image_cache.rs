use anyhow::Result;
use log::{debug, warn};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::time::SystemTime;

pub struct WeChatImageCache {
    /// ~/Library/Containers/com.tencent.xinWeChat/.../xwechat_files/{wxid}/cache
    cache_base: Option<PathBuf>,
    /// Learned chat_name -> session_hash mapping
    session_map: HashMap<String, String>,
}

impl WeChatImageCache {
    pub fn new() -> Self {
        let cache_base = Self::discover_cache_base();
        if let Some(ref base) = cache_base {
            debug!("WeChatImageCache: cache_base = {}", base.display());
        } else {
            warn!("WeChatImageCache: could not find WeChat cache directory");
        }
        Self {
            cache_base,
            session_map: HashMap::new(),
        }
    }

    fn discover_cache_base() -> Option<PathBuf> {
        let home = dirs_next().ok()?;
        let container =
            home.join("Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files");
        if !container.is_dir() {
            return None;
        }

        // Find most recently modified wxid_* directory
        let mut best: Option<(PathBuf, SystemTime)> = None;
        if let Ok(entries) = std::fs::read_dir(&container) {
            for entry in entries.flatten() {
                let name = entry.file_name();
                let name_str = name.to_string_lossy();
                if !name_str.starts_with("wxid_") && !name_str.starts_with("wx_") {
                    // Also try any directory that looks like a user directory
                    if name_str.len() < 10 {
                        continue;
                    }
                }
                let path = entry.path();
                let cache_dir = path.join("cache");
                if cache_dir.is_dir() {
                    if let Ok(meta) = std::fs::metadata(&cache_dir) {
                        if let Ok(modified) = meta.modified() {
                            if best.as_ref().map_or(true, |(_, t)| modified > *t) {
                                best = Some((cache_dir, modified));
                            }
                        }
                    }
                }
            }
        }

        best.map(|(p, _)| p)
    }

    /// Find an image thumbnail that matches a [图片] message timestamp.
    /// Returns the file path if found.
    pub fn find_image_for_message(
        &mut self,
        chat_name: &str,
        message_timestamp: i64,
    ) -> Option<PathBuf> {
        let cache_base = self.cache_base.as_ref()?;

        let now = chrono::Local::now();
        let current_month = now.format("%Y-%m").to_string();

        // Also check previous month in case we're near the month boundary
        let prev_month = {
            let prev = now - chrono::Duration::days(5);
            prev.format("%Y-%m").to_string()
        };

        let months = if current_month == prev_month {
            vec![current_month]
        } else {
            vec![current_month, prev_month]
        };

        // If we have a known session hash for this chat, search there first
        if let Some(hash) = self.session_map.get(chat_name).cloned() {
            for month in &months {
                let thumb_dir = cache_base
                    .join(month)
                    .join("Message")
                    .join(&hash)
                    .join("Thumb");
                if let Some(path) = Self::find_closest_thumb(&thumb_dir, message_timestamp) {
                    return Some(path);
                }
            }
        }

        // No mapping yet — scan all session directories
        for month in &months {
            let msg_dir = cache_base.join(month).join("Message");
            if !msg_dir.is_dir() {
                continue;
            }
            if let Ok(entries) = std::fs::read_dir(&msg_dir) {
                for entry in entries.flatten() {
                    let hash = entry.file_name().to_string_lossy().to_string();
                    let thumb_dir = entry.path().join("Thumb");
                    if let Some(path) = Self::find_closest_thumb(&thumb_dir, message_timestamp) {
                        // Learn the mapping
                        debug!(
                            "WeChatImageCache: learned mapping {} -> {}",
                            chat_name, hash
                        );
                        self.session_map.insert(chat_name.to_string(), hash);
                        return Some(path);
                    }
                }
            }
        }

        None
    }

    /// Find the thumb file whose timestamp is closest to message_timestamp
    /// and within a 10-second window.
    fn find_closest_thumb(thumb_dir: &Path, message_timestamp: i64) -> Option<PathBuf> {
        if !thumb_dir.is_dir() {
            return None;
        }

        let entries = std::fs::read_dir(thumb_dir).ok()?;
        let mut best: Option<(PathBuf, i64)> = None;

        for entry in entries.flatten() {
            let name = entry.file_name();
            let name_str = name.to_string_lossy();

            // Pattern: {msg_seq}_{unix_timestamp}_thumb.jpg
            // or {msg_seq}_{unix_timestamp}_thumb.png
            if let Some(ts) = Self::extract_timestamp(&name_str) {
                let diff = (ts - message_timestamp).abs();
                if diff <= 10 {
                    if best.as_ref().map_or(true, |(_, d)| diff < *d) {
                        best = Some((entry.path(), diff));
                    }
                }
            }
        }

        best.map(|(p, _)| p)
    }

    /// Extract Unix timestamp from filename like "12345_1709712345_thumb.jpg"
    fn extract_timestamp(filename: &str) -> Option<i64> {
        let stem = filename.split('.').next()?;
        let parts: Vec<&str> = stem.split('_').collect();
        if parts.len() >= 2 {
            // Try second part as timestamp
            if let Ok(ts) = parts[1].parse::<i64>() {
                // Sanity check: should be a reasonable Unix timestamp (after 2020)
                if ts > 1_577_836_800 {
                    return Some(ts);
                }
            }
        }
        None
    }
}

fn dirs_next() -> Result<PathBuf> {
    std::env::var("HOME")
        .map(PathBuf::from)
        .map_err(|_| anyhow::anyhow!("HOME not set"))
}

/// Check if the message content is an image placeholder
pub fn is_image_placeholder(text: &str) -> bool {
    let trimmed = text.trim();
    matches!(
        trimmed,
        "[图片]" | "[Image]" | "[Images]" | "[image]" | "[photo]" | "[Photo]"
    )
}
