use crate::config::{load_app_config, ConfigDir};
use crate::dictionary::db::hash_text;
use crate::dictionary::{DictionaryDb, DictionaryRouter, FavoriteWord, ProviderInfo, ReviewSession, ReviewStats, TranslationWorker, WordEntry};
use crate::task_manager::TaskManager;
use crate::translator::TranslationService;
use std::collections::HashMap;
use std::sync::Arc;
use tauri::AppHandle;

/// 查询单词（立即返回，异步翻译）
#[tauri::command]
pub async fn word_lookup(
    app_handle: AppHandle,
    config_dir: tauri::State<'_, ConfigDir>,
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    dict_router: tauri::State<'_, Arc<DictionaryRouter>>,
    translation_service: tauri::State<'_, Arc<TranslationService>>,
    word: String,
    provider: Option<String>,
) -> Result<WordEntry, String> {
    let word = word.to_lowercase().trim().to_string();
    if word.is_empty() {
        return Err("Word cannot be empty".to_string());
    }

    // 获取用户配置的词典提供者
    let provider_id = provider.or_else(|| {
        load_app_config(&config_dir.0)
            .ok()
            .map(|c| c.dict.provider)
    });

    // 1. 检查数据库缓存（考虑词典来源）
    if let Ok(Some(cached)) = dict_db.get_word(&word) {
        // 如果缓存来源与当前选择的提供者匹配，且已翻译完成，直接返回
        let cache_matches_provider = provider_id
            .as_ref()
            .map(|p| cached.data_source == *p)
            .unwrap_or(true);

        if cache_matches_provider && cached.translation_completed {
            return Ok(cached);
        }

        // 如果来源匹配但未翻译完成，启动异步翻译并返回
        if cache_matches_provider {
            spawn_translation_task(&app_handle, &dict_db, &translation_service, &word, cached.clone()).await;
            return Ok(cached);
        }
        // 如果来源不匹配，继续查询新的词典源
    }

    // 2. 使用词典路由器查询
    let entry = dict_router
        .lookup(&word, provider_id.as_deref())
        .await
        .map_err(|e| e.to_string())?;

    // 3. 立即存入数据库（未翻译状态）
    dict_db
        .upsert_word(&word, &entry)
        .map_err(|e| e.to_string())?;

    // 4. 启动异步翻译任务
    spawn_translation_task(&app_handle, &dict_db, &translation_service, &word, entry.clone()).await;

    // 5. 立即返回（英文释义 + 空中文）
    Ok(entry)
}

/// 获取可用的词典提供者列表
#[tauri::command]
pub async fn list_dict_providers(
    dict_router: tauri::State<'_, Arc<DictionaryRouter>>,
) -> Result<Vec<ProviderInfo>, String> {
    Ok(dict_router.list_providers())
}

/// 获取当前配置的词典提供者
#[tauri::command]
pub async fn get_dict_provider(
    config_dir: tauri::State<'_, ConfigDir>,
) -> Result<String, String> {
    let config = load_app_config(&config_dir.0).map_err(|e| e.to_string())?;
    Ok(config.dict.provider)
}

/// 启动异步翻译任务
async fn spawn_translation_task(
    app_handle: &AppHandle,
    dict_db: &Arc<DictionaryDb>,
    translation_service: &Arc<crate::translator::TranslationService>,
    word: &str,
    entry: WordEntry,
) {
    // 检查翻译服务是否可用
    if !translation_service.is_available().await {
        return; // 无翻译服务，不启动翻译
    }

    // 创建翻译工作器并启动任务
    let worker = TranslationWorker::new(
        app_handle.clone(),
        dict_db.clone(),
        translation_service.clone(),
    );
    worker.spawn_translation(word.to_string(), entry);
}

/// 翻译文本（带缓存）
/// source_lang 和 target_lang 用于指定翻译语言对
#[tauri::command]
pub async fn translate_cached(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    manager: tauri::State<'_, TaskManager>,
    text: String,
    source_lang: Option<String>,
    target_lang: Option<String>,
) -> Result<String, String> {
    let source_lang = source_lang.unwrap_or_else(|| "en".to_string());
    let target_lang = target_lang.unwrap_or_else(|| "zh".to_string());
    let hash = hash_text(&text);

    // 1. 检查数据库缓存
    if let Ok(Some(cached)) = dict_db.get_translation(&hash, &source_lang, &target_lang) {
        return Ok(cached);
    }

    // 2. 使用翻译服务翻译
    let translation_service = manager.get_translation_service();
    if !translation_service.is_available().await {
        return Err("Translator not configured".to_string());
    }

    // 3. 调用翻译服务（使用传入的语言对）
    let translated = translation_service
        .translate_with_langs(&text, &source_lang, &target_lang)
        .await
        .map_err(|e| e.to_string())?;

    // 4. 存入数据库
    dict_db
        .insert_translation(&text, &hash, &translated, &source_lang, &target_lang)
        .map_err(|e| e.to_string())?;

    Ok(translated)
}

/// 批量翻译（用于一次性翻译多个释义）
#[tauri::command]
pub async fn translate_batch(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    manager: tauri::State<'_, TaskManager>,
    texts: Vec<String>,
    source_lang: Option<String>,
    target_lang: Option<String>,
) -> Result<Vec<Option<String>>, String> {
    let source_lang = source_lang.unwrap_or_else(|| "en".to_string());
    let target_lang = target_lang.unwrap_or_else(|| "zh".to_string());

    let mut results = Vec::with_capacity(texts.len());

    for text in texts {
        let hash = hash_text(&text);

        // 检查缓存
        if let Ok(Some(cached)) = dict_db.get_translation(&hash, &source_lang, &target_lang) {
            results.push(Some(cached));
            continue;
        }

        // 使用翻译服务翻译
        let translation_service = manager.get_translation_service();
        if translation_service.is_available().await {
            match translation_service.translate_with_langs(&text, &source_lang, &target_lang).await {
                Ok(translated) => {
                    let _ = dict_db.insert_translation(
                        &text,
                        &hash,
                        &translated,
                        &source_lang,
                        &target_lang,
                    );
                    results.push(Some(translated));
                }
                Err(_) => {
                    results.push(None);
                }
            }
        } else {
            results.push(None);
        }
    }

    Ok(results)
}

// ========== 收藏功能 ==========

/// 收藏/取消收藏单词（toggle）
#[tauri::command]
pub async fn toggle_favorite(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    word: String,
    entry: Option<WordEntry>,
) -> Result<bool, String> {
    let word = word.to_lowercase().trim().to_string();
    if word.is_empty() {
        return Err("Word cannot be empty".to_string());
    }

    // 检查是否已收藏
    let is_favorited = dict_db.is_favorited(&word).map_err(|e| e.to_string())?;

    if is_favorited {
        // 取消收藏
        dict_db.remove_favorite(&word).map_err(|e| e.to_string())?;
        Ok(false)
    } else {
        // 添加收藏
        dict_db
            .add_favorite(&word, entry.as_ref())
            .map_err(|e| e.to_string())?;
        Ok(true)
    }
}

/// 检查单词是否已收藏
#[tauri::command]
pub async fn is_word_favorited(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    word: String,
) -> Result<bool, String> {
    dict_db
        .is_favorited(&word)
        .map_err(|e| e.to_string())
}

/// 批量检查收藏状态
#[tauri::command]
pub async fn get_favorites_batch(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    words: Vec<String>,
) -> Result<HashMap<String, bool>, String> {
    let results = dict_db
        .get_favorites_batch(&words)
        .map_err(|e| e.to_string())?;
    
    Ok(results.into_iter().collect())
}

/// 获取收藏列表
#[tauri::command]
pub async fn list_favorites(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    offset: Option<u32>,
    limit: Option<u32>,
) -> Result<Vec<FavoriteWord>, String> {
    let offset = offset.unwrap_or(0);
    let limit = limit.unwrap_or(50);
    
    dict_db
        .list_favorites(offset, limit)
        .map_err(|e| e.to_string())
}

/// 更新收藏笔记
#[tauri::command]
pub async fn update_favorite_note(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    word: String,
    note: String,
) -> Result<bool, String> {
    dict_db
        .update_favorite_note(&word, &note)
        .map_err(|e| e.to_string())
}

/// 记录复习
#[tauri::command]
pub async fn record_review(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    word: String,
) -> Result<bool, String> {
    dict_db
        .record_review(&word)
        .map_err(|e| e.to_string())
}

/// 获取收藏总数
#[tauri::command]
pub async fn count_favorites(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
) -> Result<u32, String> {
    dict_db
        .count_favorites()
        .map_err(|e| e.to_string())
}

// ========== 复习功能 ==========

/// 获取待复习单词
#[tauri::command]
pub async fn get_words_for_review(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    limit: Option<u32>,
) -> Result<Vec<FavoriteWord>, String> {
    let limit = limit.unwrap_or(20);
    dict_db
        .get_words_for_review(limit)
        .map_err(|e| e.to_string())
}

/// 开始复习会话
#[tauri::command]
pub async fn start_review_session(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    mode: String,
    word_count: i32,
) -> Result<i64, String> {
    dict_db
        .start_review_session(&mode, word_count)
        .map_err(|e| e.to_string())
}

/// 记录复习反馈
#[tauri::command]
pub async fn record_review_feedback(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    session_id: i64,
    word: String,
    feedback: i32,
    response_time_ms: Option<i32>,
) -> Result<FavoriteWord, String> {
    dict_db
        .record_review_feedback(session_id, &word, feedback, response_time_ms.unwrap_or(0))
        .map_err(|e| e.to_string())
}

/// 结束复习会话
#[tauri::command]
pub async fn finish_review_session(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
    session_id: i64,
) -> Result<ReviewSession, String> {
    dict_db
        .finish_review_session(session_id)
        .map_err(|e| e.to_string())
}

/// 获取复习统计
#[tauri::command]
pub async fn get_review_stats(
    dict_db: tauri::State<'_, Arc<DictionaryDb>>,
) -> Result<ReviewStats, String> {
    dict_db
        .get_review_stats()
        .map_err(|e| e.to_string())
}
