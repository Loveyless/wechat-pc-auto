use crate::translator::ai::AiTranslator;
use crate::translator::config::{TranslateConfig, TranslateProviderConfig};
use crate::translator::deeplx::DeepLXTranslator;
use crate::translator::limiter::TranslationLimiter;
use crate::translator::traits::Translator;
use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;

/// 翻译服务状态
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TranslatorServiceStatus {
    pub enabled: bool,
    pub configured: bool,
    pub checking: bool,
    pub healthy: Option<bool>,
    pub last_error: Option<String>,
    #[serde(default)]
    pub provider: String,
}

impl TranslatorServiceStatus {
    pub fn disabled() -> Self {
        Self {
            enabled: false,
            configured: false,
            checking: false,
            healthy: None,
            last_error: None,
            provider: String::new(),
        }
    }

    pub fn unconfigured(provider: &str) -> Self {
        Self {
            enabled: true,
            configured: false,
            checking: false,
            healthy: None,
            last_error: None,
            provider: provider.to_string(),
        }
    }

    pub fn checking(provider: &str) -> Self {
        Self {
            enabled: true,
            configured: true,
            checking: true,
            healthy: None,
            last_error: None,
            provider: provider.to_string(),
        }
    }

    pub fn healthy(provider: &str) -> Self {
        Self {
            enabled: true,
            configured: true,
            checking: false,
            healthy: Some(true),
            last_error: None,
            provider: provider.to_string(),
        }
    }

    pub fn error(provider: &str, message: impl Into<String>) -> Self {
        let msg = message.into();
        let short_msg = if msg.len() > 100 {
            format!("{}...", &msg[..100])
        } else {
            msg
        };
        Self {
            enabled: true,
            configured: true,
            checking: false,
            healthy: Some(false),
            last_error: Some(short_msg),
            provider: provider.to_string(),
        }
    }

    pub fn menu_text(&self) -> &'static str {
        if !self.enabled {
            "○ 翻译未启用"
        } else if !self.configured {
            "○ 翻译未配置"
        } else if self.checking {
            "◐ 翻译检测中"
        } else if self.healthy == Some(true) {
            "● 翻译服务可用"
        } else {
            "⚠ 翻译服务异常"
        }
    }

    pub fn as_json(&self) -> serde_json::Value {
        serde_json::json!({
            "enabled": self.enabled,
            "configured": self.configured,
            "checking": self.checking,
            "healthy": self.healthy,
            "last_error": self.last_error,
            "provider": self.provider,
        })
    }
}

/// 全局翻译服务
/// 统一管理翻译器和限流器，支持动态切换渠道
pub struct TranslationService {
    translator: RwLock<Option<Arc<dyn Translator>>>,
    limiter: RwLock<Option<Arc<TranslationLimiter>>>,
    config: RwLock<TranslateConfig>,
    status: RwLock<TranslatorServiceStatus>,
}

impl TranslationService {
    pub fn new() -> Self {
        Self {
            translator: RwLock::new(None),
            limiter: RwLock::new(None),
            config: RwLock::new(TranslateConfig::default()),
            status: RwLock::new(TranslatorServiceStatus::disabled()),
        }
    }

    /// 根据配置创建对应的翻译器实例
    fn create_translator(config: &TranslateConfig) -> Result<Arc<dyn Translator>> {
        match &config.provider_config {
            TranslateProviderConfig::Deeplx { url } => {
                Ok(Arc::new(DeepLXTranslator::new(
                    url,
                    &config.source_lang,
                    &config.target_lang,
                    config.timeout_seconds,
                )))
            }
            TranslateProviderConfig::Ai {
                provider_id,
                model_id,
                api_key,
                base_url,
            } => {
                Ok(Arc::new(AiTranslator::new(
                    provider_id,
                    model_id,
                    api_key,
                    base_url.as_deref(),
                    &config.source_lang,
                    &config.target_lang,
                    config.timeout_seconds,
                )?))
            }
        }
    }

    /// 更新翻译配置
    pub async fn update_config(&self, config: TranslateConfig) -> TranslatorServiceStatus {
        let provider_name = config.provider_name().to_string();

        let (translator, limiter, status) = if !config.enabled {
            (None, None, TranslatorServiceStatus::disabled())
        } else if !config.is_configured() {
            (None, None, TranslatorServiceStatus::unconfigured(&provider_name))
        } else {
            match Self::create_translator(&config) {
                Ok(t) => {
                    let limiter = Arc::new(TranslationLimiter::new(
                        config.max_concurrency,
                        config.max_requests_per_second,
                    ));
                    (Some(t), Some(limiter), TranslatorServiceStatus::checking(&provider_name))
                }
                Err(e) => {
                    log::error!("Failed to create translator: {}", e);
                    (None, None, TranslatorServiceStatus::error(&provider_name, e.to_string()))
                }
            }
        };

        {
            let mut t = self.translator.write().await;
            *t = translator;
        }
        {
            let mut l = self.limiter.write().await;
            *l = limiter;
        }
        {
            let mut c = self.config.write().await;
            *c = config;
        }
        {
            let mut s = self.status.write().await;
            *s = status.clone();
        }

        status
    }

    /// 设置翻译服务状态
    pub async fn set_status(&self, status: TranslatorServiceStatus) {
        let mut s = self.status.write().await;
        *s = status;
    }

    /// 获取当前状态
    pub async fn get_status(&self) -> TranslatorServiceStatus {
        self.status.read().await.clone()
    }

    /// 获取当前配置
    pub async fn get_config(&self) -> TranslateConfig {
        self.config.read().await.clone()
    }

    /// 检查服务是否可用
    pub async fn is_available(&self) -> bool {
        self.translator.read().await.is_some()
    }

    /// 翻译文本（使用默认语言配置）
    pub async fn translate(&self, text: &str) -> Result<String> {
        let config = self.config.read().await.clone();
        self.translate_with_langs(text, &config.source_lang, &config.target_lang)
            .await
    }

    /// 翻译文本（指定语言）
    pub async fn translate_with_langs(
        &self,
        text: &str,
        source_lang: &str,
        target_lang: &str,
    ) -> Result<String> {
        let translator = {
            let guard = self.translator.read().await;
            guard.clone()
        };

        let translator = translator.ok_or_else(|| anyhow::anyhow!("翻译服务未配置"))?;

        let limiter = {
            let guard = self.limiter.read().await;
            guard.clone()
        };

        if let Some(limiter) = limiter {
            let _permit = limiter.acquire().await;
            translator.translate(text, source_lang, target_lang).await
        } else {
            translator.translate(text, source_lang, target_lang).await
        }
    }

    /// 健康检查
    pub async fn check_health(&self) -> Result<()> {
        let translator = {
            let guard = self.translator.read().await;
            guard.clone()
        };

        let translator = translator.ok_or_else(|| anyhow::anyhow!("翻译服务未配置"))?;

        let limiter = {
            let guard = self.limiter.read().await;
            guard.clone()
        };

        if let Some(limiter) = limiter {
            let _permit = limiter.acquire().await;
            translator.check_health().await
        } else {
            translator.check_health().await
        }
    }

    /// 获取限流器（供需要直接访问的场景）
    pub async fn get_limiter(&self) -> Option<Arc<TranslationLimiter>> {
        self.limiter.read().await.clone()
    }

    /// 同时获取翻译器和限流器（用于 sidebar）
    pub async fn get_translator_and_limiter(
        &self,
    ) -> (
        Option<Arc<dyn Translator>>,
        Option<Arc<TranslationLimiter>>,
    ) {
        let translator = self.translator.read().await.clone();
        let limiter = self.limiter.read().await.clone();
        (translator, limiter)
    }
}

impl Default for TranslationService {
    fn default() -> Self {
        Self::new()
    }
}
