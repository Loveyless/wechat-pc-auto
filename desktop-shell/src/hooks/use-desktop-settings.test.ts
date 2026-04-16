import { describe, expect, it, vi } from "vitest"

import type { BackendConnectionInfo } from "@/lib/api"
import type { DesktopRuntimeConfig } from "@/lib/settings-types"
import {
  buildDesktopSettingsSavePayload,
  createDesktopSettingsDraft,
  isDesktopSettingsDirty,
  persistDesktopSettings,
  resolveConfigSaveErrorMessage,
  resolveDesktopSettingsActionState,
} from "@/hooks/use-desktop-settings"
import { ConfigSaveError } from "@/lib/api"

function createRuntimeConfig(): DesktopRuntimeConfig {
  return {
    translate: {
      enabled: true,
      provider: "deeplx",
      available_providers: ["deeplx", "openai_compatible", "passthrough"],
      source_lang: "auto",
      target_lang: "EN",
      providers: {
        deeplx: {
          timeout_seconds: 8,
          deeplx_url: {
            configured: true,
            source: "env",
            env_key: "DEEPLX_URL",
            value: "https://deeplx.local",
          },
        },
        openai_compatible: {
          base_url: "https://openrouter.local/v1",
          model: "gpt-4o-mini",
          timeout_seconds: 12,
          api_key: {
            configured: true,
            source: "direct",
            value: "openai-token",
          },
        },
        passthrough: {},
      },
    },
    display: {
      english_only: true,
      tts_auto_read_active_chat: true,
      on_translate_fail: "show_cn_with_reason",
    },
    tts: {
      provider: "macos_system",
      available_providers: ["macos_system", "doubao", "less_tts", "tencent_cloud"],
      providers: {
        macos_system: {},
        doubao: {
          config_path: "config/doubao_tts.json",
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
            value: "",
          },
          access_token: {
            configured: false,
            source: "env",
            env_key: "VOLCENGINE_TTS_ACCESS_TOKEN",
            value: "",
          },
        },
        less_tts: {
          config_path: "config/less_tts.json",
          endpoint: "https://less-tts.example/v1/audio/speech",
          api_key: {
            configured: false,
            source: "env",
            env_key: "LESS_TTS_API_KEY",
            value: "",
          },
        },
        tencent_cloud: {
          config_path: "config/tencent_tts.json",
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
            value: "",
          },
          secret_key: {
            configured: false,
            source: "env",
            env_key: "TENCENTCLOUD_SECRET_KEY",
            value: "",
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

  it("echoes current secret values into the draft and only saves changed secrets as direct values", () => {
    const draft = createDesktopSettingsDraft(createRuntimeConfig())

    expect(draft.translate.providers.deeplx.deeplx_url.value).toBe("https://deeplx.local")
    expect(draft.translate.providers.openai_compatible.api_key.value).toBe("openai-token")

    draft.tts.provider = "doubao"
    draft.translate.providers.deeplx.deeplx_url.value = "https://deeplx.override"
    draft.translate.providers.openai_compatible.api_key.value = "next-openai-token"
    draft.tts.providers.doubao.appid.value = "new-app-id"
    draft.tts.providers.doubao.access_token.value = ""

    const payload = buildDesktopSettingsSavePayload(draft)
    const deeplxUpdates = payload.secret_updates.translate.deeplx
    const openAiUpdates = payload.secret_updates.translate.openai_compatible
    const doubaoUpdates = payload.secret_updates.tts.doubao

    expect(payload.translate.provider).toBe("deeplx")
    expect(payload.translate.providers.deeplx.timeout_seconds).toBe(8)
    expect(deeplxUpdates).toBeDefined()
    expect(openAiUpdates).toBeDefined()
    expect(doubaoUpdates).toBeDefined()
    expect(deeplxUpdates!.deeplx_url).toEqual({
      value: "https://deeplx.override",
    })
    expect(openAiUpdates!.api_key).toEqual({
      value: "next-openai-token",
    })
    expect(doubaoUpdates!.appid).toEqual({
      value: "new-app-id",
    })
    expect(doubaoUpdates!.access_token).toBeUndefined()
    expect(payload.secret_updates.tts.tencent_cloud).toBeUndefined()
    expect(payload.secret_updates.tts.less_tts).toBeUndefined()
  })

  it("omits unchanged secret updates when saving unrelated fields", () => {
    const draft = createDesktopSettingsDraft(createRuntimeConfig())

    draft.display.english_only = false

    const payload = buildDesktopSettingsSavePayload(draft)

    expect(payload.display.english_only).toBe(false)
    expect(payload.secret_updates.translate).toEqual({})
    expect(payload.secret_updates.tts).toEqual({})
  })

  it("allows explicitly clearing a legacy env-backed secret even when the echoed value is empty", () => {
    const draft = createDesktopSettingsDraft(createRuntimeConfig())

    draft.tts.provider = "less_tts"
    draft.tts.providers.less_tts.api_key.forceClear = true

    const payload = buildDesktopSettingsSavePayload(draft)

    expect(payload.secret_updates.tts.less_tts).toEqual({
      api_key: {
        value: "",
      },
    })
  })

  it("preserves provider-specific translate payload branches when switching to openai_compatible", () => {
    const draft = createDesktopSettingsDraft(createRuntimeConfig())

    draft.translate.provider = "openai_compatible"
    draft.translate.providers.openai_compatible.base_url = "https://gateway.local/v1"
    draft.translate.providers.openai_compatible.model = "gpt-4.1-mini"
    draft.translate.providers.openai_compatible.timeout_seconds = 18
    draft.translate.providers.openai_compatible.api_key.value = ""

    const payload = buildDesktopSettingsSavePayload(draft)
    const openAiUpdates = payload.secret_updates.translate.openai_compatible

    expect(payload.translate.provider).toBe("openai_compatible")
    expect(payload.translate.providers.openai_compatible).toEqual({
      base_url: "https://gateway.local/v1",
      model: "gpt-4.1-mini",
      timeout_seconds: 18,
    })
    expect(payload.translate.providers.passthrough).toEqual({})
    expect(openAiUpdates).toBeDefined()
    expect(openAiUpdates!.api_key).toEqual({
      value: "",
    })
  })

  it("builds less_tts payload and direct api_key updates", () => {
    const draft = createDesktopSettingsDraft(createRuntimeConfig())

    draft.tts.provider = "less_tts"
    draft.tts.providers.less_tts.endpoint = "https://less-tts.changed/v1/audio/speech"
    draft.tts.providers.less_tts.api_key.value = "less-token"

    const payload = buildDesktopSettingsSavePayload(draft)
    const lessTtsUpdates = payload.secret_updates.tts.less_tts

    expect(payload.tts.provider).toBe("less_tts")
    expect(payload.tts.providers.less_tts).toEqual({
      config_path: "config/less_tts.json",
      endpoint: "https://less-tts.changed/v1/audio/speech",
    })
    expect(lessTtsUpdates).toBeDefined()
    expect(lessTtsUpdates!.api_key).toEqual({
      value: "less-token",
    })
  })

  it("surfaces field-level validation detail when backend only returns a generic save error", () => {
    const error = new ConfigSaveError("config validation failed", {
      "tts.providers.less_tts.api_key": "less_tts api_key is required",
    })

    expect(resolveConfigSaveErrorMessage(error)).toBe(
      "保存失败：less_tts api_key is required",
    )
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
