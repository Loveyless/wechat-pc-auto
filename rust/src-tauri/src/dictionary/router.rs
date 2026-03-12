use anyhow::{anyhow, Result};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;

use super::providers::{CambridgeProvider, DictionaryProvider, FreeDictionaryProvider};
use super::types::WordEntry;

/// 词典路由器，根据 provider 分发查询请求
pub struct DictionaryRouter {
    providers: HashMap<&'static str, Arc<dyn DictionaryProvider>>,
    default_provider: &'static str,
}

impl DictionaryRouter {
    pub fn new(cambridge_db_path: Option<PathBuf>) -> Result<Self> {
        let mut providers: HashMap<&'static str, Arc<dyn DictionaryProvider>> = HashMap::new();

        // 注册 Free Dictionary Provider
        let free_dict = FreeDictionaryProvider::new()?;
        providers.insert(free_dict.id(), Arc::new(free_dict));

        // 注册 Cambridge Provider（如果数据库存在）
        let default_provider = if let Some(db_path) = cambridge_db_path {
            if db_path.exists() {
                match CambridgeProvider::new(db_path) {
                    Ok(cambridge) => {
                        let id = cambridge.id();
                        providers.insert(id, Arc::new(cambridge));
                        log::info!("Cambridge dictionary loaded successfully");
                        "cambridge"
                    }
                    Err(e) => {
                        log::warn!("Failed to load Cambridge dictionary: {}, falling back to free_dictionary", e);
                        "free_dictionary"
                    }
                }
            } else {
                log::warn!("Cambridge dictionary file not found, using free_dictionary");
                "free_dictionary"
            }
        } else {
            "free_dictionary"
        };

        Ok(Self {
            providers,
            default_provider,
        })
    }

    /// 获取可用的词典提供者列表
    pub fn list_providers(&self) -> Vec<ProviderInfo> {
        self.providers
            .values()
            .map(|p| ProviderInfo {
                id: p.id().to_string(),
                display_name: p.display_name().to_string(),
                requires_network: p.requires_network(),
                is_default: p.id() == self.default_provider,
            })
            .collect()
    }

    /// 获取默认提供者 ID
    pub fn default_provider_id(&self) -> &'static str {
        self.default_provider
    }

    /// 检查提供者是否可用
    pub fn has_provider(&self, provider_id: &str) -> bool {
        self.providers.contains_key(provider_id)
    }

    /// 使用指定提供者查询单词
    pub async fn lookup(&self, word: &str, provider_id: Option<&str>) -> Result<WordEntry> {
        let provider_id = provider_id.unwrap_or(self.default_provider);

        let provider = self
            .providers
            .get(provider_id)
            .ok_or_else(|| anyhow!("Unknown dictionary provider: {}", provider_id))?;

        provider.lookup(word).await
    }
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct ProviderInfo {
    pub id: String,
    pub display_name: String,
    pub requires_network: bool,
    pub is_default: bool,
}
