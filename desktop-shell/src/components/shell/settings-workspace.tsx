import type { ReactNode } from "react"

import { ShellEmptyState } from "@/components/shell/shell-empty-state"
import { Button } from "@/components/ui/button"
import type { UseDesktopSettingsResult } from "@/hooks/use-desktop-settings"
import type {
  DesktopSecretInputDraft,
  DesktopSettingsDraft,
  DesktopTranslateProvider,
  DesktopTtsProvider,
} from "@/lib/settings-types"

const TRANSLATE_FAIL_OPTIONS = ["show_cn_with_reason", "show_cn", "show_reason"] as const

type SettingsWorkspaceProps = {
  settings: UseDesktopSettingsResult
}

type SectionProps = {
  title: string
  detail: string
  children: ReactNode
}

type FieldProps = {
  label: string
  description: string
  error?: string
  children: ReactNode
}

type SecretEditorProps = {
  label: string
  description: string
  draft: DesktopSecretInputDraft
  error?: string
  fixedEnvKey?: string
  allowEnv?: boolean
  onChange: (next: DesktopSecretInputDraft) => void
}

type AdvancedSectionProps = {
  summary: string
  detail: string
  children: ReactNode
}

function Section({ title, detail, children }: SectionProps) {
  return (
    <section className="rounded-[1rem] border border-border-subtle bg-surface-panel-raised/88 px-3 py-3 shadow-[0_8px_22px_rgba(29,38,50,0.04)]">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
        {title}
      </p>
      <p className="mt-1 text-[12px] leading-5 text-text-secondary">{detail}</p>
      <div className="mt-3 grid gap-3">{children}</div>
    </section>
  )
}

function Field({ label, description, error, children }: FieldProps) {
  return (
    <label className="grid gap-1.5">
      <div>
        <p className="text-[12px] font-semibold text-text-primary">{label}</p>
        <p className="text-[11px] leading-5 text-text-secondary">{description}</p>
      </div>
      {children}
      {error ? <p className="text-[11px] text-state-danger">{error}</p> : null}
    </label>
  )
}

function AdvancedSection({ summary, detail, children }: AdvancedSectionProps) {
  return (
    <details className="rounded-[0.95rem] border border-border-subtle bg-workspace-canvas-strong/70 px-3 py-3">
      <summary className="cursor-pointer list-none text-[12px] font-semibold text-text-primary">
        {summary}
      </summary>
      <p className="mt-1 text-[11px] leading-5 text-text-secondary">{detail}</p>
      <div className="mt-3 grid gap-3">{children}</div>
    </details>
  )
}

function statusLabel(draft: DesktopSecretInputDraft) {
  if (!draft.status.configured) {
    return "未配置"
  }
  if (draft.status.source === "env") {
    return draft.status.env_key ? `环境变量 ${draft.status.env_key}` : "环境变量"
  }
  if (draft.status.source === "direct") {
    return "直接值"
  }
  return "已配置"
}

function providerLabel(provider: string) {
  switch (provider) {
    case "windows_system":
      return "系统朗读"
    case "doubao":
      return "豆包 TTS"
    case "tencent_cloud":
      return "腾讯云 TTS"
    case "deeplx":
      return "DeepLX"
    case "openai_compatible":
      return "OpenAI Compatible"
    case "passthrough":
      return "原文透传"
    default:
      return provider
  }
}

export function resolveDesktopSettingsTranslateSections(provider: DesktopTranslateProvider) {
  return {
    showDeeplxFields: provider === "deeplx",
    showOpenAICompatibleFields: provider === "openai_compatible",
    showPassthroughNotice: provider === "passthrough",
  }
}

export function resolveDesktopSettingsProviderSections(provider: DesktopTtsProvider) {
  return {
    showWindowsSystemNotice: provider === "windows_system",
    showDoubaoFields: provider === "doubao",
    showTencentFields: provider === "tencent_cloud",
  }
}

function num(value: string, fallback: number) {
  if (!value.trim()) {
    return fallback
  }
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function SecretEditor({
  label,
  description,
  draft,
  error,
  fixedEnvKey,
  allowEnv = true,
  onChange,
}: SecretEditorProps) {
  const modeValue = !allowEnv && draft.mode === "env" ? "keep" : draft.mode

  return (
    <div className="rounded-[0.95rem] border border-border-subtle bg-workspace-canvas-strong/70 px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[12px] font-semibold text-text-primary">{label}</p>
          <p className="text-[11px] leading-5 text-text-secondary">{description}</p>
        </div>
        <span className="rounded-full bg-surface-panel px-2.5 py-1 text-[11px] text-text-secondary">
          {statusLabel(draft)}
        </span>
      </div>
      <div className="mt-3 grid gap-2">
        <select
          className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
          value={modeValue}
          onChange={(event) => {
            const nextMode = event.target.value as DesktopSecretInputDraft["mode"]
            onChange({
              ...draft,
              mode: nextMode,
              env_key: nextMode === "env" && fixedEnvKey ? fixedEnvKey : draft.env_key,
            })
          }}
        >
          <option value="keep">保持现状</option>
          <option value="direct">改成直接值</option>
          {allowEnv ? <option value="env">改成环境变量</option> : null}
          <option value="clear">清空配置</option>
        </select>
        {draft.mode === "direct" ? (
          <input
            className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
            placeholder="输入新的 secret，后端不会回显"
            type="password"
            value={draft.value}
            onChange={(event) => onChange({ ...draft, value: event.target.value })}
          />
        ) : null}
        {allowEnv && draft.mode === "env" && fixedEnvKey ? (
          <div className="rounded-lg border border-dashed border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-secondary">
            固定环境变量：{fixedEnvKey}
          </div>
        ) : null}
        {allowEnv && draft.mode === "env" && !fixedEnvKey ? (
          <input
            className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
            placeholder="输入环境变量名"
            value={draft.env_key}
            onChange={(event) => onChange({ ...draft, env_key: event.target.value })}
          />
        ) : null}
      </div>
      {error ? <p className="mt-2 text-[11px] text-state-danger">{error}</p> : null}
    </div>
  )
}

export function SettingsWorkspace({ settings }: SettingsWorkspaceProps) {
  const draft = settings.draft
  const updateDraft = (updater: (current: DesktopSettingsDraft) => DesktopSettingsDraft) =>
    settings.setDraft((current) => (current ? updater(current) : current))
  const updateSecretDrafts = (
    updater: (current: NonNullable<UseDesktopSettingsResult["secretDrafts"]>) => NonNullable<
      UseDesktopSettingsResult["secretDrafts"]
    >,
  ) => settings.setSecretDrafts((current) => (current ? updater(current) : current))
  const fieldError = (path: string) => settings.fieldErrors[path]

  if (settings.loading && !draft) {
    return (
      <aside className="flex h-full min-h-0 flex-col border-l border-border-subtle bg-surface-panel/92">
        <div className="flex min-h-0 flex-1 p-3">
          <ShellEmptyState
            eyebrow="Loading Settings"
            title="正在加载配置"
            detail="桌面壳正在请求 `/api/config`。拿不到 DTO 之前不允许编辑。"
            icon="◔"
          />
        </div>
      </aside>
    )
  }

  if (!draft) {
    return (
      <aside className="flex h-full min-h-0 flex-col border-l border-border-subtle bg-surface-panel/92">
        <div className="flex min-h-0 flex-1 p-3">
          <ShellEmptyState
            eyebrow="Settings Unavailable"
            title="配置还没准备好"
            detail={settings.saveError || "当前还没有可编辑配置，请先重试加载。"}
            icon="◎"
          />
        </div>
        <div className="shrink-0 border-t border-border-subtle px-3 py-3">
          <Button onClick={() => void settings.reloadSettings()} size="sm" variant="panel">
            重试加载
          </Button>
        </div>
      </aside>
    )
  }

  const ttsProvider = draft.tts.provider as DesktopTtsProvider
  const providerSections = resolveDesktopSettingsProviderSections(ttsProvider)
  const renderToggle = (
    value: boolean,
    onToggle: () => void,
    enabledLabel = "已启用",
    disabledLabel = "已关闭",
  ) => (
    <button
      className={`rounded-lg border px-3 py-2 text-left text-sm ${
        value
          ? "border-state-ready bg-state-ready-soft text-state-ready"
          : "border-border-strong bg-surface-panel text-text-secondary"
      }`}
      type="button"
      onClick={onToggle}
    >
      {value ? enabledLabel : disabledLabel}
    </button>
  )

  return (
    <aside className="flex h-full min-h-0 flex-col border-l border-border-subtle bg-surface-panel/92">
      <div className="shrink-0 border-b border-border-subtle px-3 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              设置工作区
            </p>
            <h2 className="mt-1 text-lg font-semibold tracking-[-0.02em] text-text-primary">
              持久化配置
            </h2>
            <p className="mt-1 text-[12px] leading-5 text-text-secondary">
              写入目标：{draft.runtime.config_path || "未返回 config_path"}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button onClick={() => void settings.reloadSettings()} size="sm" variant="outline">
              刷新
            </Button>
            <Button onClick={settings.closeSettings} size="sm" variant="quiet">
              关闭
            </Button>
          </div>
        </div>
      </div>

      <div className="shell-scrollbar min-h-0 flex-1 overflow-y-auto px-3 py-3">
        <div className="flex flex-col gap-3">
          <Section
            title="Translate"
            detail="翻译是持久化默认值。只渲染当前 provider 的字段，secret 仍然是 write-only。"
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="翻译开关" description="控制启动默认值" error={fieldError("translate.enabled")}>
                {renderToggle(draft.translate.enabled, () =>
                  updateDraft((current) => ({
                    ...current,
                    translate: { ...current.translate, enabled: !current.translate.enabled },
                  })),
                )}
              </Field>
              <Field label="Provider" description="只改持久化默认值" error={fieldError("translate.provider")}>
                <select
                  className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                  value={draft.translate.provider}
                  onChange={(event) =>
                    updateDraft((current) => ({
                      ...current,
                      translate: {
                        ...current.translate,
                        provider: event.target.value as DesktopTranslateProvider,
                      },
                    }))
                  }
                >
                  {draft.translate.available_providers.map((provider) => (
                    <option key={provider} value={provider}>
                      {providerLabel(provider)}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="Source Lang"
                description="translate.source_lang"
                error={fieldError("translate.source_lang")}
              >
                <input
                  className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                  value={draft.translate.source_lang}
                  onChange={(event) =>
                    updateDraft((current) => ({
                      ...current,
                      translate: { ...current.translate, source_lang: event.target.value },
                    }))
                  }
                />
              </Field>
              <Field
                label="Target Lang"
                description="translate.target_lang"
                error={fieldError("translate.target_lang")}
              >
                <input
                  className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                  value={draft.translate.target_lang}
                  onChange={(event) =>
                    updateDraft((current) => ({
                      ...current,
                      translate: { ...current.translate, target_lang: event.target.value },
                    }))
                  }
                />
              </Field>
            </div>

            {resolveDesktopSettingsTranslateSections(draft.translate.provider).showDeeplxFields ? (
              <>
                <Field
                  label="DeepLX Timeout"
                  description="translate.providers.deeplx.timeout_seconds"
                  error={fieldError("translate.providers.deeplx.timeout_seconds")}
                >
                  <input
                    className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                    type="number"
                    value={draft.translate.providers.deeplx.timeout_seconds}
                    onChange={(event) =>
                      updateDraft((current) => ({
                        ...current,
                        translate: {
                          ...current.translate,
                          providers: {
                            ...current.translate.providers,
                            deeplx: {
                              ...current.translate.providers.deeplx,
                              timeout_seconds: num(
                                event.target.value,
                                current.translate.providers.deeplx.timeout_seconds,
                              ),
                            },
                          },
                        },
                      }))
                    }
                  />
                </Field>
                <SecretEditor
                  label="DeepLX URL"
                  description="仅 `deeplx` 生效；env 模式固定使用 `DEEPLX_URL`，GUI 不会写 `.env.local`。"
                  draft={draft.translate.providers.deeplx.deeplx_url}
                  error={fieldError("translate.providers.deeplx.deeplx_url")}
                  fixedEnvKey="DEEPLX_URL"
                  onChange={(next) =>
                    updateSecretDrafts((current) => ({
                      ...current,
                      translate: {
                        ...current.translate,
                        deeplx: {
                          ...current.translate.deeplx,
                          deeplx_url: next,
                        },
                      },
                    }))
                  }
                />
              </>
            ) : null}

            {resolveDesktopSettingsTranslateSections(draft.translate.provider).showOpenAICompatibleFields ? (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field
                    label="Base URL"
                    description="translate.providers.openai_compatible.base_url"
                    error={fieldError("translate.providers.openai_compatible.base_url")}
                  >
                    <input
                      className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                      value={draft.translate.providers.openai_compatible.base_url}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          translate: {
                            ...current.translate,
                            providers: {
                              ...current.translate.providers,
                              openai_compatible: {
                                ...current.translate.providers.openai_compatible,
                                base_url: event.target.value,
                              },
                            },
                          },
                        }))
                      }
                    />
                  </Field>
                  <Field
                    label="Model"
                    description="translate.providers.openai_compatible.model"
                    error={fieldError("translate.providers.openai_compatible.model")}
                  >
                    <input
                      className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                      value={draft.translate.providers.openai_compatible.model}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          translate: {
                            ...current.translate,
                            providers: {
                              ...current.translate.providers,
                              openai_compatible: {
                                ...current.translate.providers.openai_compatible,
                                model: event.target.value,
                              },
                            },
                          },
                        }))
                      }
                    />
                  </Field>
                </div>
                <Field
                  label="Request Timeout"
                  description="translate.providers.openai_compatible.timeout_seconds"
                  error={fieldError("translate.providers.openai_compatible.timeout_seconds")}
                >
                  <input
                    className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                    type="number"
                    value={draft.translate.providers.openai_compatible.timeout_seconds}
                    onChange={(event) =>
                      updateDraft((current) => ({
                        ...current,
                        translate: {
                          ...current.translate,
                          providers: {
                            ...current.translate.providers,
                            openai_compatible: {
                              ...current.translate.providers.openai_compatible,
                              timeout_seconds: num(
                                event.target.value,
                                current.translate.providers.openai_compatible.timeout_seconds,
                              ),
                            },
                          },
                        },
                      }))
                    }
                  />
                </Field>
                <SecretEditor
                  label="API Key"
                  description="只允许直接值或清空；后端不会回显，也不支持 env 模式。"
                  draft={draft.translate.providers.openai_compatible.api_key}
                  error={fieldError("translate.providers.openai_compatible.api_key")}
                  allowEnv={false}
                  onChange={(next) =>
                    updateSecretDrafts((current) => ({
                      ...current,
                      translate: {
                        ...current.translate,
                        openai_compatible: {
                          ...current.translate.openai_compatible,
                          api_key: next,
                        },
                      },
                    }))
                  }
                />
              </>
            ) : null}

            {resolveDesktopSettingsTranslateSections(draft.translate.provider).showPassthroughNotice ? (
              <div className="rounded-[0.95rem] border border-dashed border-border-strong bg-workspace-canvas-strong/75 px-3 py-3 text-[12px] leading-6 text-text-secondary">
                `passthrough` 只保留语言方向，不请求外部翻译 provider，也没有 secret 表单。
              </div>
            ) : null}
          </Section>

          <Section
            title="Display"
            detail="这里是下次启动默认值。顶部 runtime quick toggle 仍然只影响当前运行态。"
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="English Only" description="只展示英文输出" error={fieldError("display.english_only")}>
                {renderToggle(draft.display.english_only, () =>
                  updateDraft((current) => ({
                    ...current,
                    display: { ...current.display, english_only: !current.display.english_only },
                  })),
                )}
              </Field>
              <Field label="默认自动朗读" description="持久化默认值，不是顶部 runtime toggle" error={fieldError("display.tts_auto_read_active_chat")}>
                {renderToggle(
                  draft.display.tts_auto_read_active_chat,
                  () =>
                    updateDraft((current) => ({
                      ...current,
                      display: {
                        ...current.display,
                        tts_auto_read_active_chat: !current.display.tts_auto_read_active_chat,
                      },
                    })),
                  "默认开启",
                  "默认关闭",
                )}
              </Field>
            </div>
            <Field label="翻译失败展示策略" description="直接对应 display.on_translate_fail" error={fieldError("display.on_translate_fail")}>
              <select
                className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                value={draft.display.on_translate_fail}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    display: {
                      ...current.display,
                      on_translate_fail:
                        event.target.value as DesktopSettingsDraft["display"]["on_translate_fail"],
                    },
                  }))
                }
              >
                {TRANSLATE_FAIL_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>
          </Section>

          <Section
            title="TTS"
            detail="首屏只保留 provider、config_path、endpoint、凭据和关键标识字段；次级调参折叠到高级区。"
          >
            <Field label="TTS Provider" description="切换默认 provider" error={fieldError("tts.provider")}>
              <select
                className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                value={draft.tts.provider}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    tts: { ...current.tts, provider: event.target.value as DesktopTtsProvider },
                  }))
                }
              >
                {draft.tts.available_providers.map((provider) => (
                  <option key={provider} value={provider}>
                    {providerLabel(provider)}
                  </option>
                ))}
              </select>
            </Field>

            {providerSections.showWindowsSystemNotice ? (
              <div className="rounded-[0.95rem] border border-dashed border-border-strong bg-workspace-canvas-strong/75 px-3 py-3 text-[12px] leading-6 text-text-secondary">
                `windows_system` 没有 provider-private 表单，当前只保留 provider 选择本身。
              </div>
            ) : null}

            {providerSections.showDoubaoFields ? (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field
                    label="Config Path"
                    description="tts.providers.doubao.config_path"
                    error={fieldError("tts.providers.doubao.config_path")}
                  >
                    <input
                      className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                      value={draft.tts.providers.doubao.config_path}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          tts: {
                            ...current.tts,
                            providers: {
                              ...current.tts.providers,
                              doubao: {
                                ...current.tts.providers.doubao,
                                config_path: event.target.value,
                              },
                            },
                          },
                        }))
                      }
                    />
                  </Field>
                  <Field
                    label="Endpoint"
                    description="豆包 WebSocket endpoint"
                    error={fieldError("tts.providers.doubao.endpoint")}
                  >
                    <input
                      className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                      value={draft.tts.providers.doubao.endpoint}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          tts: {
                            ...current.tts,
                            providers: {
                              ...current.tts.providers,
                              doubao: {
                                ...current.tts.providers.doubao,
                                endpoint: event.target.value,
                              },
                            },
                          },
                        }))
                      }
                    />
                  </Field>
                  <Field
                    label="Resource ID"
                    description="豆包 resource_id"
                    error={fieldError("tts.providers.doubao.resource_id")}
                  >
                    <input
                      className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                      value={draft.tts.providers.doubao.resource_id}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          tts: {
                            ...current.tts,
                            providers: {
                              ...current.tts.providers,
                              doubao: {
                                ...current.tts.providers.doubao,
                                resource_id: event.target.value,
                              },
                            },
                          },
                        }))
                      }
                    />
                  </Field>
                  <Field
                    label="Speaker"
                    description="豆包 speaker"
                    error={fieldError("tts.providers.doubao.speaker")}
                  >
                    <input
                      className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                      value={draft.tts.providers.doubao.speaker}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          tts: {
                            ...current.tts,
                            providers: {
                              ...current.tts.providers,
                              doubao: {
                                ...current.tts.providers.doubao,
                                speaker: event.target.value,
                              },
                            },
                          },
                        }))
                      }
                    />
                  </Field>
                </div>
                <SecretEditor
                  label="豆包 App ID"
                  description="支持直接值或 env_key。"
                  draft={draft.tts.providers.doubao.appid}
                  error={fieldError("tts.providers.doubao.appid")}
                  onChange={(next) =>
                    updateSecretDrafts((current) => ({
                      ...current,
                      tts: {
                        ...current.tts,
                        doubao: {
                          ...current.tts.doubao,
                          appid: next,
                        },
                      },
                    }))
                  }
                />
                <SecretEditor
                  label="豆包 Access Token"
                  description="支持直接值或 env_key。"
                  draft={draft.tts.providers.doubao.access_token}
                  error={fieldError("tts.providers.doubao.access_token")}
                  onChange={(next) =>
                    updateSecretDrafts((current) => ({
                      ...current,
                      tts: {
                        ...current.tts,
                        doubao: {
                          ...current.tts.doubao,
                          access_token: next,
                        },
                      },
                    }))
                  }
                />
                <AdvancedSection
                  summary="高级参数"
                  detail="次级音频调参保留在折叠区，避免把首屏变成 provider 私有参数垃圾堆。"
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field
                      label="Audio Format"
                      description="当前只支持 wav"
                      error={fieldError("tts.providers.doubao.audio_format")}
                    >
                      <select
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        value={draft.tts.providers.doubao.audio_format}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                doubao: {
                                  ...current.tts.providers.doubao,
                                  audio_format: event.target.value,
                                },
                              },
                            },
                          }))
                        }
                      >
                        <option value="wav">wav</option>
                      </select>
                    </Field>
                    <Field
                      label="Sample Rate"
                      description="允许值集合"
                      error={fieldError("tts.providers.doubao.sample_rate")}
                    >
                      <select
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        value={draft.tts.providers.doubao.sample_rate}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                doubao: {
                                  ...current.tts.providers.doubao,
                                  sample_rate: num(
                                    event.target.value,
                                    current.tts.providers.doubao.sample_rate,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      >
                        {[8000, 16000, 22050, 24000, 32000, 44100, 48000].map((rate) => (
                          <option key={rate} value={rate}>
                            {rate}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field
                      label="Speech Rate"
                      description="范围 -50 到 100"
                      error={fieldError("tts.providers.doubao.speech_rate")}
                    >
                      <input
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        type="number"
                        value={draft.tts.providers.doubao.speech_rate}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                doubao: {
                                  ...current.tts.providers.doubao,
                                  speech_rate: num(
                                    event.target.value,
                                    current.tts.providers.doubao.speech_rate,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                    <Field
                      label="Loudness Rate"
                      description="范围 -50 到 100"
                      error={fieldError("tts.providers.doubao.loudness_rate")}
                    >
                      <input
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        type="number"
                        value={draft.tts.providers.doubao.loudness_rate}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                doubao: {
                                  ...current.tts.providers.doubao,
                                  loudness_rate: num(
                                    event.target.value,
                                    current.tts.providers.doubao.loudness_rate,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                    <Field
                      label="UID"
                      description="客户端 uid"
                      error={fieldError("tts.providers.doubao.uid")}
                    >
                      <input
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        value={draft.tts.providers.doubao.uid}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                doubao: {
                                  ...current.tts.providers.doubao,
                                  uid: event.target.value,
                                },
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                    <Field
                      label="Connect Timeout"
                      description="单位秒"
                      error={fieldError("tts.providers.doubao.connect_timeout_seconds")}
                    >
                      <input
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        type="number"
                        value={draft.tts.providers.doubao.connect_timeout_seconds}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                doubao: {
                                  ...current.tts.providers.doubao,
                                  connect_timeout_seconds: num(
                                    event.target.value,
                                    current.tts.providers.doubao.connect_timeout_seconds,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                    <Field
                      label="Use Cache"
                      description="provider 私有缓存开关"
                      error={fieldError("tts.providers.doubao.use_cache")}
                    >
                      {renderToggle(
                        draft.tts.providers.doubao.use_cache,
                        () =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                doubao: {
                                  ...current.tts.providers.doubao,
                                  use_cache: !current.tts.providers.doubao.use_cache,
                                },
                              },
                            },
                          })),
                      )}
                    </Field>
                  </div>
                </AdvancedSection>
              </>
            ) : null}

            {providerSections.showTencentFields ? (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field
                    label="Config Path"
                    description="tts.providers.tencent_cloud.config_path"
                    error={fieldError("tts.providers.tencent_cloud.config_path")}
                  >
                    <input
                      className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                      value={draft.tts.providers.tencent_cloud.config_path}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          tts: {
                            ...current.tts,
                            providers: {
                              ...current.tts.providers,
                              tencent_cloud: {
                                ...current.tts.providers.tencent_cloud,
                                config_path: event.target.value,
                              },
                            },
                          },
                        }))
                      }
                    />
                  </Field>
                  <Field
                    label="Endpoint"
                    description="腾讯云 API endpoint"
                    error={fieldError("tts.providers.tencent_cloud.endpoint")}
                  >
                    <input
                      className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                      value={draft.tts.providers.tencent_cloud.endpoint}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          tts: {
                            ...current.tts,
                            providers: {
                              ...current.tts.providers,
                              tencent_cloud: {
                                ...current.tts.providers.tencent_cloud,
                                endpoint: event.target.value,
                              },
                            },
                          },
                        }))
                      }
                    />
                  </Field>
                  <Field
                    label="Region"
                    description="可为空"
                    error={fieldError("tts.providers.tencent_cloud.region")}
                  >
                    <input
                      className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                      value={draft.tts.providers.tencent_cloud.region}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          tts: {
                            ...current.tts,
                            providers: {
                              ...current.tts.providers,
                              tencent_cloud: {
                                ...current.tts.providers.tencent_cloud,
                                region: event.target.value,
                              },
                            },
                          },
                        }))
                      }
                    />
                  </Field>
                  <Field
                    label="Voice Type"
                    description="腾讯云 voice_type"
                    error={fieldError("tts.providers.tencent_cloud.voice_type")}
                  >
                    <input
                      className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                      type="number"
                      value={draft.tts.providers.tencent_cloud.voice_type}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          tts: {
                            ...current.tts,
                            providers: {
                              ...current.tts.providers,
                              tencent_cloud: {
                                ...current.tts.providers.tencent_cloud,
                                voice_type: num(
                                  event.target.value,
                                  current.tts.providers.tencent_cloud.voice_type,
                                ),
                              },
                            },
                          },
                        }))
                      }
                    />
                  </Field>
                </div>
                <SecretEditor
                  label="Tencent Secret ID"
                  description="支持直接值或 env_key。"
                  draft={draft.tts.providers.tencent_cloud.secret_id}
                  error={fieldError("tts.providers.tencent_cloud.secret_id")}
                  onChange={(next) =>
                    updateSecretDrafts((current) => ({
                      ...current,
                      tts: {
                        ...current.tts,
                        tencent_cloud: {
                          ...current.tts.tencent_cloud,
                          secret_id: next,
                        },
                      },
                    }))
                  }
                />
                <SecretEditor
                  label="Tencent Secret Key"
                  description="支持直接值或 env_key。"
                  draft={draft.tts.providers.tencent_cloud.secret_key}
                  error={fieldError("tts.providers.tencent_cloud.secret_key")}
                  onChange={(next) =>
                    updateSecretDrafts((current) => ({
                      ...current,
                      tts: {
                        ...current.tts,
                        tencent_cloud: {
                          ...current.tts.tencent_cloud,
                          secret_key: next,
                        },
                      },
                    }))
                  }
                />
                <AdvancedSection
                  summary="高级参数"
                  detail="采样、情绪和超时仍可调，但不该堆在首屏污染主路径配置。"
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field
                      label="Codec"
                      description="当前只支持 wav"
                      error={fieldError("tts.providers.tencent_cloud.codec")}
                    >
                      <select
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        value={draft.tts.providers.tencent_cloud.codec}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  codec: event.target.value,
                                },
                              },
                            },
                          }))
                        }
                      >
                        <option value="wav">wav</option>
                      </select>
                    </Field>
                    <Field
                      label="Sample Rate"
                      description="允许值集合"
                      error={fieldError("tts.providers.tencent_cloud.sample_rate")}
                    >
                      <select
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        value={draft.tts.providers.tencent_cloud.sample_rate}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  sample_rate: num(
                                    event.target.value,
                                    current.tts.providers.tencent_cloud.sample_rate,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      >
                        {[8000, 16000, 24000].map((rate) => (
                          <option key={rate} value={rate}>
                            {rate}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field
                      label="Speed"
                      description="范围 -2 到 6"
                      error={fieldError("tts.providers.tencent_cloud.speed")}
                    >
                      <input
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        type="number"
                        value={draft.tts.providers.tencent_cloud.speed}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  speed: num(
                                    event.target.value,
                                    current.tts.providers.tencent_cloud.speed,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                    <Field
                      label="Volume"
                      description="范围 -10 到 10"
                      error={fieldError("tts.providers.tencent_cloud.volume")}
                    >
                      <input
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        type="number"
                        value={draft.tts.providers.tencent_cloud.volume}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  volume: num(
                                    event.target.value,
                                    current.tts.providers.tencent_cloud.volume,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                    <Field
                      label="Primary Language"
                      description="腾讯云 primary_language"
                      error={fieldError("tts.providers.tencent_cloud.primary_language")}
                    >
                      <select
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        value={draft.tts.providers.tencent_cloud.primary_language}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  primary_language: num(
                                    event.target.value,
                                    current.tts.providers.tencent_cloud.primary_language,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      >
                        {[1, 2].map((value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field
                      label="Model Type"
                      description="当前只支持 1"
                      error={fieldError("tts.providers.tencent_cloud.model_type")}
                    >
                      <select
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        value={draft.tts.providers.tencent_cloud.model_type}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  model_type: num(
                                    event.target.value,
                                    current.tts.providers.tencent_cloud.model_type,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      >
                        <option value={1}>1</option>
                      </select>
                    </Field>
                    <Field
                      label="Project ID"
                      description="腾讯云 project_id"
                      error={fieldError("tts.providers.tencent_cloud.project_id")}
                    >
                      <input
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        type="number"
                        value={draft.tts.providers.tencent_cloud.project_id}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  project_id: num(
                                    event.target.value,
                                    current.tts.providers.tencent_cloud.project_id,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                    <Field
                      label="Segment Rate"
                      description="腾讯云 segment_rate"
                      error={fieldError("tts.providers.tencent_cloud.segment_rate")}
                    >
                      <select
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        value={draft.tts.providers.tencent_cloud.segment_rate}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  segment_rate: num(
                                    event.target.value,
                                    current.tts.providers.tencent_cloud.segment_rate,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      >
                        {[0, 1, 2].map((value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field
                      label="Emotion Category"
                      description="留空则不校验 intensity"
                      error={fieldError("tts.providers.tencent_cloud.emotion_category")}
                    >
                      <input
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        value={draft.tts.providers.tencent_cloud.emotion_category}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  emotion_category: event.target.value,
                                },
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                    <Field
                      label="Emotion Intensity"
                      description="emotion_category 非空时范围 50 到 200"
                      error={fieldError("tts.providers.tencent_cloud.emotion_intensity")}
                    >
                      <input
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        type="number"
                        value={draft.tts.providers.tencent_cloud.emotion_intensity}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  emotion_intensity: num(
                                    event.target.value,
                                    current.tts.providers.tencent_cloud.emotion_intensity,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                    <Field
                      label="Request Timeout"
                      description="单位秒"
                      error={fieldError("tts.providers.tencent_cloud.request_timeout_seconds")}
                    >
                      <input
                        className="rounded-lg border border-border-strong bg-surface-panel px-3 py-2 text-sm text-text-primary outline-none focus:border-state-progress"
                        type="number"
                        value={draft.tts.providers.tencent_cloud.request_timeout_seconds}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  request_timeout_seconds: num(
                                    event.target.value,
                                    current.tts.providers.tencent_cloud.request_timeout_seconds,
                                  ),
                                },
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                    <Field
                      label="Enable Subtitle"
                      description="provider 私有字幕开关"
                      error={fieldError("tts.providers.tencent_cloud.enable_subtitle")}
                    >
                      {renderToggle(
                        draft.tts.providers.tencent_cloud.enable_subtitle,
                        () =>
                          updateDraft((current) => ({
                            ...current,
                            tts: {
                              ...current.tts,
                              providers: {
                                ...current.tts.providers,
                                tencent_cloud: {
                                  ...current.tts.providers.tencent_cloud,
                                  enable_subtitle:
                                    !current.tts.providers.tencent_cloud.enable_subtitle,
                                },
                              },
                            },
                          })),
                      )}
                    </Field>
                  </div>
                </AdvancedSection>
              </>
            ) : null}
          </Section>
        </div>
      </div>

      <div className="shrink-0 border-t border-border-subtle px-3 py-3">
        <div className="rounded-[0.95rem] border border-border-subtle bg-workspace-canvas-strong/80 px-3 py-3">
          <p className="text-[12px] font-semibold text-text-primary">{settings.actionState.title}</p>
          <p className="mt-1 text-[11px] leading-5 text-text-secondary">{settings.actionState.detail}</p>
        </div>
        {settings.saveNotice ? <div className="mt-3 rounded-[0.95rem] border border-state-ready/25 bg-state-ready-soft px-3 py-2 text-[11px] leading-5 text-state-ready">{settings.saveNotice}</div> : null}
        {settings.saveError ? <div className="mt-3 rounded-[0.95rem] border border-state-danger/25 bg-state-danger-soft px-3 py-2 text-[11px] leading-5 text-state-danger">{settings.saveError}</div> : null}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button disabled={!settings.isDirty || settings.loading || settings.saving} onClick={() => void settings.saveSettings("save")} size="sm">
            {settings.saving ? "保存中..." : settings.actionState.saveLabel}
          </Button>
          {settings.actionState.mode === "save_and_apply" ? (
            <Button disabled={!settings.isDirty || settings.loading || settings.saving} onClick={() => void settings.saveSettings("apply")} size="sm" variant="panel">
              {settings.actionState.applyLabel}
            </Button>
          ) : (
            <span className="text-[11px] leading-5 text-text-secondary">{settings.actionState.applyLabel}</span>
          )}
        </div>
      </div>
    </aside>
  )
}
