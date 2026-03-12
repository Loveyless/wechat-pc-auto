use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// 模型费用信息
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelCost {
    #[serde(default)]
    pub input: f64,
    #[serde(default)]
    pub output: f64,
}

/// 模型信息
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub family: Option<String>,
    #[serde(default)]
    pub cost: Option<ModelCost>,
    #[serde(default)]
    pub tool_call: bool,
}

/// 渠道信息
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderInfo {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub api: Option<String>,
    #[serde(default)]
    pub doc: Option<String>,
    #[serde(default)]
    pub models: HashMap<String, ModelInfo>,
}

/// rig 框架支持的渠道列表
const SUPPORTED_PROVIDERS: &[&str] = &[
    "openai",
    "anthropic",
    "cohere",
    "deepseek",
    "gemini",
    "groq",
    "mistral",
    "openrouter",
    "perplexity",
    "together",
    "xai",
    "hyperbolic",
    "moonshot",
];

/// 从 models.dev 获取可用渠道和模型
pub async fn fetch_providers() -> Result<HashMap<String, ProviderInfo>> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()?;

    let resp = client
        .get("https://models.dev/api.json")
        .send()
        .await?;

    if !resp.status().is_success() {
        anyhow::bail!("Failed to fetch models.dev API: {}", resp.status());
    }

    let providers: HashMap<String, ProviderInfo> = resp.json().await?;

    // 过滤：只保留 rig 支持的渠道
    let filtered: HashMap<String, ProviderInfo> = providers
        .into_iter()
        .filter(|(k, _)| SUPPORTED_PROVIDERS.contains(&k.as_str()))
        .collect();

    Ok(filtered)
}

/// 获取内置的默认渠道列表（用于离线或 API 失败时）
pub fn get_builtin_providers() -> Vec<ProviderInfo> {
    vec![
        ProviderInfo {
            id: "openai".to_string(),
            name: "OpenAI".to_string(),
            api: Some("https://api.openai.com/v1".to_string()),
            doc: Some("https://platform.openai.com/docs".to_string()),
            models: [
                ("gpt-4o".to_string(), ModelInfo {
                    id: "gpt-4o".to_string(),
                    name: "GPT-4o".to_string(),
                    family: Some("gpt".to_string()),
                    cost: Some(ModelCost { input: 2.5, output: 10.0 }),
                    tool_call: true,
                }),
                ("gpt-4o-mini".to_string(), ModelInfo {
                    id: "gpt-4o-mini".to_string(),
                    name: "GPT-4o Mini".to_string(),
                    family: Some("gpt".to_string()),
                    cost: Some(ModelCost { input: 0.15, output: 0.6 }),
                    tool_call: true,
                }),
            ].into_iter().collect(),
        },
        ProviderInfo {
            id: "anthropic".to_string(),
            name: "Anthropic".to_string(),
            api: Some("https://api.anthropic.com".to_string()),
            doc: Some("https://docs.anthropic.com".to_string()),
            models: [
                ("claude-sonnet-4-20250514".to_string(), ModelInfo {
                    id: "claude-sonnet-4-20250514".to_string(),
                    name: "Claude Sonnet 4".to_string(),
                    family: Some("claude".to_string()),
                    cost: Some(ModelCost { input: 3.0, output: 15.0 }),
                    tool_call: true,
                }),
                ("claude-3-5-haiku-20241022".to_string(), ModelInfo {
                    id: "claude-3-5-haiku-20241022".to_string(),
                    name: "Claude 3.5 Haiku".to_string(),
                    family: Some("claude".to_string()),
                    cost: Some(ModelCost { input: 0.8, output: 4.0 }),
                    tool_call: true,
                }),
            ].into_iter().collect(),
        },
        ProviderInfo {
            id: "deepseek".to_string(),
            name: "DeepSeek".to_string(),
            api: Some("https://api.deepseek.com".to_string()),
            doc: Some("https://platform.deepseek.com/api-docs".to_string()),
            models: [
                ("deepseek-chat".to_string(), ModelInfo {
                    id: "deepseek-chat".to_string(),
                    name: "DeepSeek Chat".to_string(),
                    family: Some("deepseek".to_string()),
                    cost: Some(ModelCost { input: 0.14, output: 0.28 }),
                    tool_call: true,
                }),
            ].into_iter().collect(),
        },
        ProviderInfo {
            id: "groq".to_string(),
            name: "Groq".to_string(),
            api: Some("https://api.groq.com/openai/v1".to_string()),
            doc: Some("https://console.groq.com/docs".to_string()),
            models: [
                ("llama-3.3-70b-versatile".to_string(), ModelInfo {
                    id: "llama-3.3-70b-versatile".to_string(),
                    name: "Llama 3.3 70B".to_string(),
                    family: Some("llama".to_string()),
                    cost: Some(ModelCost { input: 0.59, output: 0.79 }),
                    tool_call: true,
                }),
            ].into_iter().collect(),
        },
        ProviderInfo {
            id: "openrouter".to_string(),
            name: "OpenRouter".to_string(),
            api: Some("https://openrouter.ai/api/v1".to_string()),
            doc: Some("https://openrouter.ai/docs".to_string()),
            models: HashMap::new(), // OpenRouter 支持多种模型，用户自己填
        },
    ]
}
