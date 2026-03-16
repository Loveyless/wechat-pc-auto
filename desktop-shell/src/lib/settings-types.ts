export type DesktopSecretStatusSource = "direct" | "env" | "unset"

export type DesktopSecretStatus = {
  configured: boolean
  source: DesktopSecretStatusSource
  env_key?: string
}

export type DesktopSecretInputMode = "keep" | "direct" | "env" | "clear"

export type DesktopSecretInputDraft = {
  status: DesktopSecretStatus
  mode: DesktopSecretInputMode
  value: string
  env_key: string
}

export type DesktopTranslateConfig = {
  enabled: boolean
  provider: string
  available_providers: string[]
  source_lang: string
  target_lang: string
  timeout_seconds: number
  deeplx_url: DesktopSecretStatus
}

export type DesktopDisplayConfig = {
  english_only: boolean
  tts_auto_read_active_chat: boolean
  on_translate_fail: "show_cn_with_reason" | "show_cn" | "show_reason"
}

export type DesktopTtsProvider = "windows_system" | "doubao" | "tencent_cloud"

export type DesktopDoubaoProviderConfig = {
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

export type DesktopTtsProvidersConfig = {
  windows_system: Record<string, never>
  doubao: DesktopDoubaoProviderConfig
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

export type DesktopTranslateDraft = {
  enabled: boolean
  provider: string
  available_providers: string[]
  source_lang: string
  target_lang: string
  timeout_seconds: number
  deeplx_url: DesktopSecretInputDraft
}

export type DesktopDisplayDraft = DesktopDisplayConfig

export type DesktopDoubaoProviderDraft = {
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

export type DesktopSettingsDraft = {
  translate: DesktopTranslateDraft
  display: DesktopDisplayDraft
  tts: {
    provider: DesktopTtsProvider
    available_providers: DesktopTtsProvider[]
    providers: {
      windows_system: Record<string, never>
      doubao: DesktopDoubaoProviderDraft
      tencent_cloud: DesktopTencentCloudProviderDraft
    }
  }
  runtime: DesktopRuntimeConfigMeta
}

export type DesktopSecretDrafts = {
  translate: {
    deeplx_url: DesktopSecretInputDraft
  }
  tts: {
    doubao: {
      appid: DesktopSecretInputDraft
      access_token: DesktopSecretInputDraft
    }
    tencent_cloud: {
      secret_id: DesktopSecretInputDraft
      secret_key: DesktopSecretInputDraft
    }
  }
}

export type DesktopSecretUpdate =
  | { mode: "keep" }
  | { mode: "clear" }
  | { mode: "direct"; value: string }
  | { mode: "env"; env_key: string }

export type DesktopSettingsSavePayload = {
  translate: {
    enabled: boolean
    provider: string
    source_lang: string
    target_lang: string
    timeout_seconds: number
  }
  display: DesktopDisplayConfig
  tts: {
    provider: DesktopTtsProvider
    providers: {
      doubao: Omit<DesktopDoubaoProviderDraft, "appid" | "access_token">
      tencent_cloud: Omit<DesktopTencentCloudProviderDraft, "secret_id" | "secret_key">
    }
  }
  secret_updates: {
    translate: {
      deeplx_url: DesktopSecretUpdate
    }
    tts: {
      doubao: {
        appid: DesktopSecretUpdate
        access_token: DesktopSecretUpdate
      }
      tencent_cloud: {
        secret_id: DesktopSecretUpdate
        secret_key: DesktopSecretUpdate
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
