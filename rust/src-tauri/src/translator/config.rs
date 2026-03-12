use serde::{Deserialize, Serialize};

/// 渠道特定配置
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "provider", rename_all = "snake_case")]
pub enum TranslateProviderConfig {
    /// DeepLX 翻译
    Deeplx {
        #[serde(default)]
        url: String,
    },
    /// AI 翻译（基于 rig 框架）
    Ai {
        /// 渠道 ID（openai, anthropic, deepseek 等）
        provider_id: String,
        /// 模型 ID
        model_id: String,
        /// API Key（敏感信息）
        #[serde(default)]
        api_key: String,
        /// 自定义 endpoint（可选，用于 OpenRouter 等）
        #[serde(default)]
        base_url: Option<String>,
    },
}

impl Default for TranslateProviderConfig {
    fn default() -> Self {
        Self::Deeplx {
            url: String::new(),
        }
    }
}

/// 翻译配置
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TranslateConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(flatten)]
    pub provider_config: TranslateProviderConfig,
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
}

impl Default for TranslateConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            provider_config: TranslateProviderConfig::default(),
            source_lang: default_source_lang(),
            target_lang: default_target_lang(),
            timeout_seconds: default_timeout(),
            max_concurrency: default_max_concurrency(),
            max_requests_per_second: default_max_requests_per_second(),
        }
    }
}

impl TranslateConfig {
    /// 获取渠道名称
    pub fn provider_name(&self) -> &str {
        match &self.provider_config {
            TranslateProviderConfig::Deeplx { .. } => "deeplx",
            TranslateProviderConfig::Ai { provider_id, .. } => provider_id,
        }
    }

    /// 检查是否已配置
    pub fn is_configured(&self) -> bool {
        match &self.provider_config {
            TranslateProviderConfig::Deeplx { url } => !url.trim().is_empty(),
            TranslateProviderConfig::Ai { api_key, .. } => !api_key.trim().is_empty(),
        }
    }
}

fn default_true() -> bool {
    true
}

fn default_source_lang() -> String {
    "auto".to_string()
}

fn default_target_lang() -> String {
    "EN".to_string()
}

fn default_timeout() -> f64 {
    15.0
}

fn default_max_concurrency() -> usize {
    3
}

fn default_max_requests_per_second() -> usize {
    3
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deeplx_config_serde() {
        let config = TranslateConfig {
            enabled: true,
            provider_config: TranslateProviderConfig::Deeplx {
                url: "https://api.deeplx.org".to_string(),
            },
            source_lang: "auto".to_string(),
            target_lang: "EN".to_string(),
            timeout_seconds: 8.0,
            max_concurrency: 3,
            max_requests_per_second: 3,
        };

        let json = serde_json::to_string_pretty(&config).unwrap();
        println!("DeepLX config JSON:\n{}", json);

        let parsed: TranslateConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(config, parsed);
    }

    #[test]
    fn test_ai_config_serde() {
        let config = TranslateConfig {
            enabled: true,
            provider_config: TranslateProviderConfig::Ai {
                provider_id: "openai".to_string(),
                model_id: "gpt-4o".to_string(),
                api_key: "sk-xxx".to_string(),
                base_url: None,
            },
            source_lang: "auto".to_string(),
            target_lang: "ZH".to_string(),
            timeout_seconds: 15.0,
            max_concurrency: 3,
            max_requests_per_second: 3,
        };

        let json = serde_json::to_string_pretty(&config).unwrap();
        println!("AI config JSON:\n{}", json);

        let parsed: TranslateConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(config, parsed);
    }
}
