use anyhow::{anyhow, Result};
use async_trait::async_trait;
use rusqlite::{params, Connection};
use std::path::PathBuf;
use std::sync::Mutex;

use super::types::CambridgePosItem;
use crate::dictionary::providers::DictionaryProvider;
use crate::dictionary::types::{part_of_speech_to_chinese, Definition, Meaning, Phonetic, WordEntry};

pub struct CambridgeProvider {
    conn: Mutex<Connection>,
}

impl CambridgeProvider {
    pub fn new(db_path: PathBuf) -> Result<Self> {
        let conn = Connection::open(&db_path)?;
        Ok(Self {
            conn: Mutex::new(conn),
        })
    }

    fn convert_pos_items(word: String, pos_items: Vec<CambridgePosItem>) -> WordEntry {
        let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();

        // 收集所有发音（去重）
        let mut phonetics: Vec<Phonetic> = Vec::new();
        let mut seen_regions: std::collections::HashSet<String> = std::collections::HashSet::new();

        for item in &pos_items {
            for pron in &item.pronunciations {
                if !seen_regions.contains(&pron.region) {
                    seen_regions.insert(pron.region.clone());
                    phonetics.push(Phonetic {
                        text: Some(pron.pronunciation.clone()),
                        audio_url: if pron.audio.is_empty() {
                            None
                        } else {
                            Some(pron.audio.clone())
                        },
                        region: Some(pron.region.clone()),
                    });
                }
            }
        }

        // 转换词性和释义
        let meanings: Vec<Meaning> = pos_items
            .into_iter()
            .map(|item| {
                let pos_zh = part_of_speech_to_chinese(&item.pos_type).to_string();
                Meaning {
                    part_of_speech: item.pos_type,
                    part_of_speech_zh: pos_zh,
                    definitions: item
                        .definitions
                        .into_iter()
                        .map(|d| Definition {
                            english: d.definition,
                            chinese: None,
                            example: d.examples.into_iter().next(),
                            example_chinese: None,
                        })
                        .collect(),
                    synonyms: Vec::new(),
                    antonyms: Vec::new(),
                }
            })
            .collect();

        WordEntry {
            word,
            summary_zh: None,
            phonetics,
            meanings,
            fetched_at: now,
            translation_completed: false,
            data_source: "cambridge".to_string(),
        }
    }
}

#[async_trait]
impl DictionaryProvider for CambridgeProvider {
    fn id(&self) -> &'static str {
        "cambridge"
    }

    fn display_name(&self) -> &'static str {
        "Cambridge Dictionary"
    }

    fn requires_network(&self) -> bool {
        false
    }

    async fn lookup(&self, word: &str) -> Result<WordEntry> {
        let word = word.trim().to_lowercase();
        if word.is_empty() {
            return Err(anyhow!("Word cannot be empty"));
        }

        let conn = self.conn.lock().map_err(|e| anyhow!("Lock error: {}", e))?;

        let mut stmt = conn.prepare(
            "SELECT word, pos_items FROM camdict WHERE word = ?1 LIMIT 1",
        )?;

        let result = stmt.query_row(params![word], |row| {
            let db_word: String = row.get(0)?;
            let pos_items_json: String = row.get(1)?;
            Ok((db_word, pos_items_json))
        });

        match result {
            Ok((db_word, pos_items_json)) => {
                let pos_items: Vec<CambridgePosItem> = serde_json::from_str(&pos_items_json)
                    .map_err(|e| anyhow!("Failed to parse pos_items: {}", e))?;

                if pos_items.is_empty() {
                    return Err(anyhow!("Word found but no definitions: {}", word));
                }

                Ok(Self::convert_pos_items(db_word, pos_items))
            }
            Err(rusqlite::Error::QueryReturnedNoRows) => {
                Err(anyhow!("Word not found in Cambridge dictionary: {}", word))
            }
            Err(e) => Err(anyhow!("Database error: {}", e)),
        }
    }
}
