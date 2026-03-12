# Free Dictionary API Provider

Free Dictionary API 渠道 - 基于在线 API 的词典查询服务。

## 特性

| 特性 | 说明 |
|------|------|
| **在线查询** | 需要网络连接，实时获取最新数据 |
| **免费开源** | 完全免费，无需 API Key |
| **同义词/反义词** | 提供丰富的同义词和反义词 |
| **多发音** | 支持英式(UK)、美式(US)、澳式(AU)发音 |

## API 端点

```
https://api.dictionaryapi.dev/api/v2/entries/en/{word}
```

### 请求参数

| 参数 | 说明 |
|------|------|
| `{word}` | 要查询的英文单词（URL 编码） |

### 响应示例

```json
[
  {
    "word": "hello",
    "phonetics": [
      {
        "text": "/həˈloʊ/",
        "audio": "https://api.dictionaryapi.dev/media/pronunciations/en/hello-us.mp3",
        "sourceUrl": "https://commons.wikimedia.org/w/index.php?curid=9851098"
      }
    ],
    "meanings": [
      {
        "partOfSpeech": "noun",
        "definitions": [
          {
            "definition": "\"Hello!\" or an equivalent greeting.",
            "example": "The newcomer was surprised by the warmth of our hellos.",
            "synonyms": [],
            "antonyms": []
          }
        ],
        "synonyms": ["greeting"],
        "antonyms": ["goodbye", "farewell"]
      }
    ]
  }
]
```

## 数据结构

### API 响应类型 (Rust)

```rust
/// freeDictionaryAPI 原始响应结构
/// API 返回一个数组，通常只包含一个元素
#[derive(Debug, Clone, Deserialize)]
pub struct FreeDictionaryApiResponse {
    pub word: String,                  // 单词原文
    pub phonetics: Vec<ApiPhonetic>,   // 发音列表
    pub meanings: Vec<ApiMeaning>,     // 词义列表（按词性分组）
}

/// 发音信息
#[derive(Debug, Clone, Deserialize)]
pub struct ApiPhonetic {
    pub text: Option<String>,          // 音标文本，如 "/həˈloʊ/"
    pub audio: Option<String>,         // 音频 URL
    #[serde(rename = "sourceUrl")]
    pub source_url: Option<String>,    // 音频来源 URL
}

/// 词性分组
#[derive(Debug, Clone, Deserialize)]
pub struct ApiMeaning {
    #[serde(rename = "partOfSpeech")]
    pub part_of_speech: String,        // 词性，如 "noun", "verb", "adjective"
    pub definitions: Vec<ApiDefinition>, // 该词性下的所有释义
    pub synonyms: Option<Vec<String>>,  // 词性级别的同义词
    pub antonyms: Option<Vec<String>>,  // 词性级别的反义词
}

/// 单个释义
#[derive(Debug, Clone, Deserialize)]
pub struct ApiDefinition {
    pub definition: String,            // 英文释义
    pub example: Option<String>,       // 例句（可选）
    pub synonyms: Option<Vec<String>>, // 释义级别的同义词
    pub antonyms: Option<Vec<String>>, // 释义级别的反义词
}
```

## 数据转换流程

```
Free Dictionary API 响应
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ FreeDictionaryApiResponse (API 原始格式)            │
│ ├── word: "hello"                                   │
│ ├── phonetics: [{ text, audio, sourceUrl }]         │
│ └── meanings: [{ partOfSpeech, definitions, ... }]  │
└─────────────────────────────────────────────────────┘
        │
        │ convert_response()
        ▼
┌─────────────────────────────────────────────────────┐
│ WordEntry (统一输出格式)                             │
│ ├── word: "hello"                                   │
│ ├── summary_zh: None (待翻译)                       │
│ ├── phonetics: [                                    │
│ │     { text: "/həˈloʊ/", audio_url, region: "us" } │
│ │   ]                                               │
│ ├── meanings: [                                     │
│ │     {                                             │
│ │       part_of_speech: "noun",                     │
│ │       part_of_speech_zh: "名词",                  │
│ │       definitions: [{ english, chinese: None }],  │
│ │       synonyms: ["greeting"],                     │
│ │       antonyms: ["goodbye"]                       │
│ │     }                                             │
│ │   ]                                               │
│ ├── fetched_at: "2024-01-01 12:00:00"               │
│ ├── translation_completed: false                    │
│ └── data_source: "free_dictionary"                  │
└─────────────────────────────────────────────────────┘
```

## 发音地区识别

通过音频 URL 自动识别发音地区：

```rust
let region = audio_url.and_then(|url| {
    if url.contains("-uk") {
        Some("uk".to_string())   // 英式发音
    } else if url.contains("-us") {
        Some("us".to_string())   // 美式发音
    } else if url.contains("-au") {
        Some("au".to_string())   // 澳式发音
    } else {
        None
    }
});
```

## 使用示例

```rust
use crate::dictionary::providers::free_dictionary::FreeDictionaryProvider;
use crate::dictionary::providers::DictionaryProvider;

// 创建 provider
let provider = FreeDictionaryProvider::new()?;

// 查询单词
let entry = provider.lookup("hello").await?;

// 访问数据
println!("单词: {}", entry.word);
println!("数据来源: {}", entry.data_source);

for phonetic in &entry.phonetics {
    if let Some(text) = &phonetic.text {
        println!("音标: {}", text);
    }
    if let Some(region) = &phonetic.region {
        println!("地区: {}", region);
    }
}

for meaning in &entry.meanings {
    println!("词性: {} ({})", meaning.part_of_speech, meaning.part_of_speech_zh);
    println!("同义词: {:?}", meaning.synonyms);
    println!("反义词: {:?}", meaning.antonyms);
    
    for def in &meaning.definitions {
        println!("  释义: {}", def.english);
        if let Some(example) = &def.example {
            println!("  例句: {}", example);
        }
    }
}
```

## 错误处理

| 状态码 | 说明 |
|--------|------|
| 200 | 查询成功 |
| 404 | 单词不存在 |
| 其他 | API 请求失败 |

## 注意事项

1. **需要网络**：每次查询都需要访问外网 API
2. **超时设置**：默认 10 秒超时
3. **中文释义需要翻译**：API 只提供英文释义，中文释义由翻译服务补充
4. **速率限制**：Free Dictionary API 可能有速率限制，请勿频繁请求
5. **全球网络**：在中国大陆可能需要代理才能访问

## 与 Cambridge 对比

| 特性 | Cambridge | Free Dictionary |
|------|-----------|-----------------|
| 网络需求 | 离线可用 | 需要网络 |
| 数据来源 | 本地 SQLite | 在线 API |
| 同义词/反义词 | ❌ | ✅ |
| 释义权威性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 词汇覆盖 | 常用词 | 更广泛 |
| 更新频率 | 静态 | 实时 |
