export type SessionKind = "group" | "private"

export type ShellSession = {
  id: string
  kind: SessionKind
  name: string
  preview: string
  unread: number
}

export type ShellMessage = {
  id: string
  sender: string
  time: string
  translated: string
  original: string
}

export const mockSessions: ShellSession[] = [
  {
    id: "group-english-checkin",
    kind: "group",
    name: "英语打卡群",
    unread: 3,
    preview: "Alice：pipeline 已经切成 HTTP + WS 了，前端别再读 stdout。",
  },
  {
    id: "private-bob",
    kind: "private",
    name: "Bob",
    unread: 1,
    preview: "preview_only 要写死，不要冒充完整正文。",
  },
  {
    id: "group-weekly-review",
    kind: "group",
    name: "周会复盘",
    unread: 0,
    preview: "先把桌面壳子起起来，运行时接线后面再说。",
  },
]

export const mockMessages: ShellMessage[] = [
  {
    id: "message-1",
    sender: "Alice",
    time: "10:20",
    translated: "The pipeline is already split into HTTP plus WebSocket.",
    original: "pipeline 已经切成 HTTP + WS 了，前端别再读 stdout。",
  },
  {
    id: "message-2",
    sender: "Bob",
    time: "10:21",
    translated: "Keep the preview-only contract explicit instead of implying full fidelity.",
    original: "preview_only 要写死，不要冒充完整正文。",
  },
]
