import { invoke, isTauri } from "@tauri-apps/api/core"

import type {
  BackendEvent,
  BackendMessage,
  BackendSession,
  BackendSnapshot,
} from "@/lib/shell-types"

export type BackendConnectionInfo = {
  httpBaseUrl: string
  wsUrl: string
  managed: boolean
  startupError: string
  runtimeRoot: string
}

const DEFAULT_BACKEND_INFO: BackendConnectionInfo = {
  httpBaseUrl: import.meta.env.VITE_BACKEND_HTTP_URL ?? "http://127.0.0.1:8765",
  wsUrl: import.meta.env.VITE_BACKEND_WS_URL ?? "ws://127.0.0.1:8766/events",
  managed: false,
  startupError: "",
  runtimeRoot: "",
}

let backendInfoPromise: Promise<BackendConnectionInfo> | null = null

export class ManagedBackendStartupError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "ManagedBackendStartupError"
  }
}

export async function resolveBackendConnectionInfo(): Promise<BackendConnectionInfo> {
  if (!isTauri()) {
    return DEFAULT_BACKEND_INFO
  }
  if (!backendInfoPromise) {
    backendInfoPromise = invoke<BackendConnectionInfo>("get_backend_connection_info").catch(
      () => DEFAULT_BACKEND_INFO,
    )
  }
  return backendInfoPromise
}

async function requireBackendConnectionInfo() {
  const backendInfo = await resolveBackendConnectionInfo()
  if (backendInfo.startupError) {
    throw new ManagedBackendStartupError(backendInfo.startupError)
  }
  return backendInfo
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const backendInfo = await requireBackendConnectionInfo()
  const response = await fetch(`${backendInfo.httpBaseUrl}${path}`, {
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

export async function createEventSocket(onEvent: (event: BackendEvent) => void) {
  const backendInfo = await requireBackendConnectionInfo()
  const socket = new WebSocket(backendInfo.wsUrl)
  socket.addEventListener("message", (message) => {
    const payload = JSON.parse(message.data) as BackendEvent
    onEvent(payload)
  })
  return socket
}
