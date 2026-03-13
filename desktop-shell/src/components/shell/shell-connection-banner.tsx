import { ShellStatePanel } from "@/components/shell/shell-state-panel"
import { resolveConnectionBannerState } from "@/components/shell/shell-view-model"
import type { StatusBadgeTone } from "@/components/ui/status-badge"
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
    <ShellStatePanel
      eyebrow="Connection State"
      title={bannerState.title}
      detail={bannerState.detail}
      badge={{ label: bannerState.label, tone: bannerState.tone }}
      className={className}
    />
  )
}
