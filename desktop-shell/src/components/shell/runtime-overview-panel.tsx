import { StatusBadge } from "@/components/ui/status-badge"
import {
  resolveConnectionOverviewState,
  resolveRuntimeSummary,
  resolveTranslationSummary,
  resolveTtsSummary,
} from "@/components/shell/shell-view-model"
import type {
  BackendRuntimeState,
  BackendTTSState,
  BackendTranslationState,
  ShellConnectionState,
} from "@/lib/shell-types"

type RuntimeOverviewPanelProps = {
  connectionState: ShellConnectionState
  runtimeState: BackendRuntimeState
  translationState: BackendTranslationState
  ttsState: BackendTTSState
  backendInfo: {
    httpBaseUrl: string
    wsUrl: string
  }
  lastEvent: string
  lastError: string
}

export function RuntimeOverviewPanel({
  connectionState,
  runtimeState,
  translationState,
  ttsState,
  backendInfo,
  lastEvent,
  lastError,
}: RuntimeOverviewPanelProps) {
  const overviewState = resolveConnectionOverviewState(connectionState, lastError)
  const translationSummary = resolveTranslationSummary(translationState)
  const ttsSummary = resolveTtsSummary(ttsState)
  const runtimeSummary = resolveRuntimeSummary(runtimeState)
  const diagnostics = [
    lastEvent ? `事件 ${lastEvent}` : "",
    lastError ? `错误 ${lastError}` : "",
  ].filter(Boolean)

  return (
    <section className="rounded-[1.05rem] border border-border-subtle bg-surface-panel-raised/95 px-3 py-2.5 shadow-[0_10px_24px_rgba(29,38,50,0.06)]">
      <div className="flex flex-col gap-2.5 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              运行概览
            </p>
            <StatusBadge tone={overviewState.tone}>{overviewState.label}</StatusBadge>
          </div>
          <h1 className="mt-0.5 text-base font-semibold tracking-[-0.02em] text-text-primary">
            {overviewState.title}
          </h1>
          <p className="mt-0.5 text-[12px] leading-5 text-text-secondary">{overviewState.detail}</p>
        </div>

        <div className="grid gap-1.5 sm:grid-cols-2 xl:grid-cols-4">
          <div className="min-w-[132px] rounded-[0.9rem] border border-border-subtle bg-workspace-canvas-strong/80 px-2.5 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
              监听范围
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <StatusBadge tone={runtimeSummary.fidelityTone}>
                {runtimeSummary.fidelityLabel}
              </StatusBadge>
              <StatusBadge tone="accent">{runtimeSummary.scopeLabel}</StatusBadge>
            </div>
          </div>
          <div className="min-w-[132px] rounded-[0.9rem] border border-border-subtle bg-workspace-canvas-strong/80 px-2.5 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
              Worker
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <StatusBadge tone={runtimeSummary.workerTone}>
                {runtimeSummary.workerLabel}
              </StatusBadge>
              {runtimeState.worker_detail ? (
                <span className="truncate text-[12px] text-text-secondary">
                  {runtimeState.worker_detail}
                </span>
              ) : null}
            </div>
          </div>
          <div className="min-w-[132px] rounded-[0.9rem] border border-border-subtle bg-workspace-canvas-strong/80 px-2.5 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
              翻译
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <StatusBadge tone={translationSummary.tone}>{translationSummary.label}</StatusBadge>
            </div>
          </div>
          <div className="min-w-[132px] rounded-[0.9rem] border border-border-subtle bg-workspace-canvas-strong/80 px-2.5 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
              朗读
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <StatusBadge tone={ttsSummary.tone}>{ttsSummary.label}</StatusBadge>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-border-subtle/80 pt-2.5 text-[11px] text-text-secondary">
        <span className="rounded-full bg-workspace-canvas-strong/85 px-2.5 py-1">
          HTTP {backendInfo.httpBaseUrl}
        </span>
        <span className="rounded-full bg-workspace-canvas-strong/85 px-2.5 py-1">
          WS {backendInfo.wsUrl}
        </span>
        {diagnostics.map((item) => (
          <span
            key={item}
            className="rounded-full bg-workspace-canvas-strong/85 px-2.5 py-1 text-text-primary"
          >
            {item}
          </span>
        ))}
      </div>
    </section>
  )
}
