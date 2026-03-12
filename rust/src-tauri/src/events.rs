use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter};

const MAX_HISTORY: usize = 2000;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    Status,
    Message,
    Log,
    Error,
    TaskState,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceEvent {
    pub id: u64,
    #[serde(rename = "type")]
    pub event_type: EventType,
    pub source: String,
    pub timestamp: String,
    pub payload: serde_json::Value,
}

pub struct EventStore {
    history: Mutex<VecDeque<ServiceEvent>>,
    counter: AtomicU64,
}

impl EventStore {
    pub fn new() -> Self {
        Self {
            history: Mutex::new(VecDeque::with_capacity(MAX_HISTORY)),
            counter: AtomicU64::new(0),
        }
    }

    fn now_iso() -> String {
        chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()
    }

    pub fn publish(
        &self,
        app: &AppHandle,
        event_type: EventType,
        source: &str,
        payload: serde_json::Value,
    ) -> ServiceEvent {
        let id = self.counter.fetch_add(1, Ordering::SeqCst) + 1;
        let event = ServiceEvent {
            id,
            event_type,
            source: source.to_string(),
            timestamp: Self::now_iso(),
            payload,
        };

        {
            let mut history = self.history.lock().unwrap();
            if history.len() >= MAX_HISTORY {
                history.pop_front();
            }
            history.push_back(event.clone());
        }

        let _ = app.emit("wechat-event", &event);
        event
    }
}
