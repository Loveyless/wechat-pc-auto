use crate::translator::traits::Translator;
use anyhow::{Context, Result};
use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;

#[derive(Clone)]
pub struct DeepLXTranslator {
    client: Client,
    base_url: String,
    source_lang: String,
    target_lang: String,
}

#[derive(Serialize)]
struct TranslateRequest {
    text: String,
    source_lang: String,
    target_lang: String,
}

#[derive(Deserialize)]
struct TranslateResponse {
    data: Option<String>,
    text: Option<String>,
    translation: Option<String>,
}

impl DeepLXTranslator {
    pub fn new(base_url: &str, source_lang: &str, target_lang: &str, timeout_seconds: f64) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs_f64(timeout_seconds))
            .build()
            .unwrap_or_default();

        Self {
            client,
            base_url: base_url.to_string(),
            source_lang: source_lang.to_string(),
            target_lang: target_lang.to_string(),
        }
    }

    pub fn source_lang(&self) -> &str {
        &self.source_lang
    }

    pub fn target_lang(&self) -> &str {
        &self.target_lang
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }
}

#[async_trait]
impl Translator for DeepLXTranslator {
    async fn translate(&self, text: &str, source_lang: &str, target_lang: &str) -> Result<String> {
        if self.base_url.is_empty() {
            return Ok(text.to_string());
        }

        let req_body = TranslateRequest {
            text: text.to_string(),
            source_lang: source_lang.to_string(),
            target_lang: target_lang.to_string(),
        };

        let mut request = self
            .client
            .post(&self.base_url)
            .header("Content-Type", "application/json; charset=utf-8")
            .header("Accept", "application/json, text/plain, */*")
            .header(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            );

        if self.base_url.contains("deeplx.org") {
            request = request
                .header("Origin", "https://api.deeplx.org")
                .header("Referer", "https://api.deeplx.org/");
        }

        let resp = request
            .json(&req_body)
            .send()
            .await
            .context("DeepLX request failed")?;

        let status = resp.status();
        if !status.is_success() {
            let body_text = resp.text().await.unwrap_or_default();
            let snippet: String = body_text.chars().take(200).collect();
            anyhow::bail!("DeepLX HTTP {}: {}", status.as_u16(), snippet);
        }

        let body: TranslateResponse = resp.json().await.context("DeepLX response parse failed")?;

        let translated = body
            .data
            .or(body.text)
            .or(body.translation)
            .unwrap_or_else(|| text.to_string());

        Ok(translated)
    }

    async fn check_health(&self) -> Result<()> {
        self.translate("你好，世界", &self.source_lang, &self.target_lang)
            .await
            .map(|_| ())
    }

    fn provider_id(&self) -> &str {
        "deeplx"
    }
}
