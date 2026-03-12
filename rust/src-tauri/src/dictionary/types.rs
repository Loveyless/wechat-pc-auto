use serde::{Deserialize, Serialize};

/// 词典条目（返回给前端）
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WordEntry {
    pub word: String,
    pub summary_zh: Option<String>,
    pub phonetics: Vec<Phonetic>,
    pub meanings: Vec<Meaning>,
    pub fetched_at: String,
    pub translation_completed: bool,
    pub data_source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Phonetic {
    pub text: Option<String>,
    pub audio_url: Option<String>,
    pub region: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Meaning {
    pub part_of_speech: String,
    pub part_of_speech_zh: String,
    pub definitions: Vec<Definition>,
    pub synonyms: Vec<String>,
    pub antonyms: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Definition {
    pub english: String,
    pub chinese: Option<String>,
    pub example: Option<String>,
    pub example_chinese: Option<String>,
}

/// freeDictionaryAPI 原始响应结构
#[derive(Debug, Clone, Deserialize)]
pub struct DictionaryApiResponse {
    pub word: String,
    pub phonetics: Vec<ApiPhonetic>,
    pub meanings: Vec<ApiMeaning>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ApiPhonetic {
    pub text: Option<String>,
    pub audio: Option<String>,
    #[serde(rename = "sourceUrl")]
    pub source_url: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ApiMeaning {
    #[serde(rename = "partOfSpeech")]
    pub part_of_speech: String,
    pub definitions: Vec<ApiDefinition>,
    pub synonyms: Option<Vec<String>>,
    pub antonyms: Option<Vec<String>>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ApiDefinition {
    pub definition: String,
    pub example: Option<String>,
    pub synonyms: Option<Vec<String>>,
    pub antonyms: Option<Vec<String>>,
}

/// 词性英中映射
pub fn part_of_speech_to_chinese(pos: &str) -> &'static str {
    match pos.to_lowercase().as_str() {
        "noun" => "名词",
        "verb" => "动词",
        "adjective" => "形容词",
        "adverb" => "副词",
        "interjection" => "感叹词",
        "pronoun" => "代词",
        "preposition" => "介词",
        "conjunction" => "连词",
        "determiner" => "限定词",
        "exclamation" => "感叹词",
        "article" => "冠词",
        "numeral" => "数词",
        _ => "其他",
    }
}

/// 从 API 响应转换为内部类型
impl From<DictionaryApiResponse> for WordEntry {
    fn from(api: DictionaryApiResponse) -> Self {
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
            data_source: "free_dictionary_api".to_string(),
        }
    }
}
