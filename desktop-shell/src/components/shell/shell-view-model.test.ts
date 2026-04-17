import { describe, expect, it } from "vitest"

import {
  resolveConnectionBannerState,
  resolveConnectionOverviewState,
  resolveDataEmptyState,
  resolveMessagePresentation,
  resolveRuntimeSummary,
  resolveTranslationSummary,
  resolveTtsSummary,
  resolveUnreadTone,
} from "@/components/shell/shell-view-model"

describe("shell view model", () => {
  it("maps ready and startup_failed connection states to distinct overview tones", () => {
    expect(resolveConnectionOverviewState("ready", "")).toMatchObject({
      label: "已就绪",
      tone: "success",
    })
    expect(resolveConnectionOverviewState("startup_failed", "boom")).toMatchObject({
      label: "启动失败",
      tone: "danger",
      detail: "boom",
    })
  })

  it("keeps degraded and reconnecting separate", () => {
    expect(resolveConnectionOverviewState("degraded", "")).toMatchObject({
      tone: "warning",
    })
    expect(resolveConnectionOverviewState("reconnecting", "")).toMatchObject({
      tone: "info",
    })
    expect(resolveConnectionBannerState("degraded", "lagging")).toEqual({
      label: "降级运行",
      tone: "warning",
      title: "Runtime 处于降级运行",
      detail: "lagging",
    })
    expect(resolveConnectionBannerState("ready", "")).toBeNull()
  })

  it("keeps unread tone stable without per-session badge helpers", () => {
    expect(resolveUnreadTone(2)).toBe("unread")
    expect(resolveUnreadTone(0)).toBe("neutral")
  })

  it("prioritizes display text after translation is ready", () => {
    expect(
      resolveMessagePresentation({
        display: "display",
        translated: "translated",
        original: "original",
        captureLevel: "preview",
        pendingTranslation: false,
      }),
    ).toEqual({
      primaryText: "display",
      fidelityLabel: "预览",
      fidelityTone: "preview",
      translationLabel: null,
      translationTone: null,
      showPendingIndicator: false,
      pendingText: null,
    })
  })

  it("hides original text and exposes loading state while translation is pending", () => {
    expect(
      resolveMessagePresentation({
        display: "中文原文",
        translated: "",
        original: "中文原文",
        captureLevel: "preview",
        pendingTranslation: true,
      }),
    ).toEqual({
      primaryText: "",
      fidelityLabel: "预览",
      fidelityTone: "preview",
      translationLabel: "翻译中",
      translationTone: "info",
      showPendingIndicator: true,
      pendingText: "等待翻译…",
    })
  })

  it("surfaces translation and tts pipeline summaries without changing backend contract", () => {
    expect(
      resolveTranslationSummary({
        enabled: true,
        pending_count: 1,
        last_error: "",
        provider: "deeplx",
      }),
    ).toEqual({ label: "DeepLX 排队 1", tone: "info" })
    expect(
      resolveTtsSummary({
        available: false,
        auto_read_enabled: true,
        last_error: "missing module",
        provider: "windows_system",
      }),
    ).toEqual({ label: "系统朗读 不可用", tone: "warning" })
    expect(
      resolveTtsSummary({
        available: true,
        auto_read_enabled: true,
        last_error: "less_tts request failed status=403",
        provider: "macos_system",
      }),
    ).toEqual({ label: "系统朗读 异常", tone: "warning" })
  })

  it("maps runtime fidelity and worker states into reusable tones", () => {
    expect(
      resolveRuntimeSummary({
        message_fidelity: "preview_only",
        monitor_scope: "all_sessions",
        worker_state: "running",
      }),
    ).toEqual({
      fidelityTone: "preview",
      fidelityLabel: "预览模式",
      scopeLabel: "全部会话",
      workerTone: "success",
      workerLabel: "运行中",
    })
  })

  it("prioritizes abnormal connection states ahead of data-empty branches", () => {
    expect(
      resolveDataEmptyState({
        connectionState: "startup_failed",
        sessionCount: 0,
        selectedSessionId: "",
        selectedMessageCount: 0,
      }),
    ).toBeNull()
  })

  it("distinguishes no sessions from no messages when runtime is otherwise renderable", () => {
    expect(
      resolveDataEmptyState({
        connectionState: "ready",
        sessionCount: 0,
        selectedSessionId: "",
        selectedMessageCount: 0,
      }),
    ).toBe("no-sessions")
    expect(
      resolveDataEmptyState({
        connectionState: "degraded",
        sessionCount: 2,
        selectedSessionId: "session-1",
        selectedMessageCount: 0,
      }),
    ).toBe("no-messages")
  })
})
