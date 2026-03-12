# Cambridge Dictionary Provider

Cambridge 词典渠道 - 基于本地 SQLite 数据库的离线词典查询。

## 特性

| 特性 | 说明 |
|------|------|
| **离线可用** | 数据存储在本地 SQLite 文件，无需网络 |
| **发音支持** | 提供英式(UK)和美式(US)发音音频 URL |
| **权威释义** | 来自剑桥词典，释义精准专业 |
| **默认渠道** | 应用的默认词典源 |

## 数据来源

词典数据存储在 `resources/dictionaries/cambridge.sqlite` 文件中。

### SQLite 表结构

```sql
-- camdict 表
CREATE TABLE camdict (
    word TEXT PRIMARY KEY,  -- 单词（小写）
    pos_items TEXT          -- 词性和释义 JSON（见下方结构）
);
```

## 数据结构

### 数据库存储格式 (pos_items JSON)

```json
[
  {
    "type": "noun",                           // 词性（英文）
    "pronunciations": [                       // 发音列表
      {
        "region": "uk",                       // 发音地区：uk/us
        "audio": "https://..../uk.mp3",       // 音频 URL
        "pronunciation": "/ˈɒp.əs/"           // 音标文本
      },
      {
        "region": "us",
        "audio": "https://..../us.mp3",
        "pronunciation": "/ˈɑː.pəs/"
      }
    ],
    "definitions": [                          // 释义列表
      {
        "definition": "a piece of music...",  // 英文释义
        "examples": [                         // 例句列表
          "Carl Nielsen's Opus 43 quintet"
        ]
      }
    ]
  }
]
```

### Rust 类型定义

```rust
/// Cambridge 词典 pos_items JSON 结构
/// 每个元素代表一个词性分组
#[derive(Debug, Clone, Deserialize)]
pub struct CambridgePosItem {
    #[serde(rename = "type")]
    pub pos_type: String,                    // 词性，如 "noun", "verb"
    pub pronunciations: Vec<CambridgePronunciation>,  // 发音列表
    pub definitions: Vec<CambridgeDefinition>,        // 释义列表
}

/// 发音信息
#[derive(Debug, Clone, Deserialize)]
pub struct CambridgePronunciation {
    pub region: String,       // 发音地区：uk/us
    pub audio: String,        // 音频 URL（远程）
    pub pronunciation: String, // 音标文本，如 "/ˈɒp.əs/"
}

/// 单个释义
#[derive(Debug, Clone, Deserialize)]
pub struct CambridgeDefinition {
    pub definition: String,   // 英文释义文本
    #[serde(default)]
    pub examples: Vec<String>, // 英文例句列表
}
```

## 数据转换流程

```
Cambridge SQLite 数据
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ CambridgePosItem (数据库原始格式)                    │
│ ├── type: "noun"                                    │
│ ├── pronunciations: [{ region, audio, pronunciation }] │
│ └── definitions: [{ definition, examples }]         │
└─────────────────────────────────────────────────────┘
        │
        │ convert_pos_items()
        ▼
┌─────────────────────────────────────────────────────┐
│ WordEntry (统一输出格式)                             │
│ ├── word: "opus"                                    │
│ ├── summary_zh: None (待翻译)                       │
│ ├── phonetics: [{ text, audio_url, region }]        │
│ ├── meanings: [{ part_of_speech, definitions }]     │
│ ├── fetched_at: "2024-01-01 12:00:00"               │
│ ├── translation_completed: false                    │
│ └── data_source: "cambridge"                        │
└─────────────────────────────────────────────────────┘
```

## 使用示例

```rust
use crate::dictionary::providers::cambridge::CambridgeProvider;
use crate::dictionary::providers::DictionaryProvider;

// 创建 provider
let provider = CambridgeProvider::new(PathBuf::from("cambridge.sqlite"))?;

// 查询单词
let entry = provider.lookup("hello").await?;

// 访问数据
println!("单词: {}", entry.word);
println!("音标: {:?}", entry.phonetics);
for meaning in &entry.meanings {
    println!("词性: {} ({})", meaning.part_of_speech, meaning.part_of_speech_zh);
    for def in &meaning.definitions {
        println!("  释义: {}", def.english);
    }
}
```

## 注意事项

1. **中文释义需要翻译**：Cambridge 词典只提供英文释义，中文释义由翻译服务补充
2. **音频需要网络**：虽然查词离线，但播放发音需要访问远程音频 URL
3. **大小写不敏感**：查询时会自动转换为小写
