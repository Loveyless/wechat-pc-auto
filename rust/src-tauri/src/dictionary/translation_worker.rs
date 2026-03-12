use crate::dictionary::db::hash_text;
use crate::dictionary::events::{
    FieldTranslatedEvent, TranslationDoneEvent, EVENT_FIELD_TRANSLATED, EVENT_TRANSLATION_DONE,
};
use crate::dictionary::{DictionaryDb, WordEntry};
use crate::translator::TranslationService;
use std::sync::Arc;
use tauri::{AppHandle, Emitter};

/// 翻译任务类型
#[derive(Debug, Clone)]
enum TranslationTask {
    SummaryZh {
        text: String,
    },
    Definition {
        meaning_idx: usize,
        def_idx: usize,
        text: String,
    },
    Example {
        meaning_idx: usize,
        def_idx: usize,
        text: String,
    },
}

impl TranslationTask {
    fn field_name(&self) -> String {
        match self {
            TranslationTask::SummaryZh { .. } => "summary_zh".to_string(),
            TranslationTask::Definition {
                meaning_idx,
                def_idx,
                ..
            } => format!("def_{}_{}", meaning_idx, def_idx),
            TranslationTask::Example {
                meaning_idx,
                def_idx,
                ..
            } => format!("ex_{}_{}", meaning_idx, def_idx),
        }
    }

    fn text(&self) -> &str {
        match self {
            TranslationTask::SummaryZh { text } => text,
            TranslationTask::Definition { text, .. } => text,
            TranslationTask::Example { text, .. } => text,
        }
    }
}

/// 翻译工作器
pub struct TranslationWorker {
    app_handle: AppHandle,
    dict_db: Arc<DictionaryDb>,
    translation_service: Arc<TranslationService>,
}

impl TranslationWorker {
    pub fn new(
        app_handle: AppHandle,
        dict_db: Arc<DictionaryDb>,
        translation_service: Arc<TranslationService>,
    ) -> Self {
        Self {
            app_handle,
            dict_db,
            translation_service,
        }
    }

    /// 启动单词翻译任务（异步，不阻塞）
    pub fn spawn_translation(&self, word: String, entry: WordEntry) {
        let worker = self.clone_inner();
        tokio::spawn(async move {
            worker.translate_word(word, entry).await;
        });
    }

    fn clone_inner(&self) -> TranslationWorkerInner {
        TranslationWorkerInner {
            app_handle: self.app_handle.clone(),
            dict_db: self.dict_db.clone(),
            translation_service: self.translation_service.clone(),
        }
    }
}

struct TranslationWorkerInner {
    app_handle: AppHandle,
    dict_db: Arc<DictionaryDb>,
    translation_service: Arc<TranslationService>,
}

impl TranslationWorkerInner {
    async fn translate_word(&self, word: String, entry: WordEntry) {
        // 收集所有需要翻译的任务
        let mut tasks = Vec::new();

        // 1. summary_zh 最先翻译（翻译单词本身）
        if entry.summary_zh.is_none() {
            tasks.push(TranslationTask::SummaryZh {
                text: word.clone(),
            });
        }

        // 2. 按词性顺序添加释义和例句
        for (m_idx, meaning) in entry.meanings.iter().enumerate() {
            for (d_idx, def) in meaning.definitions.iter().enumerate() {
                if def.chinese.is_none() {
                    tasks.push(TranslationTask::Definition {
                        meaning_idx: m_idx,
                        def_idx: d_idx,
                        text: def.english.clone(),
                    });
                }
                if let Some(ref example) = def.example {
                    if def.example_chinese.is_none() {
                        tasks.push(TranslationTask::Example {
                            meaning_idx: m_idx,
                            def_idx: d_idx,
                            text: example.clone(),
                        });
                    }
                }
            }
        }

        let total = tasks.len() as u32;
        let mut translated = 0u32;

        // 3. 逐个执行翻译（通过 TranslationService 统一限流）
        for task in tasks {
            let field_name = task.field_name();
            let text = task.text();

            // 检查缓存
            let hash = hash_text(text);
            let cached = self.dict_db.get_translation(&hash, "en", "zh").ok().flatten();

            let translated_text = if let Some(cached) = cached {
                Some(cached)
            } else {
                // 调用翻译服务（自动限流）
                match self.translation_service.translate_with_langs(text, "en", "zh").await {
                    Ok(result) => {
                        // 缓存翻译结果
                        let _ = self
                            .dict_db
                            .insert_translation(text, &hash, &result, "en", "zh");
                        Some(result)
                    }
                    Err(_) => None,
                }
            };

            // 更新数据库
            if let Some(ref translated_str) = translated_text {
                if let Err(e) = self.dict_db.update_word_field(&word, &field_name, translated_str) {
                    log::warn!("Failed to update word field: {}", e);
                    continue;
                }

                translated += 1;

                // 发送事件通知前端
                let _ = self.app_handle.emit(
                    EVENT_FIELD_TRANSLATED,
                    FieldTranslatedEvent {
                        word: word.clone(),
                        field: field_name,
                    },
                );
            }
        }

        // 4. 全部完成后更新状态并发送完成事件
        let _ = self.dict_db.mark_translation_completed(&word);

        // 注意：不再需要手动同步收藏表，因为 list_favorites 使用 JOIN 查询
        // 会自动从词典表获取最新的翻译数据

        let _ = self.app_handle.emit(
            EVENT_TRANSLATION_DONE,
            TranslationDoneEvent {
                word,
                total,
                translated,
                success: translated > 0,
            },
        );
    }
}
