use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::{Path, PathBuf};

/// Wrapper around the resolved config base directory, registered as Tauri managed state.
pub struct ConfigDir(pub PathBuf);

fn config_path(base: &Path) -> PathBuf {
    base.join("config").join("listener.json")
}

fn ensure_config_dir(base: &Path) {
    let path = config_path(base);
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
}

// ---------------------------------------------------------------------------
// Typed config structs
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListenConfig {
    #[serde(default = "default_mode")]
    pub mode: String,
    #[serde(default)]
    pub targets: Vec<String>,
    #[serde(default = "default_interval")]
    pub interval_seconds: f64,
    #[serde(default = "default_dedupe")]
    pub dedupe_window_seconds: f64,
    #[serde(default = "default_session_preview_dedupe")]
    pub session_preview_dedupe_window_seconds: f64,
    #[serde(default = "default_cross_source_merge")]
    pub cross_source_merge_window_seconds: f64,
    #[serde(default)]
    pub focus_refresh: bool,
    #[serde(default)]
    pub worker_debug: bool,
    #[serde(default)]
    pub use_right_panel_details: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranslateConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_provider")]
    pub provider: String,
    #[serde(default = "default_deeplx_url")]
    pub deeplx_url: String,
    #[serde(default, skip_serializing)]
    pub deeplx_base_url: String,
    #[serde(default, skip_serializing)]
    pub deeplx_access_token: String,
    #[serde(default = "default_source_lang")]
    pub source_lang: String,
    #[serde(default = "default_target_lang")]
    pub target_lang: String,
    #[serde(default = "default_timeout")]
    pub timeout_seconds: f64,
    #[serde(default = "default_max_concurrency")]
    pub max_concurrency: usize,
    #[serde(default = "default_max_requests_per_second")]
    pub max_requests_per_second: usize,
    // AI 翻译相关字段
    #[serde(default)]
    pub ai_provider_id: String,
    #[serde(default)]
    pub ai_model_id: String,
    #[serde(default)]
    pub ai_api_key: String,
    #[serde(default)]
    pub ai_base_url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SidebarAppearance {
    #[serde(default = "default_bg_opacity")]
    pub bg_opacity: f32,
    #[serde(default = "default_blur")]
    pub blur: String,
    #[serde(default = "default_card_style")]
    pub card_style: String,
    #[serde(default = "default_text_enhance")]
    pub text_enhance: String,
}

fn default_bg_opacity() -> f32 {
    0.8
}
fn default_blur() -> String {
    "strong".into()
}
fn default_card_style() -> String {
    "standard".into()
}
fn default_text_enhance() -> String {
    "none".into()
}

impl Default for SidebarAppearance {
    fn default() -> Self {
        Self {
            bg_opacity: default_bg_opacity(),
            blur: default_blur(),
            card_style: default_card_style(),
            text_enhance: default_text_enhance(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DisplayConfig {
    #[serde(default = "default_true")]
    pub english_only: bool,
    #[serde(default = "default_on_translate_fail")]
    pub on_translate_fail: String,
    #[serde(default = "default_width")]
    pub width: u32,
    #[serde(default = "default_side")]
    pub side: String,
    #[serde(default = "default_collapsed_display_count")]
    pub collapsed_display_count: u32,
    #[serde(default)]
    pub ghost_mode: bool,
    #[serde(default)]
    pub sidebar_appearance: SidebarAppearance,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoggingConfig {
    #[serde(default = "default_log_file")]
    pub file: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DictConfig {
    /// 当前使用的词典提供者
    /// 可选值: "cambridge" | "free_dictionary"
    #[serde(default = "default_dict_provider")]
    pub provider: String,
}

fn default_dict_provider() -> String {
    "cambridge".to_string()
}

impl Default for DictConfig {
    fn default() -> Self {
        Self {
            provider: default_dict_provider(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    #[serde(default)]
    pub listen: ListenConfig,
    #[serde(default)]
    pub translate: TranslateConfig,
    #[serde(default)]
    pub display: DisplayConfig,
    #[serde(default)]
    pub logging: LoggingConfig,
    #[serde(default)]
    pub dict: DictConfig,
}

// ---------------------------------------------------------------------------
// Default helpers
// ---------------------------------------------------------------------------

fn default_mode() -> String {
    "session".into()
}
fn default_interval() -> f64 {
    1.0
}
fn default_dedupe() -> f64 {
    2.5
}
fn default_session_preview_dedupe() -> f64 {
    20.0
}
fn default_cross_source_merge() -> f64 {
    3.0
}
fn default_true() -> bool {
    true
}
fn default_provider() -> String {
    "deeplx".into()
}
fn default_deeplx_url() -> String {
    "".into()
}
fn default_source_lang() -> String {
    "auto".into()
}
fn default_target_lang() -> String {
    "EN".into()
}
fn default_timeout() -> f64 {
    8.0
}
fn default_max_concurrency() -> usize {
    3
}
fn default_max_requests_per_second() -> usize {
    3
}
fn default_on_translate_fail() -> String {
    "show_cn_with_reason".into()
}
fn default_width() -> u32 {
    420
}
fn default_side() -> String {
    "right".into()
}
fn default_log_file() -> String {
    "logs/sidebar_listener.log".into()
}
fn default_collapsed_display_count() -> u32 {
    3
}

impl Default for ListenConfig {
    fn default() -> Self {
        Self {
            mode: default_mode(),
            targets: vec![],
            interval_seconds: default_interval(),
            dedupe_window_seconds: default_dedupe(),
            session_preview_dedupe_window_seconds: default_session_preview_dedupe(),
            cross_source_merge_window_seconds: default_cross_source_merge(),
            focus_refresh: false,
            worker_debug: false,
            use_right_panel_details: false,
        }
    }
}

impl Default for TranslateConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            provider: default_provider(),
            deeplx_url: default_deeplx_url(),
            deeplx_base_url: String::new(),
            deeplx_access_token: String::new(),
            source_lang: default_source_lang(),
            target_lang: default_target_lang(),
            timeout_seconds: default_timeout(),
            max_concurrency: default_max_concurrency(),
            max_requests_per_second: default_max_requests_per_second(),
            ai_provider_id: String::new(),
            ai_model_id: String::new(),
            ai_api_key: String::new(),
            ai_base_url: String::new(),
        }
    }
}

impl TranslateConfig {
    fn normalize_legacy(&mut self) {
        if self.deeplx_url.trim().is_empty() {
            let base = self.deeplx_base_url.trim().trim_end_matches('/');
            let token = self.deeplx_access_token.trim();
            if !base.is_empty() {
                self.deeplx_url = if token.is_empty() {
                    format!("{base}/translate")
                } else {
                    format!("{base}/{token}/translate")
                };
            }
        }
        self.deeplx_base_url.clear();
        self.deeplx_access_token.clear();
    }
}

impl Default for DisplayConfig {
    fn default() -> Self {
        Self {
            english_only: true,
            on_translate_fail: default_on_translate_fail(),
            width: default_width(),
            side: default_side(),
            collapsed_display_count: default_collapsed_display_count(),
            ghost_mode: false,
            sidebar_appearance: SidebarAppearance::default(),
        }
    }
}

impl Default for LoggingConfig {
    fn default() -> Self {
        Self {
            file: default_log_file(),
        }
    }
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            listen: ListenConfig::default(),
            translate: TranslateConfig::default(),
            display: DisplayConfig::default(),
            logging: LoggingConfig::default(),
            dict: DictConfig::default(),
        }
    }
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

impl AppConfig {
    fn normalize(&mut self) {
        self.translate.normalize_legacy();
    }

    pub fn validate(&self) -> Vec<String> {
        let mut errors = Vec::new();

        if self.listen.mode != "session" {
            errors.push(format!(
                "listen.mode 只允许 \"session\"，当前值: \"{}\"",
                self.listen.mode
            ));
        }
        if self.listen.interval_seconds < 0.3 {
            errors.push(format!(
                "listen.interval_seconds 不能小于 0.3，当前值: {}",
                self.listen.interval_seconds
            ));
        }
        if self.listen.dedupe_window_seconds <= 0.0 {
            errors.push(format!(
                "listen.dedupe_window_seconds 必须大于 0，当前值: {}",
                self.listen.dedupe_window_seconds
            ));
        }
        if self.listen.session_preview_dedupe_window_seconds <= 0.0 {
            errors.push(format!(
                "listen.session_preview_dedupe_window_seconds 必须大于 0，当前值: {}",
                self.listen.session_preview_dedupe_window_seconds
            ));
        }
        if self.listen.cross_source_merge_window_seconds <= 0.0 {
            errors.push(format!(
                "listen.cross_source_merge_window_seconds 必须大于 0，当前值: {}",
                self.listen.cross_source_merge_window_seconds
            ));
        }

        if self.translate.timeout_seconds < 1.0 {
            errors.push(format!(
                "translate.timeout_seconds 不能小于 1.0，当前值: {}",
                self.translate.timeout_seconds
            ));
        }
        if self.translate.max_concurrency == 0 {
            errors.push("translate.max_concurrency 必须大于 0".to_string());
        }
        if self.translate.max_requests_per_second == 0 {
            errors.push("translate.max_requests_per_second 必须大于 0".to_string());
        }

        if !(200..=1200).contains(&self.display.width) {
            errors.push(format!(
                "display.width 须在 200–1200 之间，当前值: {}",
                self.display.width
            ));
        }
        if self.display.side != "left" && self.display.side != "right" {
            errors.push(format!(
                "display.side 只允许 \"left\" 或 \"right\"，当前值: \"{}\"",
                self.display.side
            ));
        }
        if self.display.on_translate_fail != "show_cn_with_reason"
            && self.display.on_translate_fail != "hide"
        {
            errors.push(format!(
                "display.on_translate_fail 只允许 \"show_cn_with_reason\" 或 \"hide\"，当前值: \"{}\"",
                self.display.on_translate_fail
            ));
        }

        errors
    }
}

// ---------------------------------------------------------------------------
// Read / Write / Default
// ---------------------------------------------------------------------------

/// Read config from disk. Missing fields are filled with defaults.
pub fn load_app_config(base: &Path) -> Result<AppConfig> {
    let path = config_path(base);
    let mut app_config: AppConfig = if path.exists() {
        let content = std::fs::read_to_string(&path)
            .context(format!("cannot read config: {}", path.display()))?;
        serde_json::from_str(&content).context("config JSON parse failed")?
    } else {
        AppConfig::default()
    };
    app_config.normalize();
    Ok(app_config)
}

/// Read config from disk. Missing fields are filled with defaults.
pub fn read_config(base: &Path) -> Result<Value> {
    let app_config = load_app_config(base)?;
    serde_json::to_value(&app_config).context("config serialize failed")
}

/// Validate and write config. Returns list of validation errors (empty = success).
pub fn validate_and_write_config(
    base: &Path,
    raw: &Value,
) -> Result<(Vec<String>, Option<String>)> {
    let mut app_config: AppConfig =
        serde_json::from_value(raw.clone()).context("配置格式不正确，无法解析为有效配置结构")?;
    app_config.normalize();

    let errors = app_config.validate();
    if !errors.is_empty() {
        return Ok((errors, None));
    }

    let canonical = serde_json::to_value(&app_config)?;
    ensure_config_dir(base);
    let path = config_path(base);
    let content = serde_json::to_string_pretty(&canonical)?;
    std::fs::write(&path, content).context(format!("cannot write config: {}", path.display()))?;
    Ok((vec![], Some(path.display().to_string())))
}

/// Returns the default config as JSON Value.
pub fn default_config_value() -> Value {
    serde_json::to_value(AppConfig::default()).unwrap()
}

#[cfg(test)]
mod tests {
    use super::{default_config_value, read_config, validate_and_write_config};
    use serde_json::json;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_base() -> PathBuf {
        let suffix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        let base = std::env::temp_dir().join(format!("wechat-pc-auto-config-{suffix}"));
        let _ = std::fs::create_dir_all(&base);
        base
    }

    #[test]
    fn default_config_should_include_translate_endpoint_fields() {
        let value = default_config_value();
        let translate = value.get("translate").expect("translate section");
        let listen = value.get("listen").expect("listen section");
        assert_eq!(
            translate.get("deeplx_url").and_then(|v| v.as_str()),
            Some("")
        );
        assert_eq!(
            translate.get("max_concurrency").and_then(|v| v.as_u64()),
            Some(3)
        );
        assert_eq!(
            translate
                .get("max_requests_per_second")
                .and_then(|v| v.as_u64()),
            Some(3)
        );
        assert_eq!(translate.get("deeplx_base_url"), None);
        assert_eq!(
            listen
                .get("use_right_panel_details")
                .and_then(|v| v.as_bool()),
            Some(false)
        );
    }

    #[test]
    fn validate_and_write_config_should_persist_translate_endpoint_fields() {
        let base = temp_base();
        let raw = json!({
            "listen": { "mode": "session", "interval_seconds": 1.0 },
            "translate": {
                "enabled": true,
                "provider": "deeplx",
                "deeplx_url": "https://api.deeplx.org/Pte_wVKtHoepysL2Q94Mq2LEZHE2Vnnl02tG-IogwGM/translate",
                "source_lang": "auto",
                "target_lang": "EN",
                "timeout_seconds": 8.0,
                "max_concurrency": 4,
                "max_requests_per_second": 5
            },
            "display": { "english_only": true, "on_translate_fail": "show_cn_with_reason", "width": 420, "side": "right" },
            "logging": { "file": "logs/sidebar_listener.log" }
        });

        let (errors, _) = validate_and_write_config(&base, &raw).expect("write config");
        assert!(errors.is_empty());

        let saved = read_config(&base).expect("read config");
        let translate = saved.get("translate").expect("translate section");
        assert_eq!(
            translate.get("deeplx_url").and_then(|v| v.as_str()),
            Some("https://api.deeplx.org/Pte_wVKtHoepysL2Q94Mq2LEZHE2Vnnl02tG-IogwGM/translate")
        );
        assert_eq!(
            translate.get("max_concurrency").and_then(|v| v.as_u64()),
            Some(4)
        );
        assert_eq!(
            translate
                .get("max_requests_per_second")
                .and_then(|v| v.as_u64()),
            Some(5)
        );
        assert_eq!(translate.get("deeplx_base_url"), None);
        assert_eq!(
            saved["listen"]["use_right_panel_details"].as_bool(),
            Some(false)
        );
    }

    #[test]
    fn validate_and_write_config_should_persist_right_panel_toggle() {
        let base = temp_base();
        let raw = json!({
            "listen": {
                "mode": "session",
                "interval_seconds": 1.0,
                "use_right_panel_details": true
            },
            "translate": {
                "enabled": false,
                "provider": "deeplx",
                "deeplx_url": "",
                "source_lang": "auto",
                "target_lang": "EN",
                "timeout_seconds": 8.0
            },
            "display": { "english_only": true, "on_translate_fail": "show_cn_with_reason", "width": 420, "side": "right" },
            "logging": { "file": "logs/sidebar_listener.log" }
        });

        let (errors, _) = validate_and_write_config(&base, &raw).expect("write config");
        assert!(errors.is_empty());

        let saved = read_config(&base).expect("read config");
        assert_eq!(
            saved["listen"]["use_right_panel_details"].as_bool(),
            Some(true)
        );
    }
}
