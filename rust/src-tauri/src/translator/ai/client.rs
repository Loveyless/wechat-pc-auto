use crate::translator::traits::Translator;
use anyhow::{Context, Result};
use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;

const TRANSLATION_SYSTEM_PROMPT: &str = r#"You are a professional translator. Your task is to translate text accurately while preserving the original meaning, tone, and style.

Rules:
1. Output ONLY the translated text, nothing else
2. Do not add explanations, notes, or commentary
3. Preserve formatting (line breaks, punctuation)
4. For technical terms or proper nouns, keep them as-is if no standard translation exists
5. Maintain the register (formal/informal) of the original text"#;

/// AI 翻译器（使用 OpenAI 兼容 API）
pub struct AiTranslator {
    client: Client,
    base_url: String,
    api_key: String,
    model_id: String,
    provider_id: String,
    source_lang: String,
    target_lang: String,
}

#[derive(Serialize)]
struct ChatMessage {
    role: String,
    content: String,
}

#[derive(Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<ChatMessage>,
    temperature: f64,
    max_tokens: Option<u32>,
}

#[derive(Deserialize)]
struct ChatChoice {
    message: ChatMessageResponse,
}

#[derive(Deserialize)]
struct ChatMessageResponse {
    content: String,
}

#[derive(Deserialize)]
struct ChatResponse {
    choices: Vec<ChatChoice>,
}

impl AiTranslator {
    pub fn new(
        provider_id: &str,
        model_id: &str,
        api_key: &str,
        base_url: Option<&str>,
        source_lang: &str,
        target_lang: &str,
        timeout_seconds: f64,
    ) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs_f64(timeout_seconds))
            .build()?;

        // 根据 provider_id 确定 base_url
        let resolved_base_url = match base_url {
            Some(url) if !url.is_empty() => url.trim_end_matches('/').to_string(),
            _ => match provider_id {
                "openai" => "https://api.openai.com/v1".to_string(),
                "anthropic" => "https://api.anthropic.com/v1".to_string(),
                "deepseek" => "https://api.deepseek.com".to_string(),
                "groq" => "https://api.groq.com/openai/v1".to_string(),
                "mistral" => "https://api.mistral.ai/v1".to_string(),
                "openrouter" => "https://openrouter.ai/api/v1".to_string(),
                "together" => "https://api.together.xyz/v1".to_string(),
                "perplexity" => "https://api.perplexity.ai".to_string(),
                "moonshot" => "https://api.moonshot.cn/v1".to_string(),
                _ => anyhow::bail!("Unknown provider '{}' requires base_url", provider_id),
            },
        };

        Ok(Self {
            client,
            base_url: resolved_base_url,
            api_key: api_key.to_string(),
            model_id: model_id.to_string(),
            provider_id: provider_id.to_string(),
            source_lang: source_lang.to_string(),
            target_lang: target_lang.to_string(),
        })
    }

    pub fn model_id(&self) -> &str {
        &self.model_id
    }

    async fn chat_completion(&self, user_message: &str) -> Result<String> {
        let url = format!("{}/chat/completions", self.base_url);

        let request = ChatRequest {
            model: self.model_id.clone(),
            messages: vec![
                ChatMessage {
                    role: "system".to_string(),
                    content: TRANSLATION_SYSTEM_PROMPT.to_string(),
                },
                ChatMessage {
                    role: "user".to_string(),
                    content: user_message.to_string(),
                },
            ],
            temperature: 0.3,
            max_tokens: Some(4096),
        };

        let mut req = self
            .client
            .post(&url)
            .header("Content-Type", "application/json")
            .header("Authorization", format!("Bearer {}", self.api_key));

        // Anthropic 使用不同的认证头
        if self.provider_id == "anthropic" {
            req = req
                .header("x-api-key", &self.api_key)
                .header("anthropic-version", "2023-06-01");
        }

        let resp = req.json(&request).send().await.context("AI API request failed")?;

        let status = resp.status();
        if !status.is_success() {
            let body = resp.text().await.unwrap_or_default();
            let snippet: String = body.chars().take(300).collect();
            anyhow::bail!("AI API HTTP {}: {}", status.as_u16(), snippet);
        }

        let response: ChatResponse = resp.json().await.context("AI API response parse failed")?;

        response
            .choices
            .first()
            .map(|c| c.message.content.trim().to_string())
            .ok_or_else(|| anyhow::anyhow!("AI API returned empty response"))
    }
}

#[async_trait]
impl Translator for AiTranslator {
    async fn translate(&self, text: &str, source_lang: &str, target_lang: &str) -> Result<String> {
        let source = if source_lang == "auto" {
            "the source language (auto-detect)"
        } else {
            source_lang
        };

        let prompt = format!(
            "Translate the following text from {} to {}:\n\n{}",
            source, target_lang, text
        );

        self.chat_completion(&prompt).await
    }

    async fn check_health(&self) -> Result<()> {
        self.translate("Hello, world!", &self.source_lang, &self.target_lang)
            .await
            .map(|_| ())
    }

    fn provider_id(&self) -> &str {
        &self.provider_id
    }
}
