import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it, vi } from "vitest"

import type { UseDesktopSettingsResult } from "@/hooks/use-desktop-settings"
import type { DesktopRuntimeConfig, DesktopTtsProvider } from "@/lib/settings-types"
import {
  createDesktopSettingsDraft,
  extractDesktopSecretDrafts,
  resolveDesktopSettingsActionState,
} from "@/hooks/use-desktop-settings"
import { SettingsWorkspace } from "@/components/shell/settings-workspace"

function createRuntimeConfig(provider: DesktopTtsProvider): DesktopRuntimeConfig {
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
      provider,
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

function createSettingsResult(params: {
  provider: DesktopTtsProvider
  managedApply: boolean
}): UseDesktopSettingsResult {
  const config = createRuntimeConfig(params.provider)
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
  it("renders provider-specific branches for windows_system, doubao, and tencent_cloud", () => {
    const windowsMarkup = renderToStaticMarkup(
      <SettingsWorkspace settings={createSettingsResult({ provider: "windows_system", managedApply: false })} />,
    )
    const doubaoMarkup = renderToStaticMarkup(
      <SettingsWorkspace settings={createSettingsResult({ provider: "doubao", managedApply: false })} />,
    )
    const tencentMarkup = renderToStaticMarkup(
      <SettingsWorkspace settings={createSettingsResult({ provider: "tencent_cloud", managedApply: false })} />,
    )

    expect(windowsMarkup).toContain("没有 provider-private 表单")
    expect(doubaoMarkup).toContain("App ID")
    expect(doubaoMarkup).toContain("Access Token")
    expect(tencentMarkup).toContain("Secret ID")
    expect(tencentMarkup).toContain("Emotion Intensity")
  })

  it("switches CTA copy between save-only and save-and-apply modes", () => {
    const saveOnlyMarkup = renderToStaticMarkup(
      <SettingsWorkspace settings={createSettingsResult({ provider: "windows_system", managedApply: false })} />,
    )
    const applyMarkup = renderToStaticMarkup(
      <SettingsWorkspace settings={createSettingsResult({ provider: "windows_system", managedApply: true })} />,
    )

    expect(saveOnlyMarkup).toContain("保存设置")
    expect(saveOnlyMarkup).not.toContain("保存并应用")
    expect(applyMarkup).toContain("仅保存")
    expect(applyMarkup).toContain("保存并应用")
  })
})
