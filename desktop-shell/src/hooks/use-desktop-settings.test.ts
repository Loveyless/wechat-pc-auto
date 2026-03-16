import { describe, expect, it, vi } from "vitest"

import type { BackendConnectionInfo } from "@/lib/api"
import type { DesktopRuntimeConfig } from "@/lib/settings-types"
import {
  buildDesktopSettingsSavePayload,
  createDesktopSettingsDraft,
  isDesktopSettingsDirty,
  persistDesktopSettings,
  resolveDesktopSettingsActionState,
} from "@/hooks/use-desktop-settings"

function createRuntimeConfig(): DesktopRuntimeConfig {
  return {
    translate: {
      enabled: true,
      provider: "deeplx",
      available_providers: ["deeplx", "passthrough"],
      source_lang: "auto",
      target_lang: "EN",
      timeout_seconds: 8,
      deeplx_url: {
        configured: true,
        source: "env",
        env_key: "DEEPLX_URL",
      },
    },
    display: {
      english_only: true,
      tts_auto_read_active_chat: true,
      on_translate_fail: "show_cn_with_reason",
    },
    tts: {
      provider: "windows_system",
      available_providers: ["windows_system", "doubao", "tencent_cloud"],
      providers: {
        windows_system: {},
        doubao: {
          endpoint: "wss://doubao.local",
          resource_id: "res-id",
          speaker: "speaker-a",
          audio_format: "wav",
          sample_rate: 32000,
          speech_rate: -10,
          loudness_rate: 0,
          use_cache: true,
          uid: "wechat-pc-auto",
          connect_timeout_seconds: 10,
          appid: {
            configured: false,
            source: "env",
            env_key: "VOLCENGINE_TTS_APPID",
          },
          access_token: {
            configured: false,
            source: "env",
            env_key: "VOLCENGINE_TTS_ACCESS_TOKEN",
          },
        },
        tencent_cloud: {
          endpoint: "tts.tencentcloudapi.com",
          region: "ap-shanghai",
          voice_type: 501008,
          codec: "wav",
          sample_rate: 16000,
          speed: 0,
          volume: 0,
          primary_language: 2,
          model_type: 1,
          project_id: 0,
          segment_rate: 0,
          enable_subtitle: false,
          emotion_category: "",
          emotion_intensity: 100,
          request_timeout_seconds: 15,
          secret_id: {
            configured: false,
            source: "env",
            env_key: "TENCENTCLOUD_SECRET_ID",
          },
          secret_key: {
            configured: false,
            source: "env",
            env_key: "TENCENTCLOUD_SECRET_KEY",
          },
        },
      },
    },
    runtime: {
      config_path: "D:/runtime/config/listener.json",
      apply_strategy: "restart_required",
      restart_required: true,
      hot_reload_supported: false,
    },
  }
}

function createBackendInfo(
  overrides: Partial<BackendConnectionInfo> = {},
): BackendConnectionInfo {
  return {
    httpBaseUrl: "http://127.0.0.1:8765",
    wsUrl: "ws://127.0.0.1:8766/events",
    managed: false,
    ownsBackend: false,
    restartSupported: false,
    startupError: "",
    runtimeRoot: "D:/runtime",
    ...overrides,
  }
}

describe("desktop settings state", () => {
  it("keeps a fresh draft clean until persisted config fields actually change", () => {
    const config = createRuntimeConfig()
    const draft = createDesktopSettingsDraft(config)

    expect(isDesktopSettingsDirty(config, draft)).toBe(false)

    draft.display.tts_auto_read_active_chat = false

    expect(isDesktopSettingsDirty(config, draft)).toBe(true)
  })

  it("builds write-only secret updates without leaking raw secret status back into payload", () => {
    const draft = createDesktopSettingsDraft(createRuntimeConfig())

    draft.tts.provider = "doubao"
    draft.translate.deeplx_url.mode = "env"
    draft.translate.deeplx_url.env_key = "DEEPLX_URL_OVERRIDE"
    draft.tts.providers.doubao.appid.mode = "direct"
    draft.tts.providers.doubao.appid.value = "new-app-id"
    draft.tts.providers.doubao.access_token.mode = "clear"

    const payload = buildDesktopSettingsSavePayload(draft)

    expect(payload.translate.provider).toBe("deeplx")
    expect(payload.secret_updates.translate.deeplx_url).toEqual({
      mode: "env",
      env_key: "DEEPLX_URL_OVERRIDE",
    })
    expect(payload.secret_updates.tts.doubao.appid).toEqual({
      mode: "direct",
      value: "new-app-id",
    })
    expect(payload.secret_updates.tts.doubao.access_token).toEqual({
      mode: "clear",
    })
    expect(payload.secret_updates.tts.tencent_cloud.secret_key).toEqual({
      mode: "keep",
    })
  })

  it("enables save_and_apply only for owned managed connections with restart support", () => {
    const config = createRuntimeConfig()

    expect(
      resolveDesktopSettingsActionState({
        config,
        backendInfo: createBackendInfo({
          managed: true,
          ownsBackend: true,
          restartSupported: true,
        }),
      }).mode,
    ).toBe("save_and_apply")

    expect(
      resolveDesktopSettingsActionState({
        config,
        backendInfo: createBackendInfo({
          managed: true,
          ownsBackend: false,
          restartSupported: true,
        }),
      }).mode,
    ).toBe("save_only")
  })

  it("persists config before invoking managed apply and reconnect callback", async () => {
    const config = createRuntimeConfig()
    const draft = createDesktopSettingsDraft(config)
    const callOrder: string[] = []
    const actionState = resolveDesktopSettingsActionState({
      config,
      backendInfo: createBackendInfo({
        managed: true,
        ownsBackend: true,
        restartSupported: true,
      }),
    })

    const result = await persistDesktopSettings({
      draft,
      actionState,
      intent: "apply",
      deps: {
        saveConfig: vi.fn(async () => {
          callOrder.push("save")
          return config
        }),
        applyManagedRestart: vi.fn(async () => {
          callOrder.push("apply")
          return createBackendInfo({
            managed: true,
            ownsBackend: true,
            restartSupported: true,
          })
        }),
        onApplied: vi.fn(async () => {
          callOrder.push("notify")
        }),
      },
    })

    expect(result.outcome).toBe("saved")
    if (result.outcome !== "saved") {
      throw new Error("expected saved outcome")
    }
    expect(result.notice).toContain("已重启当前托管 backend")
    expect(callOrder).toEqual(["save", "apply", "notify"])
  })

  it("does not invoke managed apply on save-only connections even if intent is apply", async () => {
    const config = createRuntimeConfig()
    const draft = createDesktopSettingsDraft(config)
    const actionState = resolveDesktopSettingsActionState({
      config,
      backendInfo: createBackendInfo({
        managed: true,
        ownsBackend: false,
        restartSupported: true,
      }),
    })
    const applyManagedRestart = vi.fn(async () =>
      createBackendInfo({
        managed: true,
        ownsBackend: true,
        restartSupported: true,
      }),
    )

    const result = await persistDesktopSettings({
      draft,
      actionState,
      intent: "apply",
      deps: {
        saveConfig: vi.fn(async () => config),
        applyManagedRestart,
      },
    })

    expect(result.outcome).toBe("saved")
    if (result.outcome !== "saved") {
      throw new Error("expected saved outcome")
    }
    expect(result.notice).toContain("仅支持 save-only")
    expect(applyManagedRestart).not.toHaveBeenCalled()
  })

  it("keeps the saved config result when managed apply fails", async () => {
    const config = createRuntimeConfig()
    const draft = createDesktopSettingsDraft(config)
    const actionState = resolveDesktopSettingsActionState({
      config,
      backendInfo: createBackendInfo({
        managed: true,
        ownsBackend: true,
        restartSupported: true,
      }),
    })

    const result = await persistDesktopSettings({
      draft,
      actionState,
      intent: "apply",
      deps: {
        saveConfig: vi.fn(async () => config),
        applyManagedRestart: vi.fn(async () => {
          throw new Error("restart backend failed")
        }),
      },
    })

    expect(result).toEqual({
      outcome: "saved_apply_failed",
      config,
      errorMessage: "restart backend failed",
    })
  })
})
