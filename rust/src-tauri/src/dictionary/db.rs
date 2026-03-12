use anyhow::Result;
use rusqlite::{params, Connection};
use std::path::Path;
use std::sync::Mutex;

use super::types::WordEntry;

const WORD_CACHE_TTL_DAYS: i64 = 7;
const TRANSLATION_CACHE_TTL_DAYS: i64 = 30;

pub struct DictionaryDb {
    conn: Mutex<Connection>,
}

impl DictionaryDb {
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self> {
        let conn = Connection::open(path)?;
        let db = Self {
            conn: Mutex::new(conn),
        };
        db.init_tables()?;
        Ok(db)
    }

    fn init_tables(&self) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        
        // 创建基础表
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS word_dictionary (
                word TEXT PRIMARY KEY NOT NULL,
                phonetic_uk TEXT,
                phonetic_us TEXT,
                audio_url_uk TEXT,
                audio_url_us TEXT,
                raw_json TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                summary_zh TEXT,
                translation_completed INTEGER DEFAULT 0,
                data_source TEXT DEFAULT 'free_dictionary_api'
            );

            CREATE TABLE IF NOT EXISTS translation_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_text TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                source_lang TEXT DEFAULT 'en',
                target_lang TEXT DEFAULT 'zh',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_hash, source_lang, target_lang)
            );

            CREATE INDEX IF NOT EXISTS idx_translation_hash 
                ON translation_cache(source_hash, source_lang, target_lang);

            CREATE TABLE IF NOT EXISTS word_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL UNIQUE,
                phonetic TEXT,
                meanings_json TEXT,
                note TEXT DEFAULT '',
                review_count INTEGER DEFAULT 0,
                last_review_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_favorites_word ON word_favorites(word);
            CREATE INDEX IF NOT EXISTS idx_favorites_created ON word_favorites(created_at DESC);

            CREATE TABLE IF NOT EXISTS review_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                mode TEXT NOT NULL,
                total_words INTEGER,
                completed_words INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                wrong_count INTEGER DEFAULT 0,
                fuzzy_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS review_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                word TEXT NOT NULL,
                feedback INTEGER NOT NULL,
                response_time_ms INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES review_sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_review_records_word ON review_records(word);
            CREATE INDEX IF NOT EXISTS idx_review_records_session ON review_records(session_id);
            "#,
        )?;

        // 迁移：为旧表添加新列（忽略已存在的错误）
        let migrations = [
            // word_favorites 迁移
            "ALTER TABLE word_favorites ADD COLUMN mastery_level INTEGER DEFAULT 0",
            "ALTER TABLE word_favorites ADD COLUMN next_review_at TEXT",
            "ALTER TABLE word_favorites ADD COLUMN last_feedback INTEGER",
            "ALTER TABLE word_favorites ADD COLUMN consecutive_correct INTEGER DEFAULT 0",
            "ALTER TABLE word_favorites ADD COLUMN summary_zh TEXT",
            // word_dictionary 迁移
            "ALTER TABLE word_dictionary ADD COLUMN summary_zh TEXT",
            "ALTER TABLE word_dictionary ADD COLUMN translation_completed INTEGER DEFAULT 0",
            "ALTER TABLE word_dictionary ADD COLUMN data_source TEXT DEFAULT 'free_dictionary_api'",
        ];

        for migration in migrations {
            let _ = conn.execute(migration, []);
        }

        // 创建索引（忽略已存在的错误）
        let _ = conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_favorites_next_review ON word_favorites(next_review_at)",
            [],
        );

        Ok(())
    }

    /// 获取缓存的单词条目
    pub fn get_word(&self, word: &str) -> Result<Option<WordEntry>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT raw_json, fetched_at FROM word_dictionary WHERE word = ?1",
        )?;

        let result = stmt.query_row(params![word.to_lowercase()], |row| {
            let raw_json: String = row.get(0)?;
            let fetched_at: String = row.get(1)?;
            Ok((raw_json, fetched_at))
        });

        match result {
            Ok((raw_json, fetched_at)) => {
                if Self::is_word_expired(&fetched_at) {
                    return Ok(None);
                }
                let entry: WordEntry = serde_json::from_str(&raw_json)
                    .map_err(|e| rusqlite::Error::ToSqlConversionFailure(Box::new(e)))?;
                Ok(Some(entry))
            }
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(e.into()),
        }
    }

    /// 插入或更新单词条目
    pub fn upsert_word(&self, word: &str, entry: &WordEntry) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        let raw_json = serde_json::to_string(entry)?;

        let phonetic_uk = entry
            .phonetics
            .iter()
            .find(|p| p.region.as_deref() == Some("uk"))
            .and_then(|p| p.text.clone());
        let phonetic_us = entry
            .phonetics
            .iter()
            .find(|p| p.region.as_deref() == Some("us"))
            .and_then(|p| p.text.clone());
        let audio_url_uk = entry
            .phonetics
            .iter()
            .find(|p| p.region.as_deref() == Some("uk"))
            .and_then(|p| p.audio_url.clone());
        let audio_url_us = entry
            .phonetics
            .iter()
            .find(|p| p.region.as_deref() == Some("us"))
            .and_then(|p| p.audio_url.clone());

        conn.execute(
            r#"
            INSERT OR REPLACE INTO word_dictionary 
            (word, phonetic_uk, phonetic_us, audio_url_uk, audio_url_us, raw_json, fetched_at, summary_zh, translation_completed, data_source)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)
            "#,
            params![
                word.to_lowercase(),
                phonetic_uk,
                phonetic_us,
                audio_url_uk,
                audio_url_us,
                raw_json,
                entry.fetched_at,
                entry.summary_zh,
                entry.translation_completed as i32,
                entry.data_source,
            ],
        )?;
        Ok(())
    }

    /// 更新单词的单个翻译字段
    /// field 格式: "summary_zh" | "def_{m}_{d}" | "ex_{m}_{d}"
    pub fn update_word_field(&self, word: &str, field: &str, value: &str) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        let word_lower = word.to_lowercase();

        // 读取当前 raw_json
        let raw_json: String = conn.query_row(
            "SELECT raw_json FROM word_dictionary WHERE word = ?1",
            params![word_lower],
            |row| row.get(0),
        )?;

        let mut entry: WordEntry = serde_json::from_str(&raw_json)?;

        // 根据 field 更新对应字段
        if field == "summary_zh" {
            entry.summary_zh = Some(value.to_string());
        } else if field.starts_with("def_") {
            // 解析 def_{m}_{d}
            let parts: Vec<&str> = field.split('_').collect();
            if parts.len() == 3 {
                if let (Ok(m_idx), Ok(d_idx)) = (parts[1].parse::<usize>(), parts[2].parse::<usize>()) {
                    if let Some(meaning) = entry.meanings.get_mut(m_idx) {
                        if let Some(def) = meaning.definitions.get_mut(d_idx) {
                            def.chinese = Some(value.to_string());
                        }
                    }
                }
            }
        } else if field.starts_with("ex_") {
            // 解析 ex_{m}_{d}
            let parts: Vec<&str> = field.split('_').collect();
            if parts.len() == 3 {
                if let (Ok(m_idx), Ok(d_idx)) = (parts[1].parse::<usize>(), parts[2].parse::<usize>()) {
                    if let Some(meaning) = entry.meanings.get_mut(m_idx) {
                        if let Some(def) = meaning.definitions.get_mut(d_idx) {
                            def.example_chinese = Some(value.to_string());
                        }
                    }
                }
            }
        }

        // 写回数据库
        let new_raw_json = serde_json::to_string(&entry)?;
        conn.execute(
            "UPDATE word_dictionary SET raw_json = ?1, summary_zh = ?2 WHERE word = ?3",
            params![new_raw_json, entry.summary_zh, word_lower],
        )?;

        Ok(())
    }

    /// 标记单词翻译完成
    pub fn mark_translation_completed(&self, word: &str) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        let word_lower = word.to_lowercase();

        // 读取并更新 raw_json 中的 translation_completed
        let raw_json: String = conn.query_row(
            "SELECT raw_json FROM word_dictionary WHERE word = ?1",
            params![word_lower],
            |row| row.get(0),
        )?;

        let mut entry: WordEntry = serde_json::from_str(&raw_json)?;
        entry.translation_completed = true;

        let new_raw_json = serde_json::to_string(&entry)?;
        conn.execute(
            "UPDATE word_dictionary SET raw_json = ?1, translation_completed = 1 WHERE word = ?2",
            params![new_raw_json, word_lower],
        )?;

        Ok(())
    }

    /// 获取缓存的翻译
    pub fn get_translation(
        &self,
        source_hash: &str,
        source_lang: &str,
        target_lang: &str,
    ) -> Result<Option<String>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            r#"
            SELECT translated_text, created_at 
            FROM translation_cache 
            WHERE source_hash = ?1 AND source_lang = ?2 AND target_lang = ?3
            "#,
        )?;

        let result = stmt.query_row(
            params![source_hash, source_lang, target_lang],
            |row| {
                let translated: String = row.get(0)?;
                let created_at: String = row.get(1)?;
                Ok((translated, created_at))
            },
        );

        match result {
            Ok((translated, created_at)) => {
                if Self::is_translation_expired(&created_at) {
                    return Ok(None);
                }
                Ok(Some(translated))
            }
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(e.into()),
        }
    }

    /// 插入翻译缓存
    pub fn insert_translation(
        &self,
        source_text: &str,
        source_hash: &str,
        translated_text: &str,
        source_lang: &str,
        target_lang: &str,
    ) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            r#"
            INSERT OR REPLACE INTO translation_cache 
            (source_text, source_hash, translated_text, source_lang, target_lang, created_at)
            VALUES (?1, ?2, ?3, ?4, ?5, datetime('now'))
            "#,
            params![source_text, source_hash, translated_text, source_lang, target_lang],
        )?;
        Ok(())
    }

    fn is_word_expired(fetched_at: &str) -> bool {
        if let Ok(fetched) = chrono::NaiveDateTime::parse_from_str(fetched_at, "%Y-%m-%d %H:%M:%S")
        {
            let now = chrono::Local::now().naive_local();
            let diff = now.signed_duration_since(fetched);
            return diff.num_days() > WORD_CACHE_TTL_DAYS;
        }
        true
    }

    fn is_translation_expired(created_at: &str) -> bool {
        if let Ok(created) = chrono::NaiveDateTime::parse_from_str(created_at, "%Y-%m-%d %H:%M:%S")
        {
            let now = chrono::Local::now().naive_local();
            let diff = now.signed_duration_since(created);
            return diff.num_days() > TRANSLATION_CACHE_TTL_DAYS;
        }
        true
    }

    // ========== 收藏功能 ==========

    /// 收藏单词（如果已存在则返回 false）
    pub fn add_favorite(&self, word: &str, entry: Option<&WordEntry>) -> Result<bool> {
        let conn = self.conn.lock().unwrap();
        let word_lower = word.to_lowercase();

        let (phonetic, meanings_json, summary_zh) = if let Some(e) = entry {
            let phonetic = e.phonetics.iter().find(|p| p.text.is_some()).and_then(|p| p.text.clone());
            let meanings_json = serde_json::to_string(&e.meanings).ok();
            (phonetic, meanings_json, e.summary_zh.clone())
        } else {
            (None, None, None)
        };

        let result = conn.execute(
            r#"
            INSERT OR IGNORE INTO word_favorites (word, phonetic, meanings_json, summary_zh, created_at, updated_at)
            VALUES (?1, ?2, ?3, ?4, datetime('now'), datetime('now'))
            "#,
            params![word_lower, phonetic, meanings_json, summary_zh],
        )?;

        Ok(result > 0)
    }

    /// 取消收藏
    pub fn remove_favorite(&self, word: &str) -> Result<bool> {
        let conn = self.conn.lock().unwrap();
        let result = conn.execute(
            "DELETE FROM word_favorites WHERE word = ?1",
            params![word.to_lowercase()],
        )?;
        Ok(result > 0)
    }

    /// 更新收藏单词的释义数据（翻译完成后调用）
    pub fn update_favorite_meanings(&self, word: &str, entry: &WordEntry) -> Result<bool> {
        let conn = self.conn.lock().unwrap();
        let word_lower = word.to_lowercase();

        let meanings_json = serde_json::to_string(&entry.meanings).ok();
        
        let result = conn.execute(
            r#"
            UPDATE word_favorites 
            SET meanings_json = ?2, summary_zh = ?3, updated_at = datetime('now')
            WHERE word = ?1
            "#,
            params![word_lower, meanings_json, entry.summary_zh],
        )?;

        Ok(result > 0)
    }

    /// 检查是否已收藏
    pub fn is_favorited(&self, word: &str) -> Result<bool> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare("SELECT 1 FROM word_favorites WHERE word = ?1")?;
        let exists = stmt.exists(params![word.to_lowercase()])?;
        Ok(exists)
    }

    /// 批量检查收藏状态
    pub fn get_favorites_batch(&self, words: &[String]) -> Result<Vec<(String, bool)>> {
        let conn = self.conn.lock().unwrap();
        let mut results = Vec::with_capacity(words.len());

        for word in words {
            let word_lower = word.to_lowercase();
            let mut stmt = conn.prepare("SELECT 1 FROM word_favorites WHERE word = ?1")?;
            let exists = stmt.exists(params![&word_lower])?;
            results.push((word_lower, exists));
        }

        Ok(results)
    }

    /// 获取收藏列表（从词典表实时获取最新释义，避免数据不一致）
    pub fn list_favorites(&self, offset: u32, limit: u32) -> Result<Vec<FavoriteWord>> {
        let conn = self.conn.lock().unwrap();
        // 使用 LEFT JOIN 从词典表获取最新释义数据
        // word_dictionary 表使用 raw_json 存储完整 WordEntry，需要解析
        let mut stmt = conn.prepare(
            r#"
            SELECT 
                f.word,
                f.phonetic,
                f.meanings_json,
                COALESCE(d.summary_zh, f.summary_zh) as summary_zh,
                f.note,
                f.review_count,
                f.last_review_at,
                f.created_at,
                f.mastery_level,
                f.next_review_at,
                f.last_feedback,
                f.consecutive_correct,
                d.raw_json
            FROM word_favorites f
            LEFT JOIN word_dictionary d ON f.word = d.word
            ORDER BY f.created_at DESC
            LIMIT ?1 OFFSET ?2
            "#,
        )?;

        let rows = stmt.query_map(params![limit, offset], |row| {
            let word: String = row.get(0)?;
            let fallback_phonetic: Option<String> = row.get(1)?;
            let fallback_meanings_json: Option<String> = row.get(2)?;
            let summary_zh: Option<String> = row.get(3)?;
            let raw_json: Option<String> = row.get(12)?;

            // 优先从词典表的 raw_json 解析最新数据
            let (phonetic, meanings_json) = if let Some(json) = raw_json {
                if let Ok(entry) = serde_json::from_str::<WordEntry>(&json) {
                    let phonetic = entry.phonetics.iter()
                        .find(|p| p.text.is_some())
                        .and_then(|p| p.text.clone());
                    let meanings = serde_json::to_string(&entry.meanings).ok();
                    (phonetic.or(fallback_phonetic), meanings.or(fallback_meanings_json))
                } else {
                    (fallback_phonetic, fallback_meanings_json)
                }
            } else {
                (fallback_phonetic, fallback_meanings_json)
            };

            Ok(FavoriteWord {
                word,
                phonetic,
                meanings_json,
                summary_zh,
                note: row.get(4)?,
                review_count: row.get(5)?,
                last_review_at: row.get(6)?,
                created_at: row.get(7)?,
                mastery_level: row.get::<_, Option<i32>>(8)?.unwrap_or(0),
                next_review_at: row.get(9)?,
                last_feedback: row.get(10)?,
                consecutive_correct: row.get::<_, Option<i32>>(11)?.unwrap_or(0),
            })
        })?;

        let mut favorites = Vec::new();
        for row in rows {
            favorites.push(row?);
        }
        Ok(favorites)
    }

    /// 更新收藏笔记
    pub fn update_favorite_note(&self, word: &str, note: &str) -> Result<bool> {
        let conn = self.conn.lock().unwrap();
        let result = conn.execute(
            r#"
            UPDATE word_favorites 
            SET note = ?1, updated_at = datetime('now')
            WHERE word = ?2
            "#,
            params![note, word.to_lowercase()],
        )?;
        Ok(result > 0)
    }

    /// 记录复习
    pub fn record_review(&self, word: &str) -> Result<bool> {
        let conn = self.conn.lock().unwrap();
        let result = conn.execute(
            r#"
            UPDATE word_favorites 
            SET review_count = review_count + 1, 
                last_review_at = datetime('now'),
                updated_at = datetime('now')
            WHERE word = ?1
            "#,
            params![word.to_lowercase()],
        )?;
        Ok(result > 0)
    }

    /// 获取收藏总数
    pub fn count_favorites(&self) -> Result<u32> {
        let conn = self.conn.lock().unwrap();
        let count: u32 = conn.query_row(
            "SELECT COUNT(*) FROM word_favorites",
            [],
            |row| row.get(0),
        )?;
        Ok(count)
    }

    // ========== 复习功能 ==========

    /// 获取待复习单词
    pub fn get_words_for_review(&self, limit: u32) -> Result<Vec<FavoriteWord>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            r#"
            SELECT word, phonetic, meanings_json, summary_zh, note, review_count, last_review_at, created_at,
                   mastery_level, next_review_at, last_feedback, consecutive_correct
            FROM word_favorites
            WHERE mastery_level < 2
              AND (next_review_at IS NULL OR next_review_at <= datetime('now'))
            ORDER BY 
                CASE WHEN next_review_at IS NULL THEN 0 ELSE 1 END,
                next_review_at ASC
            LIMIT ?1
            "#,
        )?;

        let rows = stmt.query_map(params![limit], |row| {
            Ok(FavoriteWord {
                word: row.get(0)?,
                phonetic: row.get(1)?,
                meanings_json: row.get(2)?,
                summary_zh: row.get(3)?,
                note: row.get(4)?,
                review_count: row.get(5)?,
                last_review_at: row.get(6)?,
                created_at: row.get(7)?,
                mastery_level: row.get::<_, Option<i32>>(8)?.unwrap_or(0),
                next_review_at: row.get(9)?,
                last_feedback: row.get(10)?,
                consecutive_correct: row.get::<_, Option<i32>>(11)?.unwrap_or(0),
            })
        })?;

        let mut favorites = Vec::new();
        for row in rows {
            favorites.push(row?);
        }
        Ok(favorites)
    }

    /// 开始复习会话
    pub fn start_review_session(&self, mode: &str, total_words: i32) -> Result<i64> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            r#"
            INSERT INTO review_sessions (started_at, mode, total_words)
            VALUES (datetime('now'), ?1, ?2)
            "#,
            params![mode, total_words],
        )?;
        Ok(conn.last_insert_rowid())
    }

    /// 记录复习反馈并更新单词状态
    pub fn record_review_feedback(
        &self,
        session_id: i64,
        word: &str,
        feedback: i32,
        response_time_ms: i32,
    ) -> Result<FavoriteWord> {
        let conn = self.conn.lock().unwrap();
        let word_lower = word.to_lowercase();

        // 插入复习记录
        conn.execute(
            r#"
            INSERT INTO review_records (session_id, word, feedback, response_time_ms)
            VALUES (?1, ?2, ?3, ?4)
            "#,
            params![session_id, word_lower, feedback, response_time_ms],
        )?;

        // 获取当前状态
        let (current_consecutive, _current_mastery): (i32, i32) = conn.query_row(
            "SELECT consecutive_correct, mastery_level FROM word_favorites WHERE word = ?1",
            params![word_lower],
            |row| Ok((row.get(0)?, row.get(1)?)),
        ).unwrap_or((0, 0));

        // 计算新状态（艾宾浩斯算法）
        let (new_consecutive, new_mastery, next_review_days) = match feedback {
            2 => {
                // 认识
                let new_consecutive = current_consecutive + 1;
                if new_consecutive >= 5 {
                    (new_consecutive, 2, 30) // 已掌握
                } else {
                    let days = [1, 3, 7, 14, 21][new_consecutive.min(4) as usize];
                    (new_consecutive, 1, days)
                }
            }
            1 => {
                // 模糊
                (0, 1, 1)
            }
            _ => {
                // 不认识
                (0, 0, 0) // 立即再次出现
            }
        };

        // 更新单词状态
        conn.execute(
            r#"
            UPDATE word_favorites SET
                review_count = review_count + 1,
                last_review_at = datetime('now'),
                last_feedback = ?1,
                consecutive_correct = ?2,
                mastery_level = ?3,
                next_review_at = datetime('now', '+' || ?4 || ' days'),
                updated_at = datetime('now')
            WHERE word = ?5
            "#,
            params![feedback, new_consecutive, new_mastery, next_review_days, word_lower],
        )?;

        // 更新会话统计
        let count_field = match feedback {
            2 => "correct_count",
            1 => "fuzzy_count",
            _ => "wrong_count",
        };
        conn.execute(
            &format!(
                "UPDATE review_sessions SET completed_words = completed_words + 1, {} = {} + 1 WHERE id = ?1",
                count_field, count_field
            ),
            params![session_id],
        )?;

        // 返回更新后的单词
        drop(conn);
        self.get_favorite_word(&word_lower)
    }

    /// 获取单个收藏单词
    fn get_favorite_word(&self, word: &str) -> Result<FavoriteWord> {
        let conn = self.conn.lock().unwrap();
        conn.query_row(
            r#"
            SELECT word, phonetic, meanings_json, summary_zh, note, review_count, last_review_at, created_at,
                   mastery_level, next_review_at, last_feedback, consecutive_correct
            FROM word_favorites WHERE word = ?1
            "#,
            params![word],
            |row| {
                Ok(FavoriteWord {
                    word: row.get(0)?,
                    phonetic: row.get(1)?,
                    meanings_json: row.get(2)?,
                    summary_zh: row.get(3)?,
                    note: row.get(4)?,
                    review_count: row.get(5)?,
                    last_review_at: row.get(6)?,
                    created_at: row.get(7)?,
                    mastery_level: row.get::<_, Option<i32>>(8)?.unwrap_or(0),
                    next_review_at: row.get(9)?,
                    last_feedback: row.get(10)?,
                    consecutive_correct: row.get::<_, Option<i32>>(11)?.unwrap_or(0),
                })
            },
        ).map_err(Into::into)
    }

    /// 结束复习会话
    pub fn finish_review_session(&self, session_id: i64) -> Result<ReviewSession> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "UPDATE review_sessions SET finished_at = datetime('now') WHERE id = ?1",
            params![session_id],
        )?;

        conn.query_row(
            r#"
            SELECT id, started_at, finished_at, mode, total_words, completed_words,
                   correct_count, wrong_count, fuzzy_count
            FROM review_sessions WHERE id = ?1
            "#,
            params![session_id],
            |row| {
                Ok(ReviewSession {
                    id: row.get(0)?,
                    started_at: row.get(1)?,
                    finished_at: row.get(2)?,
                    mode: row.get(3)?,
                    total_words: row.get(4)?,
                    completed_words: row.get(5)?,
                    correct_count: row.get(6)?,
                    wrong_count: row.get(7)?,
                    fuzzy_count: row.get(8)?,
                })
            },
        ).map_err(Into::into)
    }

    /// 获取复习统计
    pub fn get_review_stats(&self) -> Result<ReviewStats> {
        let conn = self.conn.lock().unwrap();

        let total_favorites: u32 = conn.query_row(
            "SELECT COUNT(*) FROM word_favorites",
            [],
            |row| row.get(0),
        )?;

        let mastered_count: u32 = conn.query_row(
            "SELECT COUNT(*) FROM word_favorites WHERE mastery_level = 2",
            [],
            |row| row.get(0),
        )?;

        let reviewing_count: u32 = conn.query_row(
            "SELECT COUNT(*) FROM word_favorites WHERE mastery_level = 1",
            [],
            |row| row.get(0),
        )?;

        let pending_count: u32 = conn.query_row(
            "SELECT COUNT(*) FROM word_favorites WHERE mastery_level = 0",
            [],
            |row| row.get(0),
        )?;

        let today_reviewed: u32 = conn.query_row(
            "SELECT COUNT(*) FROM review_records WHERE date(created_at) = date('now')",
            [],
            |row| row.get(0),
        )?;

        let total_reviews: u32 = conn.query_row(
            "SELECT COUNT(*) FROM review_records",
            [],
            |row| row.get(0),
        )?;

        Ok(ReviewStats {
            total_favorites,
            mastered_count,
            reviewing_count,
            pending_count,
            today_reviewed,
            total_reviews,
        })
    }
}

/// 收藏单词数据结构
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct FavoriteWord {
    pub word: String,
    pub phonetic: Option<String>,
    pub meanings_json: Option<String>,
    pub summary_zh: Option<String>,
    pub note: Option<String>,
    pub review_count: i32,
    pub last_review_at: Option<String>,
    pub created_at: String,
    pub mastery_level: i32,
    pub next_review_at: Option<String>,
    pub last_feedback: Option<i32>,
    pub consecutive_correct: i32,
}

/// 复习会话数据结构
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ReviewSession {
    pub id: i64,
    pub started_at: String,
    pub finished_at: Option<String>,
    pub mode: String,
    pub total_words: i32,
    pub completed_words: i32,
    pub correct_count: i32,
    pub wrong_count: i32,
    pub fuzzy_count: i32,
}

/// 复习统计数据
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ReviewStats {
    pub total_favorites: u32,
    pub mastered_count: u32,
    pub reviewing_count: u32,
    pub pending_count: u32,
    pub today_reviewed: u32,
    pub total_reviews: u32,
}

/// 生成文本哈希（用于翻译缓存 key）
pub fn hash_text(text: &str) -> String {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};

    let mut hasher = DefaultHasher::new();
    text.hash(&mut hasher);
    format!("{:x}", hasher.finish())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_hash_text() {
        let hash1 = hash_text("hello world");
        let hash2 = hash_text("hello world");
        let hash3 = hash_text("hello");

        assert_eq!(hash1, hash2);
        assert_ne!(hash1, hash3);
    }

    #[test]
    fn test_translation_cache() {
        let dir = tempdir().unwrap();
        let db_path = dir.path().join("test.db");
        let db = DictionaryDb::open(&db_path).unwrap();

        let hash = hash_text("hello");
        db.insert_translation("hello", &hash, "你好", "en", "zh")
            .unwrap();

        let result = db.get_translation(&hash, "en", "zh").unwrap();
        assert_eq!(result, Some("你好".to_string()));

        let result2 = db.get_translation(&hash, "en", "ja").unwrap();
        assert_eq!(result2, None);
    }
}
