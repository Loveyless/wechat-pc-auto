import { ShellStatePanel } from "@/components/shell/shell-state-panel"
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

  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,0.8fr)]">
      <ShellStatePanel
        eyebrow="Runtime Overview"
        title={overviewState.title}
        detail={overviewState.detail}
        badge={{ label: overviewState.label, tone: overviewState.tone }}
        className="bg-surface-panel-raised/95"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-[1.25rem] border border-border-subtle bg-workspace-canvas-strong/75 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              监听范围
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusBadge tone={runtimeSummary.fidelityTone}>
                {runtimeState.message_fidelity}
              </StatusBadge>
              <StatusBadge tone="accent">{runtimeState.monitor_scope}</StatusBadge>
            </div>
          </div>
          <div className="rounded-[1.25rem] border border-border-subtle bg-workspace-canvas-strong/75 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              Worker
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusBadge tone={runtimeSummary.workerTone}>
                {runtimeState.worker_state}
              </StatusBadge>
              {runtimeState.worker_detail ? (
                <p className="text-sm text-text-secondary">{runtimeState.worker_detail}</p>
              ) : null}
            </div>
          </div>
          <div className="rounded-[1.25rem] border border-border-subtle bg-workspace-canvas-strong/75 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              翻译链路
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusBadge tone={translationSummary.tone}>
                {translationSummary.label}
              </StatusBadge>
            </div>
          </div>
          <div className="rounded-[1.25rem] border border-border-subtle bg-workspace-canvas-strong/75 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              朗读链路
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusBadge tone={ttsSummary.tone}>{ttsSummary.label}</StatusBadge>
            </div>
          </div>
        </div>
      </ShellStatePanel>

      <div className="grid gap-4">
        <ShellStatePanel
          eyebrow="Transport"
          title="本地接口与事件流"
          detail="桌面壳仍通过本地 HTTP bootstrap 和 WebSocket 增量同步接线。"
        >
          <dl className="grid gap-3 text-sm text-text-secondary">
            <div className="rounded-[1.1rem] border border-border-subtle bg-workspace-canvas-strong/70 p-4">
              <dt className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                HTTP
              </dt>
              <dd className="mt-2 break-all text-text-primary">{backendInfo.httpBaseUrl}</dd>
            </div>
            <div className="rounded-[1.1rem] border border-border-subtle bg-workspace-canvas-strong/70 p-4">
              <dt className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                WebSocket
              </dt>
              <dd className="mt-2 break-all text-text-primary">{backendInfo.wsUrl}</dd>
            </div>
          </dl>
        </ShellStatePanel>

        <ShellStatePanel
          eyebrow="Diagnostics"
          title="最近事件与错误"
          detail="保留 runtime 诊断，而不是把状态问题埋在角落小字里。"
        >
          <dl className="grid gap-3 text-sm text-text-secondary">
            <div className="rounded-[1.1rem] border border-border-subtle bg-workspace-canvas-strong/70 p-4">
              <dt className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                Last Event
              </dt>
              <dd className="mt-2 text-text-primary">{lastEvent || "n/a"}</dd>
            </div>
            <div className="rounded-[1.1rem] border border-border-subtle bg-workspace-canvas-strong/70 p-4">
              <dt className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                Last Error
              </dt>
              <dd className="mt-2 text-text-primary">{lastError || "n/a"}</dd>
            </div>
          </dl>
        </ShellStatePanel>
      </div>
    </section>
  )
}
