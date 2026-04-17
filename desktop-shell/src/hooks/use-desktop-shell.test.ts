import { describe, expect, it } from "vitest"

import { applyTtsUpdatedEvent } from "@/hooks/use-desktop-shell"
import type { BackendTTSState, BackendTtsUpdatedPayload } from "@/lib/shell-types"

describe("useDesktopShell tts event state", () => {
  it("uses explicit runtime snapshot fields from tts.updated payload", () => {
    const current: BackendTTSState = {
      auto_read_enabled: true,
      provider: "less_tts",
      available: false,
      last_error: "stale failure",
    }
    const payload: BackendTtsUpdatedPayload = {
      action: "playback_result",
      session_id: "",
      message_id: "",
      accepted: true,
      provider: "less_tts",
      detail: "",
      available: true,
      last_error: "",
    }

    expect(applyTtsUpdatedEvent(current, payload)).toEqual({
      auto_read_enabled: true,
      provider: "less_tts",
      available: true,
      last_error: "",
    })
  })

  it("falls back to accepted/detail when legacy payload omits explicit state fields", () => {
    const current: BackendTTSState = {
      auto_read_enabled: false,
      provider: "macos_system",
      available: true,
      last_error: "old error",
    }
    const payload: BackendTtsUpdatedPayload = {
      action: "autoplay",
      session_id: "测试群",
      message_id: "m1",
      accepted: false,
      provider: "macos_system",
      detail: "tts rejected",
      auto_read_enabled: true,
    }

    expect(applyTtsUpdatedEvent(current, payload)).toEqual({
      auto_read_enabled: true,
      provider: "macos_system",
      available: true,
      last_error: "tts rejected",
    })
  })
})
