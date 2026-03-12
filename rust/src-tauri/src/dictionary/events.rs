use serde::Serialize;

/// 单个字段翻译完成事件
#[derive(Debug, Clone, Serialize)]
pub struct FieldTranslatedEvent {
    pub word: String,
    pub field: String, // "summary_zh" | "def_{m}_{d}" | "ex_{m}_{d}"
}

/// 整体翻译完成事件
#[derive(Debug, Clone, Serialize)]
pub struct TranslationDoneEvent {
    pub word: String,
    pub total: u32,
    pub translated: u32,
    pub success: bool,
}

/// 事件名称常量
pub const EVENT_FIELD_TRANSLATED: &str = "dictionary:field_translated";
pub const EVENT_TRANSLATION_DONE: &str = "dictionary:translation_done";
