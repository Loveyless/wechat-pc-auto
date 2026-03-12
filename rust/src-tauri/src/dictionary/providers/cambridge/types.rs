use serde::Deserialize;

/// Cambridge 词典 pos_items JSON 结构
#[derive(Debug, Clone, Deserialize)]
pub struct CambridgePosItem {
    #[serde(rename = "type")]
    pub pos_type: String,
    pub pronunciations: Vec<CambridgePronunciation>,
    pub definitions: Vec<CambridgeDefinition>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CambridgePronunciation {
    pub region: String,
    pub audio: String,
    pub pronunciation: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CambridgeDefinition {
    pub definition: String,
    #[serde(default)]
    pub examples: Vec<String>,
}
