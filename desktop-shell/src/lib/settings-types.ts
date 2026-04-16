export type DesktopSecretStatusSource = "direct" | "env" | "unset"

export type DesktopSecretStatus = {
  configured: boolean
  source: DesktopSecretStatusSource
  env_key?: string
  value: string
}

export type DesktopSecretInputDraft = {
  status: DesktopSecretStatus
  value: string
  forceClear: boolean
}

export type DesktopTranslateProvider = "deeplx" | "openai_compatible" | "passthrough"

export type DesktopDeeplxProviderConfig = {
  timeout_seconds: number
  deeplx_url: DesktopSecretStatus
}

export type DesktopOpenAICompatibleProviderConfig = {
  base_url: string
  model: string
  timeout_seconds: number
  api_key: DesktopSecretStatus
}

export type DesktopTranslateProvidersConfig = {
  deeplx: DesktopDeeplxProviderConfig
  openai_compatible: DesktopOpenAICompatibleProviderConfig
  passthrough: Record<string, never>
}

export type DesktopTranslateConfig = {
  enabled: boolean
  provider: DesktopTranslateProvider
  available_providers: DesktopTranslateProvider[]
  source_lang: string
  target_lang: string
  providers: DesktopTranslateProvidersConfig
}

export type DesktopDisplayConfig = {
  english_only: boolean
  tts_auto_read_active_chat: boolean
  on_translate_fail: "show_cn_with_reason" | "show_cn" | "show_reason"
}

export type DesktopTtsProvider = "macos_system" | "doubao" | "less_tts" | "tencent_cloud"

export type DesktopDoubaoProviderConfig = {
  config_path: string
  endpoint: string
  resource_id: string
  speaker: string
  audio_format: string
  sample_rate: number
  speech_rate: number
  loudness_rate: number
  use_cache: boolean
  uid: string
  connect_timeout_seconds: number
  appid: DesktopSecretStatus
  access_token: DesktopSecretStatus
}

export type DesktopTencentCloudProviderConfig = {
  config_path: string
  endpoint: string
  region: string
  voice_type: number
  codec: string
  sample_rate: number
  speed: number
  volume: number
  primary_language: number
  model_type: number
  project_id: number
  segment_rate: number
  enable_subtitle: boolean
  emotion_category: string
  emotion_intensity: number
  request_timeout_seconds: number
  secret_id: DesktopSecretStatus
  secret_key: DesktopSecretStatus
}

export type DesktopLessTtsProviderConfig = {
  config_path: string
  endpoint: string
  api_key: DesktopSecretStatus
}

export type DesktopTtsProvidersConfig = {
  macos_system: Record<string, never>
  doubao: DesktopDoubaoProviderConfig
  less_tts: DesktopLessTtsProviderConfig
  tencent_cloud: DesktopTencentCloudProviderConfig
}

export type DesktopTtsConfig = {
  provider: DesktopTtsProvider
  available_providers: DesktopTtsProvider[]
  providers: DesktopTtsProvidersConfig
}

export type DesktopRuntimeConfigMeta = {
  config_path: string
  apply_strategy: string
  restart_required: boolean
  hot_reload_supported: boolean
}

export type DesktopRuntimeConfig = {
  translate: DesktopTranslateConfig
  display: DesktopDisplayConfig
  tts: DesktopTtsConfig
  runtime: DesktopRuntimeConfigMeta
}

export type DesktopDeeplxProviderDraft = {
  timeout_seconds: number
  deeplx_url: DesktopSecretInputDraft
}

export type DesktopOpenAICompatibleProviderDraft = {
  base_url: string
  model: string
  timeout_seconds: number
  api_key: DesktopSecretInputDraft
}

export type DesktopTranslateDraft = {
  enabled: boolean
  provider: DesktopTranslateProvider
  available_providers: DesktopTranslateProvider[]
  source_lang: string
  target_lang: string
  providers: {
    deeplx: DesktopDeeplxProviderDraft
    openai_compatible: DesktopOpenAICompatibleProviderDraft
    passthrough: Record<string, never>
  }
}

export type DesktopDisplayDraft = DesktopDisplayConfig

export type DesktopDoubaoProviderDraft = {
  config_path: string
  endpoint: string
  resource_id: string
  speaker: string
  audio_format: string
  sample_rate: number
  speech_rate: number
  loudness_rate: number
  use_cache: boolean
  uid: string
  connect_timeout_seconds: number
  appid: DesktopSecretInputDraft
  access_token: DesktopSecretInputDraft
}

export type DesktopTencentCloudProviderDraft = {
  config_path: string
  endpoint: string
  region: string
  voice_type: number
  codec: string
  sample_rate: number
  speed: number
  volume: number
  primary_language: number
  model_type: number
  project_id: number
  segment_rate: number
  enable_subtitle: boolean
  emotion_category: string
  emotion_intensity: number
  request_timeout_seconds: number
  secret_id: DesktopSecretInputDraft
  secret_key: DesktopSecretInputDraft
}

export type DesktopLessTtsProviderDraft = {
  config_path: string
  endpoint: string
  api_key: DesktopSecretInputDraft
}

export type DesktopSettingsDraft = {
  translate: DesktopTranslateDraft
  display: DesktopDisplayDraft
  tts: {
    provider: DesktopTtsProvider
    available_providers: DesktopTtsProvider[]
    providers: {
      macos_system: Record<string, never>
      doubao: DesktopDoubaoProviderDraft
      less_tts: DesktopLessTtsProviderDraft
      tencent_cloud: DesktopTencentCloudProviderDraft
    }
  }
  runtime: DesktopRuntimeConfigMeta
}

export type DesktopSecretDrafts = {
  translate: {
    deeplx: {
      deeplx_url: DesktopSecretInputDraft
    }
    openai_compatible: {
      api_key: DesktopSecretInputDraft
    }
  }
  tts: {
    doubao: {
      appid: DesktopSecretInputDraft
      access_token: DesktopSecretInputDraft
    }
    less_tts: {
      api_key: DesktopSecretInputDraft
    }
    tencent_cloud: {
      secret_id: DesktopSecretInputDraft
      secret_key: DesktopSecretInputDraft
    }
  }
}

export type DesktopSecretUpdate = {
  value: string
}

export type DesktopSettingsSavePayload = {
  translate: {
    enabled: boolean
    provider: DesktopTranslateProvider
    source_lang: string
    target_lang: string
    providers: {
      deeplx: {
        timeout_seconds: number
      }
      openai_compatible: {
        base_url: string
        model: string
        timeout_seconds: number
      }
      passthrough: Record<string, never>
    }
  }
  display: DesktopDisplayConfig
  tts: {
    provider: DesktopTtsProvider
    providers: {
      doubao: Omit<DesktopDoubaoProviderDraft, "appid" | "access_token">
      less_tts: Omit<DesktopLessTtsProviderDraft, "api_key">
      tencent_cloud: Omit<DesktopTencentCloudProviderDraft, "secret_id" | "secret_key">
    }
  }
  secret_updates: {
    translate: {
      deeplx?: {
        deeplx_url?: DesktopSecretUpdate
      }
      openai_compatible?: {
        api_key?: DesktopSecretUpdate
      }
    }
    tts: {
      doubao?: {
        appid?: DesktopSecretUpdate
        access_token?: DesktopSecretUpdate
      }
      less_tts?: {
        api_key?: DesktopSecretUpdate
      }
      tencent_cloud?: {
        secret_id?: DesktopSecretUpdate
        secret_key?: DesktopSecretUpdate
      }
    }
  }
}

export type DesktopSettingsSaveIntent = "save" | "apply"

export type DesktopSettingsActionState = {
  mode: "save_only" | "save_and_apply"
  title: string
  detail: string
  saveLabel: string
  applyLabel: string
}

export type DesktopSettingsApplyMode = "save_only" | "managed"
