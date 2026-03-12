use anyhow::{Context, Result};
use chrono::NaiveDateTime;
use rusqlite::{params, Connection};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::path::Path;
use std::sync::Mutex;

pub struct MessageDb {
    conn: Mutex<Connection>,
}

#[derive(Debug, Clone, Serialize)]
pub struct StoredMessage {
    pub id: i64,
    pub chat_name: String,
    pub chat_type: Option<String>,
    pub sender: String,
    pub content: String,
    pub content_en: String,
    pub is_self: bool,
    pub detected_at: String,
    pub image_path: Option<String>,
    pub source: Option<String>,
    pub quality: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ChatSummary {
    pub chat_name: String,
    pub message_count: i64,
    pub last_message_at: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct DbStats {
    pub total_messages: i64,
    pub total_chats: i64,
    pub earliest_message: String,
    pub latest_message: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct CachedTranslation {
    pub translated_text: String,
    pub source_lang: String,
    pub target_lang: String,
    pub updated_at: String,
}

pub(crate) fn content_hash(sender: &str, content: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(sender.as_bytes());
    hasher.update(b"\n");
    hasher.update(content.as_bytes());
    let result = hasher.finalize();
    hex::encode(&result[..8])
}

pub(crate) fn content_only_hash(content: &str) -> String {
    content_hash("", content)
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

fn normalize_for_match(raw: &str) -> String {
    raw.chars()
        .filter(|c| !matches!(c, '\u{200b}' | '\u{200c}' | '\u{200d}' | '\u{feff}'))
        .collect::<String>()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn prefix8_key(raw: &str) -> String {
    normalize_for_match(raw).chars().take(8).collect()
}

fn parse_detected_at(raw: &str) -> Option<NaiveDateTime> {
    NaiveDateTime::parse_from_str(raw, "%Y-%m-%d %H:%M:%S").ok()
}

mod hex {
    pub fn encode(bytes: &[u8]) -> String {
        super::hex_encode(bytes)
    }
}

impl MessageDb {
    pub fn new(path: &Path) -> Result<Self> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).context("create db directory")?;
        }
        let conn = Connection::open(path).context("open sqlite database")?;
        conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")
            .context("set pragmas")?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_name    TEXT NOT NULL,
                sender       TEXT NOT NULL DEFAULT '',
                content      TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                detected_at  TEXT NOT NULL,
                content_en   TEXT NOT NULL DEFAULT '',
                is_self      INTEGER NOT NULL DEFAULT 0,
                image_path   TEXT DEFAULT NULL,
                source       TEXT NOT NULL DEFAULT 'chat',
                quality      TEXT NOT NULL DEFAULT 'high',
                UNIQUE(chat_name, content_hash)
            );
            CREATE INDEX IF NOT EXISTS idx_chat_time ON messages(chat_name, detected_at);
            CREATE INDEX IF NOT EXISTS idx_sender ON messages(sender);
            CREATE INDEX IF NOT EXISTS idx_source_quality ON messages(source, quality, chat_name, detected_at);
            CREATE TABLE IF NOT EXISTS message_translations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash    TEXT NOT NULL,
                source_lang     TEXT NOT NULL,
                target_lang     TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                UNIQUE(content_hash, source_lang, target_lang)
            );
            CREATE INDEX IF NOT EXISTS idx_message_translations_lookup
              ON message_translations(content_hash, source_lang, target_lang);",
        )
        .context("create schema")?;

        // Migrate: add columns for existing databases
        let has_content_en: bool = conn
            .prepare("SELECT content_en FROM messages LIMIT 0")
            .is_ok();
        if !has_content_en {
            let _ = conn.execute_batch(
                "ALTER TABLE messages ADD COLUMN content_en TEXT NOT NULL DEFAULT '';
                 ALTER TABLE messages ADD COLUMN is_self INTEGER NOT NULL DEFAULT 0;",
            );
        }

        let has_image_path: bool = conn
            .prepare("SELECT image_path FROM messages LIMIT 0")
            .is_ok();
        if !has_image_path {
            let _ =
                conn.execute_batch("ALTER TABLE messages ADD COLUMN image_path TEXT DEFAULT NULL;");
        }

        let has_source: bool = conn.prepare("SELECT source FROM messages LIMIT 0").is_ok();
        if !has_source {
            let _ = conn.execute_batch(
                "ALTER TABLE messages ADD COLUMN source TEXT NOT NULL DEFAULT 'chat';",
            );
        }

        let has_quality: bool = conn.prepare("SELECT quality FROM messages LIMIT 0").is_ok();
        if !has_quality {
            let _ = conn.execute_batch(
                "ALTER TABLE messages ADD COLUMN quality TEXT NOT NULL DEFAULT 'high';",
            );
        }

        // Migrate: add chat_type column (nullable, history data will have NULL)
        let has_chat_type: bool = conn.prepare("SELECT chat_type FROM messages LIMIT 0").is_ok();
        if !has_chat_type {
            let _ = conn.execute_batch(
                "ALTER TABLE messages ADD COLUMN chat_type TEXT DEFAULT NULL;",
            );
        }

        Ok(Self {
            conn: Mutex::new(conn),
        })
    }

    /// Insert a message. Returns true if actually inserted (not a duplicate).
    pub fn insert_message(
        &self,
        chat_name: &str,
        sender: &str,
        content: &str,
        content_en: &str,
        is_self: bool,
        detected_at: &str,
        image_path: Option<&str>,
    ) -> Result<bool> {
        self.insert_message_with_meta(
            chat_name,
            None,
            sender,
            content,
            content_en,
            is_self,
            detected_at,
            image_path,
            "chat",
            "high",
        )
    }

    /// Insert a message with explicit source/quality/chat_type metadata.
    pub fn insert_message_with_meta(
        &self,
        chat_name: &str,
        chat_type: Option<&str>,
        sender: &str,
        content: &str,
        content_en: &str,
        is_self: bool,
        detected_at: &str,
        image_path: Option<&str>,
        source: &str,
        quality: &str,
    ) -> Result<bool> {
        let hash = content_hash(sender, content);
        let conn = self.conn.lock().unwrap();
        let rows = conn
            .execute(
                "INSERT OR IGNORE INTO messages (
                    chat_name, chat_type, sender, content, content_hash, detected_at, content_en, is_self, image_path, source, quality
                 ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)",
                params![
                    chat_name,
                    chat_type,
                    sender,
                    content,
                    hash,
                    detected_at,
                    content_en,
                    is_self as i32,
                    image_path,
                    source,
                    quality
                ],
            )
            .context("insert message")?;
        Ok(rows > 0)
    }

    pub fn update_message_translation(
        &self,
        chat_name: &str,
        sender: &str,
        content: &str,
        _detected_at: &str,
        content_en: &str,
    ) -> Result<bool> {
        let hash = content_hash(sender, content);
        let conn = self.conn.lock().unwrap();
        // 使用 chat_name + content_hash 定位消息（不再依赖 detected_at）
        let rows = conn
            .execute(
                "UPDATE messages
                 SET content_en = ?1
                 WHERE chat_name = ?2
                   AND content_hash = ?3
                   AND content_en = ''",
                params![content_en, chat_name, hash],
            )
            .context("update message translation")?;
        Ok(rows > 0)
    }

    pub fn get_cached_translation(
        &self,
        content: &str,
        source_lang: &str,
        target_lang: &str,
    ) -> Result<Option<CachedTranslation>> {
        let hash = content_only_hash(content);
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT translated_text, source_lang, target_lang, updated_at
             FROM message_translations
             WHERE content_hash = ?1 AND source_lang = ?2 AND target_lang = ?3
             LIMIT 1",
        )?;
        let mut rows = stmt.query(params![hash, source_lang, target_lang])?;
        if let Some(row) = rows.next()? {
            return Ok(Some(CachedTranslation {
                translated_text: row.get(0)?,
                source_lang: row.get(1)?,
                target_lang: row.get(2)?,
                updated_at: row.get(3)?,
            }));
        }
        Ok(None)
    }

    pub fn upsert_cached_translation(
        &self,
        content: &str,
        source_lang: &str,
        target_lang: &str,
        translated_text: &str,
    ) -> Result<()> {
        let hash = content_only_hash(content);
        let updated_at = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO message_translations (
                content_hash, source_lang, target_lang, translated_text, updated_at
             ) VALUES (?1, ?2, ?3, ?4, ?5)
             ON CONFLICT(content_hash, source_lang, target_lang)
             DO UPDATE SET translated_text = excluded.translated_text,
                           updated_at = excluded.updated_at",
            params![hash, source_lang, target_lang, translated_text, updated_at],
        )
        .context("upsert cached translation")?;
        Ok(())
    }

    /// Try updating a recent low-quality session_preview row into a corrected high-quality row.
    /// Matching key: same chat + prefix8(content) + short time window.
    pub fn try_correct_preview_row(
        &self,
        chat_name: &str,
        chat_type: Option<&str>,
        content: &str,
        sender: &str,
        content_en: &str,
        is_self: bool,
        image_path: Option<&str>,
        detected_at: &str,
        window_seconds: i64,
    ) -> Result<bool> {
        let target_key = prefix8_key(content);
        if target_key.is_empty() {
            return Ok(false);
        }

        let now = match parse_detected_at(detected_at) {
            Some(ts) => ts,
            None => return Ok(false),
        };

        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, content, detected_at
             FROM messages
             WHERE chat_name = ?1
               AND source = 'session_preview'
               AND quality = 'low'
             ORDER BY id DESC
             LIMIT 30",
        )?;
        let rows = stmt.query_map(params![chat_name], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
            ))
        })?;

        let mut candidate_id: Option<i64> = None;
        for row in rows {
            let (id, row_content, row_time) = row.context("read preview row")?;
            if prefix8_key(&row_content) != target_key {
                continue;
            }
            let Some(row_ts) = parse_detected_at(&row_time) else {
                continue;
            };
            let delta = now.signed_duration_since(row_ts).num_seconds();
            if delta < 0 || delta > window_seconds {
                continue;
            }
            candidate_id = Some(id);
            break;
        }
        drop(stmt);

        let Some(target_id) = candidate_id else {
            return Ok(false);
        };

        let hash = content_hash(sender, content);
        let rows = conn.execute(
            "UPDATE OR IGNORE messages
             SET sender = ?1,
                 content = ?2,
                 content_hash = ?3,
                 detected_at = ?4,
                 content_en = ?5,
                 is_self = ?6,
                 image_path = ?7,
                 chat_type = ?8,
                 source = 'session_corrected',
                 quality = 'high'
             WHERE id = ?9",
            params![
                sender,
                content,
                hash,
                detected_at,
                content_en,
                is_self as i32,
                image_path,
                chat_type,
                target_id
            ],
        )?;
        Ok(rows > 0)
    }

    pub fn query_messages(
        &self,
        chat_name: Option<&str>,
        sender: Option<&str>,
        keyword: Option<&str>,
        limit: i64,
        offset: i64,
    ) -> Result<Vec<StoredMessage>> {
        let conn = self.conn.lock().unwrap();

        let mut sql = String::from(
            "SELECT id, chat_name, chat_type, sender, content, detected_at, content_en, is_self, image_path, source, quality
             FROM messages
             WHERE 1=1",
        );
        let mut param_values: Vec<Box<dyn rusqlite::types::ToSql>> = Vec::new();

        if let Some(cn) = chat_name {
            sql.push_str(" AND chat_name = ?");
            param_values.push(Box::new(cn.to_string()));
        }
        if let Some(s) = sender {
            sql.push_str(" AND sender = ?");
            param_values.push(Box::new(s.to_string()));
        }
        if let Some(kw) = keyword {
            sql.push_str(" AND content LIKE ?");
            param_values.push(Box::new(format!("%{}%", kw)));
        }
        sql.push_str(" ORDER BY detected_at DESC, id DESC LIMIT ? OFFSET ?");
        param_values.push(Box::new(limit));
        param_values.push(Box::new(offset));

        let params_ref: Vec<&dyn rusqlite::types::ToSql> =
            param_values.iter().map(|p| p.as_ref()).collect();

        let mut stmt = conn.prepare(&sql).context("prepare query")?;
        let rows = stmt
            .query_map(params_ref.as_slice(), |row| {
                Ok(StoredMessage {
                    id: row.get(0)?,
                    chat_name: row.get(1)?,
                    chat_type: row.get::<_, Option<String>>(2).unwrap_or(None),
                    sender: row.get(3)?,
                    content: row.get(4)?,
                    detected_at: row.get(5)?,
                    content_en: row.get::<_, String>(6).unwrap_or_default(),
                    is_self: row.get::<_, i32>(7).unwrap_or(0) != 0,
                    image_path: row.get::<_, Option<String>>(8).unwrap_or(None),
                    source: row.get::<_, Option<String>>(9).unwrap_or(None),
                    quality: row.get::<_, Option<String>>(10).unwrap_or(None),
                })
            })
            .context("execute query")?;

        let mut messages = Vec::new();
        for row in rows {
            messages.push(row.context("read row")?);
        }
        Ok(messages)
    }

    pub fn latest_chat_name(&self) -> Result<Option<String>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT chat_name
             FROM messages
             ORDER BY detected_at DESC, id DESC
             LIMIT 1",
        )?;
        let mut rows = stmt.query([])?;
        if let Some(row) = rows.next()? {
            return Ok(Some(row.get(0)?));
        }
        Ok(None)
    }

    /// Return a bag (hash → count) of recent content_hashes for a given chat,
    /// used by reconcile_with_db to detect messages not yet persisted.
    pub fn query_recent_hashes(
        &self,
        chat_name: &str,
        limit: i64,
    ) -> Result<HashMap<String, usize>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT content_hash FROM messages WHERE chat_name = ?1
             ORDER BY detected_at DESC, id DESC LIMIT ?2",
        )?;
        let rows = stmt.query_map(params![chat_name, limit], |row| row.get::<_, String>(0))?;
        let mut bag: HashMap<String, usize> = HashMap::new();
        for row in rows {
            let hash = row.context("read hash row")?;
            *bag.entry(hash).or_default() += 1;
        }
        Ok(bag)
    }

    /// Return two bags for recent rows:
    /// - full hash bag: sender+content hash (stored content_hash)
    /// - content-only bag: hash(content) for fallback matching when sender is unknown
    pub fn query_recent_hashes_dual(
        &self,
        chat_name: &str,
        limit: i64,
    ) -> Result<(HashMap<String, usize>, HashMap<String, usize>)> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT content_hash, content FROM messages WHERE chat_name = ?1
             ORDER BY detected_at DESC, id DESC LIMIT ?2",
        )?;
        let rows = stmt.query_map(params![chat_name, limit], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
        })?;

        let mut full_bag: HashMap<String, usize> = HashMap::new();
        let mut content_bag: HashMap<String, usize> = HashMap::new();
        for row in rows {
            let (full_hash, content) = row.context("read hash row")?;
            *full_bag.entry(full_hash).or_default() += 1;
            *content_bag.entry(content_only_hash(&content)).or_default() += 1;
        }
        Ok((full_bag, content_bag))
    }

    pub fn get_chat_list(&self) -> Result<Vec<ChatSummary>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT chat_name, COUNT(*) as cnt, MAX(detected_at) as last_at
             FROM messages
             GROUP BY chat_name
             ORDER BY last_at DESC",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok(ChatSummary {
                chat_name: row.get(0)?,
                message_count: row.get(1)?,
                last_message_at: row.get(2)?,
            })
        })?;

        let mut chats = Vec::new();
        for row in rows {
            chats.push(row?);
        }
        Ok(chats)
    }

    pub fn clear_all(&self) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute_batch("DELETE FROM messages; VACUUM;")
            .context("clear all messages")?;
        Ok(())
    }

    pub fn get_stats(&self) -> Result<DbStats> {
        let conn = self.conn.lock().unwrap();
        let total_messages: i64 =
            conn.query_row("SELECT COUNT(*) FROM messages", [], |r| r.get(0))?;
        let total_chats: i64 =
            conn.query_row("SELECT COUNT(DISTINCT chat_name) FROM messages", [], |r| {
                r.get(0)
            })?;
        let earliest: String = conn
            .query_row(
                "SELECT COALESCE(MIN(detected_at), '') FROM messages",
                [],
                |r| r.get(0),
            )
            .unwrap_or_default();
        let latest: String = conn
            .query_row(
                "SELECT COALESCE(MAX(detected_at), '') FROM messages",
                [],
                |r| r.get(0),
            )
            .unwrap_or_default();

        Ok(DbStats {
            total_messages,
            total_chats,
            earliest_message: earliest,
            latest_message: latest,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::MessageDb;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_db_path(tag: &str) -> PathBuf {
        let ts = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time after epoch")
            .as_nanos();
        std::env::temp_dir().join(format!("wechat_pc_auto_db_{}_{}.db", tag, ts))
    }

    fn cleanup_db(path: &PathBuf) {
        let _ = std::fs::remove_file(path);
        let _ = std::fs::remove_file(format!("{}-wal", path.display()));
        let _ = std::fs::remove_file(format!("{}-shm", path.display()));
    }

    #[test]
    fn query_messages_should_include_all_quality_levels() {
        let path = temp_db_path("query_all_quality");
        let db = MessageDb::new(&path).expect("create db");
        db.insert_message_with_meta(
            "chat-a",
            Some("private"),
            "",
            "preview row",
            "",
            false,
            "2026-03-07 10:00:00",
            None,
            "session_preview",
            "low",
        )
        .expect("insert low");
        db.insert_message_with_meta(
            "chat-a",
            Some("private"),
            "Alice",
            "high row",
            "",
            false,
            "2026-03-07 10:00:01",
            None,
            "chat",
            "high",
        )
        .expect("insert high");

        let rows = db
            .query_messages(Some("chat-a"), None, None, 20, 0)
            .expect("query messages");
        assert_eq!(rows.len(), 2);

        drop(db);
        cleanup_db(&path);
    }

    #[test]
    fn try_correct_preview_row_should_upgrade_low_quality_preview() {
        let path = temp_db_path("correct_preview");
        let db = MessageDb::new(&path).expect("create db");
        db.insert_message_with_meta(
            "chat-b",
            Some("group"),
            "",
            "因为rust的代码简直不是人类读的",
            "",
            false,
            "2026-03-07 11:00:00",
            None,
            "session_preview",
            "low",
        )
        .expect("insert low preview");

        let corrected = db
            .try_correct_preview_row(
                "chat-b",
                Some("group"),
                "因为rust的代码简直不是人类读的!!!",
                "花姐",
                "",
                false,
                None,
                "2026-03-07 11:00:05",
                20,
            )
            .expect("correct preview");
        assert!(corrected);

        let rows = db
            .query_messages(Some("chat-b"), None, None, 20, 0)
            .expect("query messages");
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].sender, "花姐");
        assert_eq!(rows[0].chat_type.as_deref(), Some("group"));
        assert_eq!(rows[0].source.as_deref(), Some("session_corrected"));
        assert_eq!(rows[0].quality.as_deref(), Some("high"));

        drop(db);
        cleanup_db(&path);
    }

    #[test]
    fn update_message_translation_should_fill_content_en_for_existing_row() {
        let path = temp_db_path("update_translation");
        let db = MessageDb::new(&path).expect("create db");
        db.insert_message_with_meta(
            "chat-a",
            Some("private"),
            "Alice",
            "你好",
            "",
            false,
            "2026-03-09 10:00:00",
            None,
            "chat",
            "high",
        )
        .expect("insert row");

        let updated = db
            .update_message_translation("chat-a", "Alice", "你好", "2026-03-09 10:00:00", "Hello")
            .expect("update translation");
        assert!(updated);

        let rows = db
            .query_messages(Some("chat-a"), None, None, 20, 0)
            .expect("query messages");
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].content_en, "Hello");

        drop(db);
        cleanup_db(&path);
    }

    #[test]
    fn cached_translation_should_match_same_language_pair_only() {
        let path = temp_db_path("cached_translation");
        let db = MessageDb::new(&path).expect("create db");

        db.upsert_cached_translation("你好", "auto", "EN", "Hello")
            .expect("cache translation");

        let hit = db
            .get_cached_translation("你好", "auto", "EN")
            .expect("query cache")
            .expect("cached translation exists");
        assert_eq!(hit.translated_text, "Hello");

        let miss = db
            .get_cached_translation("你好", "auto", "JA")
            .expect("query other lang");
        assert!(miss.is_none());

        drop(db);
        cleanup_db(&path);
    }
}
