use std::{
    io::{Read, Write},
    net::{Ipv4Addr, SocketAddr, TcpStream},
    time::Duration,
};

use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct HealthPayload {
    status: String,
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
    if parse_http_status_code(response) != Some(200) {
        return false;
    }
    let Some(body) = extract_http_body(response) else {
        return false;
    };
    let Ok(payload) = serde_json::from_str::<HealthPayload>(body.trim()) else {
        return false;
    };
    payload.status == "ok"
}

pub fn probe_backend_health(port: u16) -> bool {
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let timeout = Duration::from_millis(300);
    let mut stream = match TcpStream::connect_timeout(&address, timeout) {
        Ok(stream) => stream,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(timeout));
    let _ = stream.set_write_timeout(Some(timeout));
    if stream
        .write_all(b"GET /healthz HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return false;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    response_is_healthy(&response)
}

#[cfg(test)]
mod tests {
    use super::response_is_healthy;

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
    fn rejects_non_200_status() {
        let response = "HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\n\r\n{\"status\": \"ok\"}";
        assert!(!response_is_healthy(response));
    }

    #[test]
    fn rejects_invalid_json() {
        let response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\nnot-json";
        assert!(!response_is_healthy(response));
    }

    #[test]
    fn rejects_non_ok_status_payload() {
        let response =
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\": \"starting\"}";
        assert!(!response_is_healthy(response));
    }
}
