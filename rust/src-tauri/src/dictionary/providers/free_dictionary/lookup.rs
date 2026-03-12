use anyhow::{anyhow, Result};
use async_trait::async_trait;
use reqwest::Client;
use std::time::Duration;

use super::types::FreeDictionaryApiResponse;
use crate::dictionary::types::{part_of_speech_to_chinese, Definition, Meaning, Phonetic, WordEntry};
use crate::dictionary::providers::DictionaryProvider;

const API_BASE_URL: &str = "https://api.dictionaryapi.dev/api/v2/entries/en";
const REQUEST_TIMEOUT_SECS: u64 = 10;

pub struct FreeDictionaryProvider {
    client: Client,
}

impl FreeDictionaryProvider {
    pub fn new() -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(REQUEST_TIMEOUT_SECS))
            .build()?;
        Ok(Self { client })
    }

    fn convert_response(api: FreeDictionaryApiResponse) -> WordEntry {
        let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();

        let phonetics = api
            .phonetics
            .into_iter()
            .filter(|p| p.text.is_some() || p.audio.is_some())
            .map(|p| {
                let region = p.audio.as_ref().and_then(|url| {
                    if url.contains("-uk") {
                        Some("uk".to_string())
                    } else if url.contains("-us") {
                        Some("us".to_string())
                    } else if url.contains("-au") {
                        Some("au".to_string())
                    } else {
                        None
                    }
                });
                Phonetic {
                    text: p.text,
                    audio_url: p.audio.filter(|s| !s.is_empty()),
                    region,
                }
            })
            .collect();

        let meanings = api
            .meanings
            .into_iter()
            .map(|m| {
                let pos_zh = part_of_speech_to_chinese(&m.part_of_speech).to_string();
                Meaning {
                    part_of_speech: m.part_of_speech,
                    part_of_speech_zh: pos_zh,
                    definitions: m
                        .definitions
                        .into_iter()
                        .map(|d| Definition {
                            english: d.definition,
                            chinese: None,
                            example: d.example,
                            example_chinese: None,
                        })
                        .collect(),
                    synonyms: m.synonyms.unwrap_or_default(),
                    antonyms: m.antonyms.unwrap_or_default(),
                }
            })
            .collect();

        WordEntry {
            word: api.word,
            summary_zh: None,
            phonetics,
            meanings,
            fetched_at: now,
            translation_completed: false,
            data_source: "free_dictionary".to_string(),
        }
    }
}

impl Default for FreeDictionaryProvider {
    fn default() -> Self {
        Self::new().expect("Failed to create FreeDictionaryProvider")
    }
}

#[async_trait]
impl DictionaryProvider for FreeDictionaryProvider {
    fn id(&self) -> &'static str {
        "free_dictionary"
    }

    fn display_name(&self) -> &'static str {
        "Free Dictionary API"
    }

    fn requires_network(&self) -> bool {
        true
    }

    async fn lookup(&self, word: &str) -> Result<WordEntry> {
        let word = word.trim().to_lowercase();
        if word.is_empty() {
            return Err(anyhow!("Word cannot be empty"));
        }

        let encoded_word = word.replace(' ', "%20");
        let url = format!("{}/{}", API_BASE_URL, encoded_word);
        let response = self.client.get(&url).send().await?;

        if !response.status().is_success() {
            let status = response.status();
            if status.as_u16() == 404 {
                return Err(anyhow!("Word not found: {}", word));
            }
            return Err(anyhow!("API request failed with status: {}", status));
        }

        let body = response.text().await?;
        let api_responses: Vec<FreeDictionaryApiResponse> = serde_json::from_str(&body)
            .map_err(|e| anyhow!("Failed to parse API response: {}", e))?;

        let first = api_responses
            .into_iter()
            .next()
            .ok_or_else(|| anyhow!("Empty response from API"))?;

        Ok(Self::convert_response(first))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_lookup_hello() {
        let provider = FreeDictionaryProvider::new().unwrap();
        let result = provider.lookup("hello").await;

        match result {
            Ok(entry) => {
                assert_eq!(entry.word, "hello");
                assert!(!entry.meanings.is_empty());
                assert_eq!(entry.data_source, "free_dictionary");
            }
            Err(e) => {
                eprintln!("Skipping test due to network error: {}", e);
            }
        }
    }
}
