use anyhow::Result;
use async_trait::async_trait;

use super::types::WordEntry;

pub mod cambridge;
pub mod free_dictionary;

/// 词典提供者 trait
#[async_trait]
pub trait DictionaryProvider: Send + Sync {
    /// 提供者标识（用于 data_source 字段）
    fn id(&self) -> &'static str;

    /// 显示名称
    fn display_name(&self) -> &'static str;

    /// 是否需要网络
    fn requires_network(&self) -> bool;

    /// 查询单词，返回统一的 WordEntry
    async fn lookup(&self, word: &str) -> Result<WordEntry>;
}

pub use cambridge::CambridgeProvider;
pub use free_dictionary::FreeDictionaryProvider;
