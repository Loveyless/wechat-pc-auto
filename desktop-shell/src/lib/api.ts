import type {
  BackendEvent,
  BackendMessage,
  BackendSession,
  BackendSnapshot,
} from "@/lib/shell-types"

const HTTP_BASE = import.meta.env.VITE_BACKEND_HTTP_URL ?? "http://127.0.0.1:8765"
const WS_URL = import.meta.env.VITE_BACKEND_WS_URL ?? "ws://127.0.0.1:8766/events"

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${HTTP_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  if (!response.ok) {
    throw new Error(`request failed ${response.status} ${path}`)
  }
  return (await response.json()) as T
}

export function getHttpBaseUrl() {
  return HTTP_BASE
}

export function getWsUrl() {
  return WS_URL
}

export async function fetchSnapshot() {
  return requestJson<BackendSnapshot>("/api/runtime")
}

export async function fetchSessions() {
  const payload = await requestJson<{ items: BackendSession[] }>("/api/sessions")
  return payload.items
}

export async function fetchSessionMessages(sessionId: string) {
  const encoded = encodeURIComponent(sessionId)
  const payload = await requestJson<{ items: BackendMessage[] }>(`/api/sessions/${encoded}/messages`)
  return payload.items
}

export async function setActiveSession(sessionId: string) {
  return requestJson<{ runtime: BackendSnapshot["runtime"] }>("/api/runtime/active-session", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  })
}

export function createEventSocket(onEvent: (event: BackendEvent) => void) {
  const socket = new WebSocket(WS_URL)
  socket.addEventListener("message", (message) => {
    const payload = JSON.parse(message.data) as BackendEvent
    onEvent(payload)
  })
  return socket
}
