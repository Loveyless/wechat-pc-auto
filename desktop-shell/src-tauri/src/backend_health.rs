use std::{
    io::{Read, Write},
    net::{Ipv4Addr, SocketAddr, TcpStream},
    time::Duration,
};

use serde::Deserialize;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BackendHealthStatus {
    Starting,
    Ok,
    StartupFailed,
    Degraded,
    Unknown(String),
}

impl BackendHealthStatus {
    pub fn as_str(&self) -> &str {
        match self {
            Self::Starting => "starting",
            Self::Ok => "ok",
            Self::StartupFailed => "startup_failed",
            Self::Degraded => "degraded",
            Self::Unknown(value) => value.as_str(),
        }
    }

    pub fn is_ready(&self) -> bool {
        matches!(self, Self::Ok)
    }

    pub fn is_retryable(&self) -> bool {
        matches!(self, Self::Starting)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BackendHealthSnapshot {
    pub status: BackendHealthStatus,
    pub detail: String,
    pub worker_state: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BackendHealthProbe {
    Reachable(BackendHealthSnapshot),
    Invalid(String),
    Unreachable,
}

#[derive(Debug, Deserialize)]
struct RawHealthPayload {
    status: String,
    #[serde(default)]
    detail: String,
    #[serde(default)]
    worker_state: String,
}

fn normalize_health_status(value: &str) -> BackendHealthStatus {
    match value.trim() {
        "starting" => BackendHealthStatus::Starting,
        "ok" => BackendHealthStatus::Ok,
        "startup_failed" => BackendHealthStatus::StartupFailed,
        "degraded" => BackendHealthStatus::Degraded,
        other => BackendHealthStatus::Unknown(other.to_string()),
    }
}

fn parse_http_status_code(response: &str) -> Option<u16> {
    let status_line = response.lines().next()?.trim();
    let mut parts = status_line.split_whitespace();
    let _http_version = parts.next()?;
    parts.next()?.parse::<u16>().ok()
}

fn extract_http_body(response: &str) -> Option<&str> {
    response
        .split_once("\r\n\r\n")
        .map(|(_, body)| body)
        .or_else(|| response.split_once("\n\n").map(|(_, body)| body))
}

pub fn response_is_healthy(response: &str) -> bool {
    matches!(
        parse_health_response(response),
        Ok(payload) if payload.status.is_ready()
    )
}

pub fn parse_health_response(response: &str) -> Result<BackendHealthSnapshot, String> {
    let Some(status_code) = parse_http_status_code(response) else {
        return Err("missing http status code".to_string());
    };
    if status_code != 200 {
        return Err(format!("unexpected http status {status_code}"));
    }
    let Some(body) = extract_http_body(response) else {
        return Err("missing http body".to_string());
    };
    let payload = serde_json::from_str::<RawHealthPayload>(body.trim())
        .map_err(|err| format!("invalid health json: {err}"))?;
    let status_text = payload.status.trim();
    if status_text.is_empty() {
        return Err("missing health status".to_string());
    }
    Ok(BackendHealthSnapshot {
        status: normalize_health_status(status_text),
        detail: payload.detail.trim().to_string(),
        worker_state: payload.worker_state.trim().to_string(),
    })
}

pub fn describe_health_snapshot(snapshot: &BackendHealthSnapshot) -> String {
    let mut parts = vec![format!("status={}", snapshot.status.as_str())];
    if !snapshot.detail.is_empty() {
        parts.push(format!("detail={}", snapshot.detail));
    }
    if !snapshot.worker_state.is_empty() {
        parts.push(format!("worker_state={}", snapshot.worker_state));
    }
    parts.join(" ")
}

pub fn probe_backend_health(port: u16) -> BackendHealthProbe {
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let timeout = Duration::from_millis(300);
    let mut stream = match TcpStream::connect_timeout(&address, timeout) {
        Ok(stream) => stream,
        Err(_) => return BackendHealthProbe::Unreachable,
    };
    let _ = stream.set_read_timeout(Some(timeout));
    let _ = stream.set_write_timeout(Some(timeout));
    if stream
        .write_all(b"GET /healthz HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return BackendHealthProbe::Invalid("write /healthz request failed".to_string());
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return BackendHealthProbe::Invalid("read /healthz response failed".to_string());
    }
    match parse_health_response(&response) {
        Ok(payload) => BackendHealthProbe::Reachable(payload),
        Err(error) => BackendHealthProbe::Invalid(error),
    }
}

#[cfg(test)]
mod tests {
    use super::{
        describe_health_snapshot, parse_health_response, response_is_healthy, BackendHealthStatus,
    };

    #[test]
    fn accepts_json_with_spaces() {
        let response =
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\": \"ok\"}";
        assert!(response_is_healthy(response));
    }

    #[test]
    fn accepts_json_without_spaces() {
        let response =
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\":\"ok\"}";
        assert!(response_is_healthy(response));
    }

    #[test]
    fn parses_startup_failed_payload_with_detail() {
        let response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\":\"startup_failed\",\"detail\":\"missing deeplx url\",\"worker_state\":\"startup_failed\"}";
        let payload = parse_health_response(response).expect("payload should parse");
        assert_eq!(payload.status, BackendHealthStatus::StartupFailed);
        assert_eq!(payload.detail, "missing deeplx url");
        assert_eq!(payload.worker_state, "startup_failed");
        assert_eq!(
            describe_health_snapshot(&payload),
            "status=startup_failed detail=missing deeplx url worker_state=startup_failed"
        );
    }

    #[test]
    fn rejects_non_200_status() {
        let response = "HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\n\r\n{\"status\": \"ok\"}";
        assert!(!response_is_healthy(response));
        assert_eq!(
            parse_health_response(response).unwrap_err(),
            "unexpected http status 503"
        );
    }

    #[test]
    fn rejects_invalid_json() {
        let response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\nnot-json";
        assert!(!response_is_healthy(response));
        assert!(parse_health_response(response)
            .unwrap_err()
            .starts_with("invalid health json:"));
    }

    #[test]
    fn rejects_non_ok_status_payload() {
        let response =
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\": \"starting\"}";
        assert!(!response_is_healthy(response));
    }

    #[test]
    fn preserves_unknown_health_status_for_diagnostics() {
        let response =
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\": \"odd_state\"}";
        let payload = parse_health_response(response).expect("payload should parse");
        assert_eq!(payload.status, BackendHealthStatus::Unknown("odd_state".to_string()));
        assert_eq!(describe_health_snapshot(&payload), "status=odd_state");
    }
}
