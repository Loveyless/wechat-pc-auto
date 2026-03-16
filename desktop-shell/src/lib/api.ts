import { invoke, isTauri } from "@tauri-apps/api/core"

import type {
  BackendEvent,
  BackendMessage,
  BackendSession,
  BackendSnapshot,
} from "@/lib/shell-types"
import type {
  DesktopRuntimeConfig,
  DesktopSettingsSavePayload,
} from "@/lib/settings-types"

export type BackendConnectionInfo = {
  httpBaseUrl: string
  wsUrl: string
  managed: boolean
  ownsBackend: boolean
  restartSupported: boolean
  startupError: string
  runtimeRoot: string
}

const DEFAULT_BACKEND_INFO: BackendConnectionInfo = {
  httpBaseUrl: import.meta.env.VITE_BACKEND_HTTP_URL ?? "http://127.0.0.1:8765",
  wsUrl: import.meta.env.VITE_BACKEND_WS_URL ?? "ws://127.0.0.1:8766/events",
  managed: false,
  ownsBackend: false,
  restartSupported: false,
  startupError: "",
  runtimeRoot: "",
}

export class ManagedBackendStartupError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "ManagedBackendStartupError"
  }
}

export class ConfigSaveError extends Error {
  fieldErrors: Record<string, string>

  constructor(message: string, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.name = "ConfigSaveError"
    this.fieldErrors = fieldErrors
  }
}

type ApiErrorPayload =
  | {
      error?: string
      message?: string
      field_errors?: Record<string, string>
    }
  | string
  | null

function normalizeBackendConnectionInfo(
  payload: Partial<BackendConnectionInfo>,
): BackendConnectionInfo {
  return {
    ...DEFAULT_BACKEND_INFO,
    ...payload,
    managed: Boolean(payload.managed),
    ownsBackend: Boolean(payload.ownsBackend),
    restartSupported: Boolean(payload.restartSupported),
    startupError: String(payload.startupError ?? ""),
    runtimeRoot: String(payload.runtimeRoot ?? ""),
  }
}

function resolveApiErrorMessage(
  status: number,
  path: string,
  payload: ApiErrorPayload,
): string {
  if (typeof payload === "string" && payload.trim()) {
    return payload
  }
  if (payload && typeof payload === "object" && payload.message) {
    return payload.message
  }
  if (payload && typeof payload === "object" && payload.error) {
    return payload.error
  }
  return `request failed ${status} ${path}`
}

async function readApiErrorPayload(response: Response): Promise<ApiErrorPayload> {
  const text = await response.text()
  if (!text.trim()) {
    return null
  }
  try {
    return JSON.parse(text) as ApiErrorPayload
  } catch {
    return text
  }
}

export async function resolveBackendConnectionInfo(): Promise<BackendConnectionInfo> {
  if (!isTauri()) {
    return DEFAULT_BACKEND_INFO
  }
  return invoke<Partial<BackendConnectionInfo>>("get_backend_connection_info")
    .then((payload) => normalizeBackendConnectionInfo(payload))
    .catch(() => DEFAULT_BACKEND_INFO)
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
    const errorPayload = await readApiErrorPayload(response)
    throw new Error(resolveApiErrorMessage(response.status, path, errorPayload))
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

export async function setTtsAutoReadEnabled(enabled: boolean) {
  return requestJson<{ tts: BackendSnapshot["tts"] }>("/api/runtime/tts-auto-read", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  })
}

export async function fetchRuntimeConfig() {
  return requestJson<DesktopRuntimeConfig>("/api/config")
}

export async function saveRuntimeConfig(payload: DesktopSettingsSavePayload) {
  const backendInfo = await requireBackendConnectionInfo()
  const response = await fetch(`${backendInfo.httpBaseUrl}/api/config`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  })
  if (response.ok) {
    const result = (await response.json()) as { config: DesktopRuntimeConfig }
    return result.config
  }
  const errorPayload = await readApiErrorPayload(response)
  const errorMessage = resolveApiErrorMessage(response.status, "/api/config", errorPayload)
  if (
    typeof errorPayload === "object" &&
    errorPayload !== null &&
    errorPayload.error === "validation_failed"
  ) {
    throw new ConfigSaveError(
      errorMessage,
      errorPayload.field_errors ?? {},
    )
  }
  throw new Error(errorMessage)
}

export async function restartManagedBackend() {
  if (!isTauri()) {
    throw new Error("保存并应用只支持 Tauri 托管桌面壳")
  }
  const payload = await invoke<Partial<BackendConnectionInfo>>("restart_owned_backend")
  return normalizeBackendConnectionInfo(payload)
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
