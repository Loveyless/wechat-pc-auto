import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it, vi } from "vitest"

import { SettingsWorkspace } from "@/components/shell/settings-workspace"
import {
  createDesktopSettingsDraft,
  extractDesktopSecretDrafts,
  resolveDesktopSettingsActionState,
} from "@/hooks/use-desktop-settings"
import type { UseDesktopSettingsResult } from "@/hooks/use-desktop-settings"
import type {
  DesktopRuntimeConfig,
  DesktopTranslateProvider,
  DesktopTtsProvider,
} from "@/lib/settings-types"

function createRuntimeConfig(params: {
  translateProvider: DesktopTranslateProvider
  ttsProvider: DesktopTtsProvider
}): DesktopRuntimeConfig {
  return {
    translate: {
      enabled: true,
      provider: params.translateProvider,
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
          base_url: "https://openai-compatible.local/v1",
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
      provider: params.ttsProvider,
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

function createSettingsResult(params: {
  translateProvider: DesktopTranslateProvider
  ttsProvider: DesktopTtsProvider
  managedApply: boolean
}): UseDesktopSettingsResult {
  const config = createRuntimeConfig(params)
  const draft = createDesktopSettingsDraft(config)
  const secretDrafts = extractDesktopSecretDrafts(draft)
  const actionState = resolveDesktopSettingsActionState({
    config,
    backendInfo: {
      httpBaseUrl: "http://127.0.0.1:8765",
      wsUrl: "ws://127.0.0.1:8766/events",
      managed: params.managedApply,
      ownsBackend: params.managedApply,
      restartSupported: params.managedApply,
      startupError: "",
      runtimeRoot: "D:/runtime",
    },
  })

  return {
    isOpen: true,
    openSettings: vi.fn(async () => {}),
    closeSettings: vi.fn(),
    reloadSettings: vi.fn(async () => {}),
    reload: vi.fn(async () => {}),
    loading: false,
    saving: false,
    draft,
    secretDrafts,
    fieldErrors: {},
    saveError: "",
    errorMessage: "",
    saveNotice: "",
    saveMessage: "",
    isDirty: true,
    actionState,
    applyMode: actionState.mode === "save_and_apply" ? "managed" : "save_only",
    setDraft: vi.fn(),
    setSecretDrafts: vi.fn(),
    saveSettings: vi.fn(async () => true),
    save: vi.fn(async () => true),
    updateTranslateField: vi.fn(),
    updateDisplayField: vi.fn(),
    updateTtsProvider: vi.fn(),
    updateDoubaoField: vi.fn(),
    updateTencentField: vi.fn(),
    updateTranslateSecret: vi.fn(),
    updateDoubaoSecret: vi.fn(),
    updateTencentSecret: vi.fn(),
  }
}

describe("settings workspace", () => {
  it("renders translate provider branches for deeplx, openai_compatible, and passthrough", () => {
    const deeplxMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "macos_system",
          managedApply: false,
        })}
      />,
    )
    const openAiMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "openai_compatible",
          ttsProvider: "macos_system",
          managedApply: false,
        })}
      />,
    )
    const passthroughMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "passthrough",
          ttsProvider: "macos_system",
          managedApply: false,
        })}
      />,
    )

    expect(deeplxMarkup).toContain("DeepLX Timeout")
    expect(deeplxMarkup).toContain("DeepLX URL")
    expect(deeplxMarkup).toContain("value=\"https://deeplx.local\"")
    expect(openAiMarkup).toContain("Base URL")
    expect(openAiMarkup).toContain("Model")
    expect(openAiMarkup).toContain("API Key")
    expect(openAiMarkup).toContain("value=\"openai-token\"")
    expect(openAiMarkup).not.toContain("改成环境变量")
    expect(passthroughMarkup).toContain("不请求外部翻译 provider")
  })

  it("keeps cloud TTS core fields visible and groups secondary tuning under advanced sections", () => {
    const doubaoMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "doubao",
          managedApply: false,
        })}
      />,
    )
    const lessTtsMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "less_tts",
          managedApply: false,
        })}
      />,
    )
    const tencentMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "tencent_cloud",
          managedApply: false,
        })}
      />,
    )

    expect(doubaoMarkup).toContain("Config Path")
    expect(doubaoMarkup).toContain("豆包 App ID")
    expect(doubaoMarkup).toContain("高级参数")
    expect(doubaoMarkup).toContain("Speech Rate")
    expect(lessTtsMarkup).toContain("Config Path")
    expect(lessTtsMarkup).toContain("API Key")
    expect(lessTtsMarkup).toContain("MP3 播放链")
    expect(lessTtsMarkup).toContain("旧环境变量 LESS_TTS_API_KEY")
    expect(lessTtsMarkup).toContain("清空配置")
    expect(lessTtsMarkup).toContain("输入新值会改成直接值")
    expect(tencentMarkup).toContain("Config Path")
    expect(tencentMarkup).toContain("Tencent Secret ID")
    expect(tencentMarkup).toContain("高级参数")
    expect(tencentMarkup).toContain("Emotion Intensity")
  })

  it("renders pending clear state for legacy env-backed secrets", () => {
    const settings = createSettingsResult({
      translateProvider: "deeplx",
      ttsProvider: "less_tts",
      managedApply: false,
    })
    settings.draft!.tts.providers.less_tts.api_key.forceClear = true

    const markup = renderToStaticMarkup(<SettingsWorkspace settings={settings} />)

    expect(markup).toContain("取消清空")
    expect(markup).toContain("待清空")
    expect(markup).toContain("这次保存会删除直接值，并移除旧环境变量引用")
  })

  it("renders provider-specific branches for macos_system, doubao, less_tts, and tencent_cloud", () => {
    const macosMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "macos_system",
          managedApply: false,
        })}
      />,
    )
    const doubaoMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "doubao",
          managedApply: false,
        })}
      />,
    )
    const lessTtsMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "less_tts",
          managedApply: false,
        })}
      />,
    )
    const tencentMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "tencent_cloud",
          managedApply: false,
        })}
      />,
    )

    expect(macosMarkup).toContain("内建 macOS")
    expect(macosMarkup).toContain("config_path")
    expect(macosMarkup).not.toContain("豆包 App ID")
    expect(doubaoMarkup).toContain("豆包 App ID")
    expect(doubaoMarkup).toContain("豆包 Access Token")
    expect(lessTtsMarkup).toContain("Less TTS HTTP endpoint")
    expect(lessTtsMarkup).toContain("API Key")
    expect(tencentMarkup).toContain("Tencent Secret ID")
    expect(tencentMarkup).toContain("Tencent Secret Key")
  })

  it("renders the TTS selector with macos_system and no legacy windows_system option", () => {
    const markup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "macos_system",
          managedApply: false,
        })}
      />,
    )

    expect(markup).toContain("option value=\"macos_system\"")
    expect(markup).toContain("macOS 系统朗读")
    expect(markup).not.toContain("option value=\"windows_system\"")
  })

  it("switches CTA copy between save-only and save-and-apply modes", () => {
    const saveOnlyMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "macos_system",
          managedApply: false,
        })}
      />,
    )
    const applyMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "macos_system",
          managedApply: true,
        })}
      />,
    )

    expect(saveOnlyMarkup).toContain("保存设置")
    expect(saveOnlyMarkup).not.toContain("保存并应用")
    expect(applyMarkup).toContain("仅保存")
    expect(applyMarkup).toContain("保存并应用")
  })

  it("renders all boolean config fields as accessible switches", () => {
    const macosMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "macos_system",
          managedApply: false,
        })}
      />,
    )
    const doubaoMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "doubao",
          managedApply: false,
        })}
      />,
    )
    const tencentMarkup = renderToStaticMarkup(
      <SettingsWorkspace
        settings={createSettingsResult({
          translateProvider: "deeplx",
          ttsProvider: "tencent_cloud",
          managedApply: false,
        })}
      />,
    )

    expect(macosMarkup.match(/role=\"switch\"/g)?.length ?? 0).toBe(3)
    expect(doubaoMarkup.match(/role=\"switch\"/g)?.length ?? 0).toBe(4)
    expect(tencentMarkup.match(/role=\"switch\"/g)?.length ?? 0).toBe(4)
    expect(macosMarkup).toContain("aria-checked=\"true\"")
    expect(tencentMarkup).toContain("aria-checked=\"false\"")
  })
})
