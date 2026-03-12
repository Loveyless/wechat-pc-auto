use std::collections::VecDeque;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{Mutex, OwnedSemaphorePermit, Semaphore};

/// 翻译请求限流器
/// 同时控制并发数和 QPS
pub struct TranslationLimiter {
    semaphore: Arc<Semaphore>,
    recent_requests: Mutex<VecDeque<Instant>>,
    max_requests_per_second: usize,
}

impl TranslationLimiter {
    pub fn new(max_concurrency: usize, max_requests_per_second: usize) -> Self {
        Self {
            semaphore: Arc::new(Semaphore::new(max_concurrency.max(1))),
            recent_requests: Mutex::new(VecDeque::new()),
            max_requests_per_second: max_requests_per_second.max(1),
        }
    }

    /// 获取翻译许可，会阻塞直到获取到许可
    pub async fn acquire(&self) -> OwnedSemaphorePermit {
        self.wait_for_window_slot().await;
        self.semaphore
            .clone()
            .acquire_owned()
            .await
            .expect("translation semaphore closed")
    }

    async fn wait_for_window_slot(&self) {
        loop {
            let mut recent = self.recent_requests.lock().await;
            let now = Instant::now();
            let window_start = now - Duration::from_secs(1);

            while recent.front().map_or(false, |&t| t < window_start) {
                recent.pop_front();
            }

            if recent.len() < self.max_requests_per_second {
                recent.push_back(now);
                break;
            }

            let wait_until = *recent.front().unwrap() + Duration::from_secs(1);
            drop(recent);

            if wait_until > now {
                tokio::time::sleep(wait_until - now).await;
            }
        }
    }
}
