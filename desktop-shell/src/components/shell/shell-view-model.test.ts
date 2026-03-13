import { describe, expect, it } from "vitest"

import {
  resolveConnectionBannerState,
  resolveConnectionOverviewState,
  resolveDataEmptyState,
  resolveMessagePresentation,
  resolveRuntimeSummary,
  resolveSessionFidelityBadge,
  resolveSessionKindBadge,
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

  it("maps session kind, unread, and preview fidelity to stable badge semantics", () => {
    expect(resolveSessionKindBadge("group")).toEqual({ label: "群聊", tone: "accent" })
    expect(resolveUnreadTone(2)).toBe("unread")
    expect(resolveSessionFidelityBadge({ previewOnly: true })).toEqual({
      label: "PREVIEW",
      tone: "preview",
    })
  })

  it("prioritizes display text and preserves preview and translating cues", () => {
    expect(
      resolveMessagePresentation({
        display: "display",
        translated: "translated",
        original: "original",
        captureLevel: "preview",
        pendingTranslation: true,
      }),
    ).toEqual({
      primaryText: "display",
      fidelityLabel: "PREVIEW",
      fidelityTone: "preview",
      translationLabel: "TRANSLATING",
      translationTone: "info",
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
    ).toEqual({ label: "translate:deeplx:1", tone: "info" })
    expect(
      resolveTtsSummary({
        available: false,
        auto_read_enabled: true,
        last_error: "missing module",
        provider: "windows_system",
      }),
    ).toEqual({ label: "tts:windows_system:blocked", tone: "warning" })
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
      workerTone: "success",
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
