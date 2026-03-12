//! 音频缓存模块
//!
//! 提供词典发音音频的本地缓存功能，避免重复下载远程音频文件。
//! 
//! ## 工作原理
//! 1. 用户请求播放音频时，先检查本地缓存
//! 2. 缓存命中 → 直接返回本地文件路径
//! 3. 缓存未命中 → 下载远程文件 → 存入缓存 → 返回本地路径
//!
//! ## 缓存策略
//! - 缓存 Key: URL 的 SHA256 前 16 字符
//! - 存储位置: app_data_dir/audio_cache/
//! - 过期策略: 不过期（音频文件内容不会变化）
//! - 大小限制: 可选，超过阈值时按 LRU 清理

use anyhow::{anyhow, Result};
use reqwest::Client;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Mutex;

/// 音频缓存管理器
pub struct AudioCache {
    /// 缓存目录路径
    cache_dir: PathBuf,
    /// HTTP 客户端（复用连接）
    client: Client,
    /// 下载锁，防止同一文件并发下载
    download_locks: Arc<Mutex<std::collections::HashMap<String, Arc<Mutex<()>>>>>,
}

impl AudioCache {
    /// 创建音频缓存管理器
    ///
    /// # 参数
    /// - `app_data_dir`: 应用数据目录
    ///
    /// # 返回
    /// - 缓存管理器实例
    pub fn new(app_data_dir: &Path) -> Result<Self> {
        let cache_dir = app_data_dir.join("audio_cache");
        
        // 确保缓存目录存在
        if !cache_dir.exists() {
            std::fs::create_dir_all(&cache_dir)?;
        }
        
        // 创建 HTTP 客户端，设置超时和连接池
        let client = Client::builder()
            .timeout(Duration::from_secs(30))
            .connect_timeout(Duration::from_secs(10))
            .pool_max_idle_per_host(5)
            .build()?;
        
        Ok(Self {
            cache_dir,
            client,
            download_locks: Arc::new(Mutex::new(std::collections::HashMap::new())),
        })
    }
    
    /// 获取音频文件路径（优先返回缓存）
    ///
    /// 如果本地缓存存在，直接返回缓存路径；
    /// 否则下载远程文件并缓存后返回。
    ///
    /// # 参数
    /// - `url`: 远程音频 URL
    ///
    /// # 返回
    /// - 本地缓存文件的绝对路径
    pub async fn get_or_download(&self, url: &str) -> Result<PathBuf> {
        println!("[AudioCache] 1. 收到请求, URL: {}", url);
        
        // 验证 URL 格式
        if !url.starts_with("http://") && !url.starts_with("https://") {
            println!("[AudioCache] 无效的 URL 格式");
            return Err(anyhow!("无效的音频 URL: {}", url));
        }
        
        // 计算缓存 key
        let hash = self.url_hash(url);
        let cache_path = self.get_cache_path(&hash);
        println!("[AudioCache] 2. 缓存路径: {}", cache_path.display());
        
        // 检查缓存是否存在
        let exists = cache_path.exists();
        println!("[AudioCache] 3. 文件存在检查: {}", exists);
        if exists {
            println!("[AudioCache] 3. 缓存命中，直接返回");
            return Ok(cache_path);
        }
        println!("[AudioCache] 3. 缓存未命中，开始下载");
        
        // 获取下载锁，防止同一文件并发下载
        let lock = {
            let mut locks = self.download_locks.lock().await;
            locks.entry(hash.clone())
                .or_insert_with(|| Arc::new(Mutex::new(())))
                .clone()
        };
        
        // 加锁下载
        let _guard = lock.lock().await;
        
        // 再次检查缓存（可能其他线程已下载完成）
        if cache_path.exists() {
            println!("[AudioCache] 4. 其他线程已下载，直接返回");
            return Ok(cache_path);
        }
        
        // 下载音频文件
        println!("[AudioCache] 4. 开始下载: {}", url);
        let bytes = self.download_audio(url).await?;
        println!("[AudioCache] 5. 下载完成，大小: {} bytes", bytes.len());
        
        // 写入缓存
        std::fs::write(&cache_path, &bytes)?;
        println!("[AudioCache] 6. 写入缓存成功: {}", cache_path.display());
        
        // 清理下载锁
        {
            let mut locks = self.download_locks.lock().await;
            locks.remove(&hash);
        }
        
        Ok(cache_path)
    }
    
    /// 下载音频文件
    async fn download_audio(&self, url: &str) -> Result<Vec<u8>> {
        let response = self.client
            .get(url)
            .send()
            .await
            .map_err(|e| anyhow!("下载音频失败: {}", e))?;
        
        if !response.status().is_success() {
            return Err(anyhow!("下载音频失败，状态码: {}", response.status()));
        }
        
        let bytes = response
            .bytes()
            .await
            .map_err(|e| anyhow!("读取音频数据失败: {}", e))?;
        
        Ok(bytes.to_vec())
    }
    
    /// 计算 URL 的缓存 key
    ///
    /// 使用 SHA256 哈希，取前 16 字符作为文件名
    fn url_hash(&self, url: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(url.as_bytes());
        let result = hasher.finalize();
        // 手动转换为十六进制字符串（取前 8 字节 = 16 字符）
        result[..8]
            .iter()
            .map(|b| format!("{:02x}", b))
            .collect()
    }
    
    /// 获取缓存文件路径
    fn get_cache_path(&self, hash: &str) -> PathBuf {
        self.cache_dir.join(format!("{}.mp3", hash))
    }
    
    /// 检查 URL 是否已缓存
    pub fn is_cached(&self, url: &str) -> bool {
        let hash = self.url_hash(url);
        self.get_cache_path(&hash).exists()
    }
    
    /// 获取缓存统计信息
    pub fn get_stats(&self) -> Result<AudioCacheStats> {
        let mut file_count = 0u64;
        let mut total_size = 0u64;
        
        if self.cache_dir.exists() {
            for entry in std::fs::read_dir(&self.cache_dir)? {
                if let Ok(entry) = entry {
                    if let Ok(metadata) = entry.metadata() {
                        if metadata.is_file() {
                            file_count += 1;
                            total_size += metadata.len();
                        }
                    }
                }
            }
        }
        
        Ok(AudioCacheStats {
            file_count,
            total_size_bytes: total_size,
            total_size_mb: (total_size as f64) / (1024.0 * 1024.0),
            cache_dir: self.cache_dir.display().to_string(),
        })
    }
    
    /// 清空所有缓存
    pub fn clear(&self) -> Result<u64> {
        let mut cleared = 0u64;
        
        if self.cache_dir.exists() {
            for entry in std::fs::read_dir(&self.cache_dir)? {
                if let Ok(entry) = entry {
                    if let Ok(metadata) = entry.metadata() {
                        if metadata.is_file() && entry.path().extension().map_or(false, |ext| ext == "mp3") {
                            if std::fs::remove_file(entry.path()).is_ok() {
                                cleared += 1;
                            }
                        }
                    }
                }
            }
        }
        
        log::info!("已清空 {} 个音频缓存文件", cleared);
        Ok(cleared)
    }
}

/// 音频缓存统计信息
#[derive(Debug, Clone, serde::Serialize)]
pub struct AudioCacheStats {
    /// 缓存文件数量
    pub file_count: u64,
    /// 总大小（字节）
    pub total_size_bytes: u64,
    /// 总大小（MB）
    pub total_size_mb: f64,
    /// 缓存目录路径
    pub cache_dir: String,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    
    #[test]
    fn test_url_hash() {
        let cache = AudioCache {
            cache_dir: PathBuf::from("/tmp/test"),
            client: Client::new(),
            download_locks: Arc::new(Mutex::new(std::collections::HashMap::new())),
        };
        
        let hash1 = cache.url_hash("https://example.com/audio1.mp3");
        let hash2 = cache.url_hash("https://example.com/audio2.mp3");
        
        // 哈希应该是 16 字符
        assert_eq!(hash1.len(), 16);
        assert_eq!(hash2.len(), 16);
        
        // 不同 URL 应该有不同哈希
        assert_ne!(hash1, hash2);
        
        // 相同 URL 应该有相同哈希
        let hash1_again = cache.url_hash("https://example.com/audio1.mp3");
        assert_eq!(hash1, hash1_again);
    }
}
