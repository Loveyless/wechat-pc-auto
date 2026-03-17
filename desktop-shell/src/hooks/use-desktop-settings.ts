import { useCallback, useMemo, useState, type Dispatch, type SetStateAction } from "react"

import {
  ConfigSaveError,
  type BackendConnectionInfo,
  fetchRuntimeConfig,
  restartManagedBackend,
  saveRuntimeConfig,
} from "@/lib/api"
import type {
  DesktopRuntimeConfig,
  DesktopSettingsApplyMode,
  DesktopSecretInputDraft,
  DesktopSecretStatus,
  DesktopSecretUpdate,
  DesktopSettingsActionState,
  DesktopSettingsDraft,
  DesktopSettingsSaveIntent,
  DesktopSettingsSavePayload,
  DesktopSecretDrafts,
} from "@/lib/settings-types"

const DEEPLX_ENV_KEY = "DEEPLX_URL"

function createSecretInputDraft(status: DesktopSecretStatus): DesktopSecretInputDraft {
  return {
    status: {
      ...status,
    },
    mode: "keep",
    value: "",
    env_key: status.env_key ?? "",
  }
}

function cloneDraft<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export function createDesktopSettingsDraft(config: DesktopRuntimeConfig): DesktopSettingsDraft {
  return {
    translate: {
      enabled: config.translate.enabled,
      provider: config.translate.provider,
      available_providers: [...config.translate.available_providers],
      source_lang: config.translate.source_lang,
      target_lang: config.translate.target_lang,
      providers: {
        deeplx: {
          timeout_seconds: config.translate.providers.deeplx.timeout_seconds,
          deeplx_url: createSecretInputDraft(config.translate.providers.deeplx.deeplx_url),
        },
        openai_compatible: {
          base_url: config.translate.providers.openai_compatible.base_url,
          model: config.translate.providers.openai_compatible.model,
          timeout_seconds: config.translate.providers.openai_compatible.timeout_seconds,
          api_key: createSecretInputDraft(config.translate.providers.openai_compatible.api_key),
        },
        passthrough: {},
      },
    },
    display: {
      english_only: config.display.english_only,
      tts_auto_read_active_chat: config.display.tts_auto_read_active_chat,
      on_translate_fail: config.display.on_translate_fail,
    },
    tts: {
      provider: config.tts.provider,
      available_providers: [...config.tts.available_providers],
      providers: {
        windows_system: {},
        doubao: {
          config_path: config.tts.providers.doubao.config_path,
          endpoint: config.tts.providers.doubao.endpoint,
          resource_id: config.tts.providers.doubao.resource_id,
          speaker: config.tts.providers.doubao.speaker,
          audio_format: config.tts.providers.doubao.audio_format,
          sample_rate: config.tts.providers.doubao.sample_rate,
          speech_rate: config.tts.providers.doubao.speech_rate,
          loudness_rate: config.tts.providers.doubao.loudness_rate,
          use_cache: config.tts.providers.doubao.use_cache,
          uid: config.tts.providers.doubao.uid,
          connect_timeout_seconds: config.tts.providers.doubao.connect_timeout_seconds,
          appid: createSecretInputDraft(config.tts.providers.doubao.appid),
          access_token: createSecretInputDraft(config.tts.providers.doubao.access_token),
        },
        tencent_cloud: {
          config_path: config.tts.providers.tencent_cloud.config_path,
          endpoint: config.tts.providers.tencent_cloud.endpoint,
          region: config.tts.providers.tencent_cloud.region,
          voice_type: config.tts.providers.tencent_cloud.voice_type,
          codec: config.tts.providers.tencent_cloud.codec,
          sample_rate: config.tts.providers.tencent_cloud.sample_rate,
          speed: config.tts.providers.tencent_cloud.speed,
          volume: config.tts.providers.tencent_cloud.volume,
          primary_language: config.tts.providers.tencent_cloud.primary_language,
          model_type: config.tts.providers.tencent_cloud.model_type,
          project_id: config.tts.providers.tencent_cloud.project_id,
          segment_rate: config.tts.providers.tencent_cloud.segment_rate,
          enable_subtitle: config.tts.providers.tencent_cloud.enable_subtitle,
          emotion_category: config.tts.providers.tencent_cloud.emotion_category,
          emotion_intensity: config.tts.providers.tencent_cloud.emotion_intensity,
          request_timeout_seconds: config.tts.providers.tencent_cloud.request_timeout_seconds,
          secret_id: createSecretInputDraft(config.tts.providers.tencent_cloud.secret_id),
          secret_key: createSecretInputDraft(config.tts.providers.tencent_cloud.secret_key),
        },
      },
    },
    runtime: {
      ...config.runtime,
    },
  }
}

export function extractDesktopSecretDrafts(
  draft: DesktopSettingsDraft | null,
): DesktopSecretDrafts | null {
  if (!draft) {
    return null
  }
  return {
    translate: {
      deeplx: {
        deeplx_url: cloneDraft(draft.translate.providers.deeplx.deeplx_url),
      },
      openai_compatible: {
        api_key: cloneDraft(draft.translate.providers.openai_compatible.api_key),
      },
    },
    tts: {
      doubao: {
        appid: cloneDraft(draft.tts.providers.doubao.appid),
        access_token: cloneDraft(draft.tts.providers.doubao.access_token),
      },
      tencent_cloud: {
        secret_id: cloneDraft(draft.tts.providers.tencent_cloud.secret_id),
        secret_key: cloneDraft(draft.tts.providers.tencent_cloud.secret_key),
      },
    },
  }
}

function mergeDesktopSecretDrafts(
  draft: DesktopSettingsDraft,
  secretDrafts: DesktopSecretDrafts,
): DesktopSettingsDraft {
  return {
    ...draft,
    translate: {
      ...draft.translate,
      providers: {
        ...draft.translate.providers,
        deeplx: {
          ...draft.translate.providers.deeplx,
          deeplx_url: cloneDraft(secretDrafts.translate.deeplx.deeplx_url),
        },
        openai_compatible: {
          ...draft.translate.providers.openai_compatible,
          api_key: cloneDraft(secretDrafts.translate.openai_compatible.api_key),
        },
      },
    },
    tts: {
      ...draft.tts,
      providers: {
        ...draft.tts.providers,
        doubao: {
          ...draft.tts.providers.doubao,
          config_path: draft.tts.providers.doubao.config_path,
          appid: cloneDraft(secretDrafts.tts.doubao.appid),
          access_token: cloneDraft(secretDrafts.tts.doubao.access_token),
        },
        tencent_cloud: {
          ...draft.tts.providers.tencent_cloud,
          config_path: draft.tts.providers.tencent_cloud.config_path,
          secret_id: cloneDraft(secretDrafts.tts.tencent_cloud.secret_id),
          secret_key: cloneDraft(secretDrafts.tts.tencent_cloud.secret_key),
        },
      },
    },
  }
}

function buildSecretUpdate(input: DesktopSecretInputDraft): DesktopSecretUpdate {
  switch (input.mode) {
    case "clear":
      return { mode: "clear" }
    case "direct":
      return { mode: "direct", value: input.value }
    case "env":
      return { mode: "env", env_key: input.env_key }
    default:
      return { mode: "keep" }
  }
}

function buildDeeplxSecretUpdate(input: DesktopSecretInputDraft): DesktopSecretUpdate {
  if (input.mode === "env") {
    return { mode: "env", env_key: DEEPLX_ENV_KEY }
  }
  return buildSecretUpdate(input)
}

export function buildDesktopSettingsSavePayload(
  draft: DesktopSettingsDraft,
): DesktopSettingsSavePayload {
  return {
    translate: {
      enabled: draft.translate.enabled,
      provider: draft.translate.provider,
      source_lang: draft.translate.source_lang,
      target_lang: draft.translate.target_lang,
      providers: {
        deeplx: {
          timeout_seconds: draft.translate.providers.deeplx.timeout_seconds,
        },
        openai_compatible: {
          base_url: draft.translate.providers.openai_compatible.base_url,
          model: draft.translate.providers.openai_compatible.model,
          timeout_seconds: draft.translate.providers.openai_compatible.timeout_seconds,
        },
        passthrough: {},
      },
    },
    display: {
      english_only: draft.display.english_only,
      tts_auto_read_active_chat: draft.display.tts_auto_read_active_chat,
      on_translate_fail: draft.display.on_translate_fail,
    },
    tts: {
      provider: draft.tts.provider,
      providers: {
        doubao: {
          config_path: draft.tts.providers.doubao.config_path,
          endpoint: draft.tts.providers.doubao.endpoint,
          resource_id: draft.tts.providers.doubao.resource_id,
          speaker: draft.tts.providers.doubao.speaker,
          audio_format: draft.tts.providers.doubao.audio_format,
          sample_rate: draft.tts.providers.doubao.sample_rate,
          speech_rate: draft.tts.providers.doubao.speech_rate,
          loudness_rate: draft.tts.providers.doubao.loudness_rate,
          use_cache: draft.tts.providers.doubao.use_cache,
          uid: draft.tts.providers.doubao.uid,
          connect_timeout_seconds: draft.tts.providers.doubao.connect_timeout_seconds,
        },
        tencent_cloud: {
          config_path: draft.tts.providers.tencent_cloud.config_path,
          endpoint: draft.tts.providers.tencent_cloud.endpoint,
          region: draft.tts.providers.tencent_cloud.region,
          voice_type: draft.tts.providers.tencent_cloud.voice_type,
          codec: draft.tts.providers.tencent_cloud.codec,
          sample_rate: draft.tts.providers.tencent_cloud.sample_rate,
          speed: draft.tts.providers.tencent_cloud.speed,
          volume: draft.tts.providers.tencent_cloud.volume,
          primary_language: draft.tts.providers.tencent_cloud.primary_language,
          model_type: draft.tts.providers.tencent_cloud.model_type,
          project_id: draft.tts.providers.tencent_cloud.project_id,
          segment_rate: draft.tts.providers.tencent_cloud.segment_rate,
          enable_subtitle: draft.tts.providers.tencent_cloud.enable_subtitle,
          emotion_category: draft.tts.providers.tencent_cloud.emotion_category,
          emotion_intensity: draft.tts.providers.tencent_cloud.emotion_intensity,
          request_timeout_seconds: draft.tts.providers.tencent_cloud.request_timeout_seconds,
        },
      },
    },
    secret_updates: {
      translate: {
        deeplx: {
          deeplx_url: buildDeeplxSecretUpdate(draft.translate.providers.deeplx.deeplx_url),
        },
        openai_compatible: {
          api_key: buildSecretUpdate(draft.translate.providers.openai_compatible.api_key),
        },
      },
      tts: {
        doubao: {
          appid: buildSecretUpdate(draft.tts.providers.doubao.appid),
          access_token: buildSecretUpdate(draft.tts.providers.doubao.access_token),
        },
        tencent_cloud: {
          secret_id: buildSecretUpdate(draft.tts.providers.tencent_cloud.secret_id),
          secret_key: buildSecretUpdate(draft.tts.providers.tencent_cloud.secret_key),
        },
      },
    },
  }
}

export function resolveDesktopSettingsActionState(params: {
  config: DesktopRuntimeConfig | null
  backendInfo: Pick<BackendConnectionInfo, "managed" | "ownsBackend" | "restartSupported">
}): DesktopSettingsActionState {
  const { config, backendInfo } = params
  if (
    config &&
    config.runtime.apply_strategy === "restart_required" &&
    backendInfo.managed &&
    backendInfo.ownsBackend &&
    backendInfo.restartSupported
  ) {
    return {
      mode: "save_and_apply",
      title: "当前连接允许保存并应用",
      detail: "桌面壳已确认 ownership，可在保存后重启当前 shell 自己拉起的 backend。",
      saveLabel: "仅保存",
      applyLabel: "保存并应用",
    }
  }
  return {
    mode: "save_only",
    title: "当前连接只能保存配置",
    detail: "没有 ownership 真值或缺少重启能力时，前端必须退回 save-only，避免误杀外部 backend。",
    saveLabel: "保存设置",
    applyLabel: "保存后手动重启",
  }
}

export function isDesktopSettingsDirty(
  config: DesktopRuntimeConfig | null,
  draft: DesktopSettingsDraft | null,
): boolean {
  if (!config || !draft) {
    return false
  }
  const nextPayload = JSON.stringify(buildDesktopSettingsSavePayload(draft))
  const initialPayload = JSON.stringify(
    buildDesktopSettingsSavePayload(createDesktopSettingsDraft(config)),
  )
  return nextPayload !== initialPayload
}

function resolveErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}

function resolveDesktopSettingsSavedNotice(
  actionState: DesktopSettingsActionState,
  applied: boolean,
): string {
  if (applied) {
    return "配置已保存，并已重启当前托管 backend。桌面壳会按现有连接链路自动恢复。"
  }
  if (actionState.mode === "save_and_apply") {
    return "配置已保存。当前连接已具备 apply 能力，可继续执行保存并应用。"
  }
  return "配置已保存。当前连接仅支持 save-only，需手动重启 backend 生效。"
}

export type PersistDesktopSettingsDependencies = {
  saveConfig: (payload: DesktopSettingsSavePayload) => Promise<DesktopRuntimeConfig>
  applyManagedRestart: () => Promise<BackendConnectionInfo>
  onApplied?: (backendInfo: BackendConnectionInfo) => Promise<void> | void
}

export type PersistDesktopSettingsResult =
  | {
      outcome: "saved"
      config: DesktopRuntimeConfig
      notice: string
    }
  | {
      outcome: "saved_apply_failed"
      config: DesktopRuntimeConfig
      errorMessage: string
    }

export async function persistDesktopSettings(params: {
  draft: DesktopSettingsDraft
  actionState: DesktopSettingsActionState
  intent?: DesktopSettingsSaveIntent
  deps: PersistDesktopSettingsDependencies
}): Promise<PersistDesktopSettingsResult> {
  const { draft, actionState, deps, intent = "save" } = params
  const nextConfig = await deps.saveConfig(buildDesktopSettingsSavePayload(draft))
  const shouldApply = intent === "apply" && actionState.mode === "save_and_apply"

  if (!shouldApply) {
    return {
      outcome: "saved",
      config: nextConfig,
      notice: resolveDesktopSettingsSavedNotice(actionState, false),
    }
  }

  try {
    const backendInfo = await deps.applyManagedRestart()
    try {
      await deps.onApplied?.(backendInfo)
    } catch {
      // WebSocket close/reconnect is already the fallback recovery path.
    }
    return {
      outcome: "saved",
      config: nextConfig,
      notice: resolveDesktopSettingsSavedNotice(actionState, true),
    }
  } catch (error) {
    return {
      outcome: "saved_apply_failed",
      config: nextConfig,
      errorMessage: resolveErrorMessage(error, "托管 backend 重启失败"),
    }
  }
}

type UseDesktopSettingsOptions = {
  onApply?: (backendInfo: BackendConnectionInfo) => Promise<void> | void
}

export type UseDesktopSettingsResult = {
  isOpen: boolean
  openSettings: () => Promise<void>
  closeSettings: () => void
  reloadSettings: () => Promise<void>
  reload: () => Promise<void>
  loading: boolean
  saving: boolean
  draft: DesktopSettingsDraft | null
  secretDrafts: DesktopSecretDrafts | null
  fieldErrors: Record<string, string>
  saveError: string
  errorMessage: string
  saveNotice: string
  saveMessage: string
  isDirty: boolean
  actionState: DesktopSettingsActionState
  applyMode: DesktopSettingsApplyMode
  setDraft: Dispatch<SetStateAction<DesktopSettingsDraft | null>>
  setSecretDrafts: Dispatch<SetStateAction<DesktopSecretDrafts | null>>
  saveSettings: (intent?: DesktopSettingsSaveIntent) => Promise<boolean>
  save: () => Promise<boolean>
  updateTranslateField: <K extends keyof DesktopSettingsDraft["translate"]>(
    key: K,
    value: DesktopSettingsDraft["translate"][K],
  ) => void
  updateDisplayField: <K extends keyof DesktopSettingsDraft["display"]>(
    key: K,
    value: DesktopSettingsDraft["display"][K],
  ) => void
  updateTtsProvider: (provider: DesktopSettingsDraft["tts"]["provider"]) => void
  updateDoubaoField: <K extends keyof DesktopSettingsDraft["tts"]["providers"]["doubao"]>(
    key: K,
    value: DesktopSettingsDraft["tts"]["providers"]["doubao"][K],
  ) => void
  updateTencentField: <K extends keyof DesktopSettingsDraft["tts"]["providers"]["tencent_cloud"]>(
    key: K,
    value: DesktopSettingsDraft["tts"]["providers"]["tencent_cloud"][K],
  ) => void
  updateTranslateSecret: (
    provider: "deeplx" | "openai_compatible",
    value: DesktopSecretInputDraft,
  ) => void
  updateDoubaoSecret: <K extends "appid" | "access_token">(
    key: K,
    value: DesktopSettingsDraft["tts"]["providers"]["doubao"][K],
  ) => void
  updateTencentSecret: <K extends "secret_id" | "secret_key">(
    key: K,
    value: DesktopSettingsDraft["tts"]["providers"]["tencent_cloud"][K],
  ) => void
}

export function useDesktopSettings(
  backendInfo: BackendConnectionInfo,
  options: UseDesktopSettingsOptions = {},
): UseDesktopSettingsResult {
  const [isOpen, setIsOpen] = useState(false)
  const [config, setConfig] = useState<DesktopRuntimeConfig | null>(null)
  const [draftState, setDraftState] = useState<DesktopSettingsDraft | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState("")
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [saveNotice, setSaveNotice] = useState("")

  const actionState = useMemo(
    () => resolveDesktopSettingsActionState({ config, backendInfo }),
    [backendInfo, config],
  )

  const setDraft = useCallback<Dispatch<SetStateAction<DesktopSettingsDraft | null>>>(
    (value) => {
      setFieldErrors({})
      setSaveError("")
      setSaveNotice("")
      setDraftState((current) =>
        typeof value === "function"
          ? (value as (draft: DesktopSettingsDraft | null) => DesktopSettingsDraft | null)(current)
          : value,
      )
    },
    [],
  )

  const secretDrafts = useMemo(() => extractDesktopSecretDrafts(draftState), [draftState])

  const setSecretDrafts = useCallback<Dispatch<SetStateAction<DesktopSecretDrafts | null>>>(
    (value) => {
      setFieldErrors({})
      setSaveError("")
      setSaveNotice("")
      setDraftState((current) => {
        if (!current) {
          return current
        }
        const nextValue =
          typeof value === "function"
            ? (value as (drafts: DesktopSecretDrafts | null) => DesktopSecretDrafts | null)(
                extractDesktopSecretDrafts(current),
              )
            : value
        if (!nextValue) {
          return current
        }
        return mergeDesktopSecretDrafts(current, nextValue)
      })
    },
    [],
  )

  const loadSettings = useCallback(async () => {
    setLoading(true)
    setSaveError("")
    setFieldErrors({})
    try {
      const nextConfig = await fetchRuntimeConfig()
      setConfig(nextConfig)
      setDraftState(createDesktopSettingsDraft(nextConfig))
      setSaveNotice("")
    } catch (error) {
      setSaveError(resolveErrorMessage(error, "加载配置失败"))
    } finally {
      setLoading(false)
    }
  }, [])

  const openSettings = useCallback(async () => {
    setIsOpen(true)
    if (config || loading) {
      return
    }
    await loadSettings()
  }, [config, loadSettings, loading])

  const closeSettings = useCallback(() => {
    setIsOpen(false)
  }, [])

  const reloadSettings = useCallback(async () => {
    await loadSettings()
  }, [loadSettings])

  const saveSettings = useCallback(
    async (intent: DesktopSettingsSaveIntent = "save") => {
      if (!draftState) {
        return false
      }
      setSaving(true)
      setSaveError("")
      setFieldErrors({})
      setSaveNotice("")
      try {
        const result = await persistDesktopSettings({
          draft: draftState,
          actionState,
          intent,
          deps: {
            saveConfig: saveRuntimeConfig,
            applyManagedRestart: restartManagedBackend,
            onApplied: options.onApply,
          },
        })
        setConfig(result.config)
        setDraftState(createDesktopSettingsDraft(result.config))
        if (result.outcome === "saved_apply_failed") {
          setSaveError(`配置已保存，但应用失败：${result.errorMessage}`)
          return false
        }
        setSaveNotice(result.notice)
        return true
      } catch (error) {
        if (error instanceof ConfigSaveError) {
          setFieldErrors(error.fieldErrors)
          setSaveError(error.message)
        } else {
          setSaveError(resolveErrorMessage(error, "保存配置失败"))
        }
        return false
      } finally {
        setSaving(false)
      }
    },
    [actionState, draftState, options.onApply],
  )

  const applyMode: DesktopSettingsApplyMode =
    actionState.mode === "save_and_apply" ? "managed" : "save_only"

  return {
    isOpen,
    openSettings,
    closeSettings,
    reloadSettings,
    reload: reloadSettings,
    loading,
    saving,
    draft: draftState,
    secretDrafts,
    fieldErrors,
    saveError,
    errorMessage: saveError,
    saveNotice,
    saveMessage: saveNotice,
    isDirty: isDesktopSettingsDirty(config, draftState),
    actionState,
    applyMode,
    setDraft,
    setSecretDrafts,
    saveSettings,
    save: () => saveSettings("save"),
    updateTranslateField(key, value) {
      setDraft((current) =>
        current
          ? {
              ...current,
              translate: {
                ...current.translate,
                [key]: value,
              },
            }
          : current,
      )
    },
    updateDisplayField(key, value) {
      setDraft((current) =>
        current
          ? {
              ...current,
              display: {
                ...current.display,
                [key]: value,
              },
            }
          : current,
      )
    },
    updateTtsProvider(provider) {
      setDraft((current) =>
        current
          ? {
              ...current,
              tts: {
                ...current.tts,
                provider,
              },
            }
          : current,
      )
    },
    updateDoubaoField(key, value) {
      setDraft((current) =>
        current
          ? {
              ...current,
              tts: {
                ...current.tts,
                providers: {
                  ...current.tts.providers,
                  doubao: {
                    ...current.tts.providers.doubao,
                    [key]: value,
                  },
                },
              },
            }
          : current,
      )
    },
    updateTencentField(key, value) {
      setDraft((current) =>
        current
          ? {
              ...current,
              tts: {
                ...current.tts,
                providers: {
                  ...current.tts.providers,
                  tencent_cloud: {
                    ...current.tts.providers.tencent_cloud,
                    [key]: value,
                  },
                },
              },
            }
          : current,
      )
    },
    updateTranslateSecret(provider, value) {
      setSecretDrafts((current) =>
        current
          ? {
              ...current,
              translate: {
                ...current.translate,
                [provider]:
                  provider === "deeplx"
                    ? {
                        ...current.translate.deeplx,
                        deeplx_url: value,
                      }
                    : {
                        ...current.translate.openai_compatible,
                        api_key: value,
                      },
              },
            }
          : current,
      )
    },
    updateDoubaoSecret(key, value) {
      setSecretDrafts((current) =>
        current
          ? {
              ...current,
              tts: {
                ...current.tts,
                doubao: {
                  ...current.tts.doubao,
                  [key]: value,
                },
              },
            }
          : current,
      )
    },
    updateTencentSecret(key, value) {
      setSecretDrafts((current) =>
        current
          ? {
              ...current,
              tts: {
                ...current.tts,
                tencent_cloud: {
                  ...current.tts.tencent_cloud,
                  [key]: value,
                },
              },
            }
          : current,
      )
    },
  }
}
