use anyhow::Result;
use async_trait::async_trait;

/// 统一的翻译器 trait
/// 所有翻译渠道（DeepLX、AI 等）都需要实现此 trait
#[async_trait]
pub trait Translator: Send + Sync {
    /// 翻译文本
    async fn translate(&self, text: &str, source_lang: &str, target_lang: &str) -> Result<String>;

    /// 健康检查
    async fn check_health(&self) -> Result<()>;

    /// 渠道标识（用于日志/调试）
    fn provider_id(&self) -> &str;
}
