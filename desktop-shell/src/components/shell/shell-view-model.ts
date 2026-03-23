import type { StatusBadgeTone } from "@/components/ui/status-badge"
import type {
  BackendRuntimeState,
  BackendTTSState,
  BackendTranslationState,
  ShellConnectionState,
  ShellMessage,
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

function formatProviderName(provider: string) {
  switch (provider) {
    case "deeplx":
      return "DeepLX"
    case "windows_system":
      return "系统朗读"
    case "doubao":
      return "豆包 TTS"
    case "tencent_cloud":
      return "腾讯云 TTS"
    default:
      return provider || "未知"
  }
}

function formatMachineStateLabel(value: string) {
  switch (value) {
    case "running":
      return "运行中"
    case "worker_backoff":
      return "退避重试"
    case "waiting_wechat":
      return "等待微信"
    case "connecting":
      return "连接中"
    case "reconnecting":
      return "重新连接"
    case "stopped":
      return "已停止"
    default:
      return value ? value.split("_").join(" ") : "未知"
  }
}

function formatMonitorScopeLabel(scope: string) {
  switch (scope) {
    case "all_sessions":
      return "全部会话"
    default:
      return scope ? scope.split("_").join(" ") : "未设置"
  }
}

function formatFidelityLabel(fidelity: string) {
  switch (fidelity) {
    case "preview_only":
      return "预览模式"
    case "full":
      return "完整正文"
    default:
      return fidelity ? fidelity.split("_").join(" ") : "未设置"
  }
}

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
        detail: "等待本地快照和首批会话数据。",
      }
    case "starting":
      return {
        label: "启动中",
        tone: "info",
        title: "Backend 正在冷启动",
        detail: "启动阶段允许短暂等待，不应误报成重连。",
      }
    case "ready":
      return {
        label: "已就绪",
        tone: "success",
        title: "桌面壳与 backend 已同步",
        detail: "HTTP 快照和实时事件流都已接通。",
      }
    case "startup_failed":
      return {
        label: "启动失败",
        tone: "danger",
        title: "Backend 冷启动失败",
        detail: lastError || "启动失败后必须显式暴露错误。",
      }
    case "degraded":
      return {
        label: "降级运行",
        tone: "warning",
        title: "Runtime 可达，但当前不在完整健康态",
        detail: lastError || "当前还能展示已知数据，但链路不是完整健康态。",
      }
    case "reconnecting":
      return {
        label: "重连中",
        tone: "info",
        title: "正在恢复实时事件流",
        detail: lastError || "保留已知数据，同时等待 WebSocket 重新接回。",
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
        detail: "桌面壳正在等待 runtime snapshot 和首批会话。",
      }
    case "starting":
      return {
        label: "启动中",
        tone: "info",
        title: "Backend 正在冷启动",
        detail: "managed backend 冷启动阶段应稳定显示 starting。",
      }
    case "startup_failed":
      return {
        label: "启动失败",
        tone: "danger",
        title: "Backend 启动失败",
        detail: lastError || "启动失败必须在页面级明确暴露。",
      }
    case "degraded":
      return {
        label: "降级运行",
        tone: "warning",
        title: "Runtime 处于降级运行",
        detail: lastError || "当前仍可看到已知快照，但链路并不完整。",
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

export function resolveUnreadTone(unread: number): StatusBadgeTone {
  return unread > 0 ? "unread" : "neutral"
}

export function resolveMessagePresentation(
  message: Pick<ShellMessage, "display" | "translated" | "original" | "captureLevel" | "pendingTranslation">,
): {
  primaryText: string
  fidelityLabel: string
  fidelityTone: StatusBadgeTone
  translationLabel: string | null
  translationTone: StatusBadgeTone | null
  showPendingIndicator: boolean
  pendingText: string | null
} {
  if (message.pendingTranslation) {
    return {
      primaryText: "",
      fidelityLabel: message.captureLevel === "preview" ? "预览" : "全文",
      fidelityTone: message.captureLevel === "preview" ? "preview" : "accent",
      translationLabel: "翻译中",
      translationTone: "info",
      showPendingIndicator: true,
      pendingText: "等待翻译…",
    }
  }

  return {
    primaryText: message.display || message.translated || message.original,
    fidelityLabel: message.captureLevel === "preview" ? "预览" : "全文",
    fidelityTone: message.captureLevel === "preview" ? "preview" : "accent",
    translationLabel: null,
    translationTone: null,
    showPendingIndicator: false,
    pendingText: null,
  }
}

export function resolveTranslationSummary(
  translationState: Pick<BackendTranslationState, "enabled" | "pending_count" | "last_error" | "provider">,
): { label: string; tone: StatusBadgeTone } {
  const providerLabel = formatProviderName(translationState.provider)
  if (!translationState.enabled) {
    return { label: `${providerLabel} 关闭`, tone: "neutral" }
  }
  if (translationState.last_error) {
    return { label: `${providerLabel} 异常`, tone: "danger" }
  }
  if (translationState.pending_count > 0) {
    return { label: `${providerLabel} 排队 ${translationState.pending_count}`, tone: "info" }
  }
  return { label: `${providerLabel} 就绪`, tone: "success" }
}

export function resolveTtsSummary(
  ttsState: Pick<BackendTTSState, "available" | "auto_read_enabled" | "last_error" | "provider">,
): { label: string; tone: StatusBadgeTone } {
  const providerLabel = formatProviderName(ttsState.provider)
  if (!ttsState.available || ttsState.last_error) {
    return { label: `${providerLabel} 不可用`, tone: "warning" }
  }
  if (!ttsState.auto_read_enabled) {
    return { label: `${providerLabel} 手动`, tone: "neutral" }
  }
  return { label: `${providerLabel} 自动`, tone: "success" }
}

export function resolveRuntimeSummary(
  runtimeState: Pick<BackendRuntimeState, "message_fidelity" | "monitor_scope" | "worker_state">,
): {
  fidelityTone: StatusBadgeTone
  fidelityLabel: string
  scopeLabel: string
  workerTone: StatusBadgeTone
  workerLabel: string
} {
  const fidelityTone =
    runtimeState.message_fidelity === "preview_only" ? "preview" : "accent"
  const workerTone =
    runtimeState.worker_state === "running"
      ? "success"
      : runtimeState.worker_state === "worker_backoff"
        ? "warning"
        : "info"

  return {
    fidelityTone,
    fidelityLabel: formatFidelityLabel(runtimeState.message_fidelity),
    scopeLabel: formatMonitorScopeLabel(runtimeState.monitor_scope),
    workerTone,
    workerLabel: formatMachineStateLabel(runtimeState.worker_state),
  }
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
