import { resolveConnectionBannerState } from "@/components/shell/shell-view-model"
import type { StatusBadgeTone } from "@/components/ui/status-badge"
import { StatusBadge } from "@/components/ui/status-badge"
import type { ShellConnectionState } from "@/lib/shell-types"

type ShellConnectionBannerProps = {
  connectionState: ShellConnectionState
  lastError: string
}

const toneClassName: Partial<Record<StatusBadgeTone, string>> = {
  neutral: "border-border-subtle bg-surface-panel-strong/95",
  info: "border-state-info/20 bg-state-info-soft/75",
  warning: "border-state-warning/20 bg-state-warning-soft/80",
  danger: "border-state-danger/20 bg-state-danger-soft/80",
}

export function ShellConnectionBanner({
  connectionState,
  lastError,
}: ShellConnectionBannerProps) {
  const bannerState = resolveConnectionBannerState(connectionState, lastError)

  if (!bannerState) {
    return null
  }

  const className = toneClassName[bannerState.tone] ?? toneClassName.info

  return (
    <section className={`rounded-[1rem] border px-3 py-2.5 ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            连接状态
          </p>
          <h2 className="text-[13px] font-semibold text-text-primary">{bannerState.title}</h2>
          <p className="text-[12px] leading-5 text-text-secondary">{bannerState.detail}</p>
        </div>
        <StatusBadge tone={bannerState.tone}>{bannerState.label}</StatusBadge>
      </div>
    </section>
  )
}
