import type {
  BackendRuntimeState,
  BackendTTSState,
  BackendTranslationState,
  ShellMessage,
  ShellSession,
} from "@/lib/shell-types"

export const mockSessions: ShellSession[] = [
  {
    id: "group-english-checkin",
    name: "英语打卡群",
    unread: 3,
    preview: "Alice：pipeline 已经切成 HTTP + WS 了，前端别再读 stdout。",
    updatedAt: "10:20",
    previewOnly: true,
  },
  {
    id: "private-bob",
    name: "Bob",
    unread: 1,
    preview: "preview_only 要写死，不要冒充完整正文。",
    updatedAt: "10:21",
    previewOnly: true,
  },
  {
    id: "group-weekly-review",
    name: "周会复盘",
    unread: 0,
    preview: "先把桌面壳子起起来，运行时接线后面再说。",
    updatedAt: "10:22",
    previewOnly: true,
  },
]

export const mockMessages: ShellMessage[] = [
  {
    id: "message-1",
    sessionId: "group-english-checkin",
    sender: "Alice",
    time: "10:20",
    translated: "The pipeline is already split into HTTP plus WebSocket.",
    original: "pipeline 已经切成 HTTP + WS 了，前端别再读 stdout。",
    display: "The pipeline is already split into HTTP plus WebSocket.",
    captureLevel: "preview",
    pendingTranslation: false,
  },
  {
    id: "message-2",
    sessionId: "group-english-checkin",
    sender: "Bob",
    time: "10:21",
    translated: "Keep the preview-only contract explicit instead of implying full fidelity.",
    original: "preview_only 要写死，不要冒充完整正文。",
    display: "Keep the preview-only contract explicit instead of implying full fidelity.",
    captureLevel: "preview",
    pendingTranslation: false,
  },
]

export const mockRuntimeState: BackendRuntimeState = {
  worker_state: "running",
  worker_detail: "mock runtime",
  active_session_id: "group-english-checkin",
  monitor_scope: "all_sessions",
  message_fidelity: "preview_only",
  session_order: mockSessions.map((session) => session.id),
}

export const mockTranslationState: BackendTranslationState = {
  enabled: true,
  provider: "deeplx",
  pending_count: 0,
  last_error: "",
}

export const mockTtsState: BackendTTSState = {
  auto_read_enabled: true,
  provider: "windows_system",
  available: true,
  last_error: "",
}
