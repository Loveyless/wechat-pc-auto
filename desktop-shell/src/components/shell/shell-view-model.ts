import type { StatusBadgeTone } from "@/components/ui/status-badge"
import type {
  BackendRuntimeState,
  BackendTTSState,
  BackendTranslationState,
  ShellConnectionState,
  ShellMessage,
  ShellSession,
} from "@/lib/shell-types"

export type ShellOverviewState = {
  label: string
  tone: StatusBadgeTone
  title: string
  detail: string
}

export type ShellConnectionBannerState = {
  label: string
  tone: StatusBadgeTone
  title: string
  detail: string
}

export type ShellDataEmptyState = "no-sessions" | "no-messages" | null

export function resolveConnectionOverviewState(
  connectionState: ShellConnectionState,
  lastError: string,
): ShellOverviewState {
  switch (connectionState) {
    case "loading":
      return {
        label: "加载中",
        tone: "neutral",
        title: "正在准备桌面壳快照",
        detail: "等待本地 HTTP 快照与初始会话数据。",
      }
    case "starting":
      return {
        label: "启动中",
        tone: "info",
        title: "Backend 正在冷启动",
        detail: "启动阶段允许短暂等待，不应误报成 reconnecting。",
      }
    case "ready":
      return {
        label: "已就绪",
        tone: "success",
        title: "桌面壳与 backend 已同步",
        detail: "HTTP bootstrap 与 WebSocket live sync 均可用。",
      }
    case "startup_failed":
      return {
        label: "启动失败",
        tone: "danger",
        title: "Backend 冷启动失败",
        detail: lastError || "启动失败后必须显式暴露错误，不允许只剩空白页面。",
      }
    case "degraded":
      return {
        label: "降级运行",
        tone: "warning",
        title: "Runtime 可达，但当前不在完整健康态",
        detail: lastError || "需要保留诊断信息，不能和 startup_failed 混成同一类状态。",
      }
    case "reconnecting":
      return {
        label: "重连中",
        tone: "info",
        title: "正在恢复实时事件流",
        detail: lastError || "保留已知数据，同时等待 WebSocket 重新连回。",
      }
  }
}

export function resolveConnectionBannerState(
  connectionState: ShellConnectionState,
  lastError: string,
): ShellConnectionBannerState | null {
  switch (connectionState) {
    case "loading":
      return {
        label: "加载中",
        tone: "neutral",
        title: "正在拉取初始快照",
        detail: "桌面壳正在等待 runtime snapshot 和首批会话，不应把这段时间误报成故障。",
      }
    case "starting":
      return {
        label: "启动中",
        tone: "info",
        title: "Backend 正在冷启动",
        detail: "managed backend 冷启动阶段应稳定显示 starting，而不是提前掉进 reconnecting。",
      }
    case "startup_failed":
      return {
        label: "启动失败",
        tone: "danger",
        title: "Backend 启动失败",
        detail: lastError || "启动失败必须在页面级明确暴露，不能只剩下角落里的错误字符串。",
      }
    case "degraded":
      return {
        label: "降级运行",
        tone: "warning",
        title: "Runtime 处于降级运行",
        detail: lastError || "当前仍可看到已知快照，但链路并不完整，应该保留诊断线索。",
      }
    case "reconnecting":
      return {
        label: "重连中",
        tone: "info",
        title: "正在恢复实时事件流",
        detail: lastError || "已知数据保留显示，同时等待事件流重新接上。",
      }
    case "ready":
      return null
  }
}

export function resolveSessionKindBadge(
  kind: ShellSession["kind"],
): { label: string; tone: StatusBadgeTone } {
  switch (kind) {
    case "group":
      return { label: "群聊", tone: "accent" }
    case "private":
      return { label: "私聊", tone: "info" }
    default:
      return { label: "未知", tone: "neutral" }
  }
}

export function resolveUnreadTone(unread: number): StatusBadgeTone {
  return unread > 0 ? "unread" : "neutral"
}

export function resolveSessionFidelityBadge(
  session: Pick<ShellSession, "previewOnly">,
): { label: string; tone: StatusBadgeTone } | null {
  return session.previewOnly ? { label: "PREVIEW", tone: "preview" } : null
}

export function resolveMessagePresentation(
  message: Pick<ShellMessage, "display" | "translated" | "original" | "captureLevel" | "pendingTranslation">,
): {
  primaryText: string
  fidelityLabel: string
  fidelityTone: StatusBadgeTone
  translationLabel: string | null
  translationTone: StatusBadgeTone | null
} {
  return {
    primaryText: message.display || message.translated || message.original,
    fidelityLabel: message.captureLevel === "preview" ? "PREVIEW" : "FULL",
    fidelityTone: message.captureLevel === "preview" ? "preview" : "accent",
    translationLabel: message.pendingTranslation ? "TRANSLATING" : null,
    translationTone: message.pendingTranslation ? "info" : null,
  }
}

export function resolveTranslationSummary(
  translationState: Pick<BackendTranslationState, "enabled" | "pending_count" | "last_error" | "provider">,
): { label: string; tone: StatusBadgeTone } {
  if (!translationState.enabled) {
    return { label: `translate:${translationState.provider}:off`, tone: "neutral" }
  }
  if (translationState.last_error) {
    return { label: `translate:${translationState.provider}:error`, tone: "danger" }
  }
  if (translationState.pending_count > 0) {
    return { label: `translate:${translationState.provider}:${translationState.pending_count}`, tone: "info" }
  }
  return { label: `translate:${translationState.provider}:ready`, tone: "success" }
}

export function resolveTtsSummary(
  ttsState: Pick<BackendTTSState, "available" | "auto_read_enabled" | "last_error" | "provider">,
): { label: string; tone: StatusBadgeTone } {
  if (!ttsState.available || ttsState.last_error) {
    return { label: `tts:${ttsState.provider}:blocked`, tone: "warning" }
  }
  if (!ttsState.auto_read_enabled) {
    return { label: `tts:${ttsState.provider}:manual`, tone: "neutral" }
  }
  return { label: `tts:${ttsState.provider}:auto`, tone: "success" }
}

export function resolveRuntimeSummary(
  runtimeState: Pick<BackendRuntimeState, "message_fidelity" | "monitor_scope" | "worker_state">,
): { fidelityTone: StatusBadgeTone; workerTone: StatusBadgeTone } {
  const fidelityTone =
    runtimeState.message_fidelity === "preview_only" ? "preview" : "accent"
  const workerTone =
    runtimeState.worker_state === "running"
      ? "success"
      : runtimeState.worker_state === "worker_backoff"
        ? "warning"
        : "info"

  return { fidelityTone, workerTone }
}

export function resolveDataEmptyState(params: {
  connectionState: ShellConnectionState
  sessionCount: number
  selectedSessionId: string
  selectedMessageCount: number
}): ShellDataEmptyState {
  if (
    params.connectionState === "loading" ||
    params.connectionState === "starting" ||
    params.connectionState === "startup_failed" ||
    params.connectionState === "reconnecting"
  ) {
    return null
  }
  if (params.sessionCount === 0) {
    return "no-sessions"
  }
  if (params.selectedSessionId && params.selectedMessageCount === 0) {
    return "no-messages"
  }
  return null
}
