use serde::Deserialize;

/// freeDictionaryAPI 原始响应结构
#[derive(Debug, Clone, Deserialize)]
pub struct FreeDictionaryApiResponse {
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
