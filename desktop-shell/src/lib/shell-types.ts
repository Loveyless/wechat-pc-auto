export type ShellConnectionState =
  | "loading"
  | "starting"
  | "ready"
  | "startup_failed"
  | "degraded"
  | "reconnecting"

export type ShellSession = {
  id: string
  name: string
  preview: string
  unread: number
  updatedAt: string
  previewOnly: boolean
}

export type ShellMessage = {
  id: string
  sessionId: string
  sender: string
  time: string
  translated: string
  original: string
  display: string
  captureLevel: "preview" | "full"
  pendingTranslation: boolean
}

export type BackendRuntimeState = {
  worker_state: string
  worker_detail: string
  active_session_id: string
  monitor_scope: string
  message_fidelity: string
  session_order: string[]
}

export type BackendTranslationState = {
  enabled: boolean
  provider: string
  pending_count: number
  last_error: string
}

export type BackendTTSState = {
  auto_read_enabled: boolean
  provider: string
  available: boolean
  last_error: string
}

export type BackendSession = {
  session_id: string
  session_name: string
  unread_count: number
  latest_preview: string
  last_message_id: string
  updated_at: string
  has_preview_only_messages: boolean
}

export type BackendMessage = {
  message_id: string
  session_id: string
  session_name: string
  sender_name: string
  text_original: string
  text_translated: string
  text_display: string
  created_at: string
  source: string
  capture_level: "preview" | "full"
  is_self: boolean
  pending_translation: boolean
}

export type BackendSnapshot = {
  runtime: BackendRuntimeState
  translation: BackendTranslationState
  tts: BackendTTSState
  sessions: BackendSession[]
}

export type BackendEvent =
  | { event: "backend.state"; payload: { state: string; detail: string } }
  | { event: "backend.log"; payload: { value: string } }
  | { event: "session.upsert"; payload: BackendSession }
  | { event: "session.list.updated"; payload: { items: BackendSession[] } }
  | { event: "message.created"; payload: BackendMessage }
  | { event: "translation.updated"; payload: BackendMessage }
  | { event: "tts.updated"; payload: { action: string; session_id: string; message_id: string; accepted: boolean; provider: string; detail: string; auto_read_enabled?: boolean } }
  | { event: "error.reported"; payload: { source: string; message: string; detail: string } }
