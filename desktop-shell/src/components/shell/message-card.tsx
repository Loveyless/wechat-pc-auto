import { StatusBadge } from "@/components/ui/status-badge"
import { resolveMessagePresentation } from "@/components/shell/shell-view-model"
import type { ShellMessage } from "@/lib/shell-types"

type MessageCardProps = {
  message: ShellMessage
}

export function MessageCard({ message }: MessageCardProps) {
  const presentation = resolveMessagePresentation(message)

  return (
    <article className="rounded-[1.55rem] border border-border-subtle bg-surface-panel-strong/95 p-5 shadow-[0_16px_36px_rgba(29,38,50,0.06)]">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="space-y-1">
          <p className="text-sm font-medium text-text-primary">{message.sender}</p>
          <p className="text-xs text-text-muted">{message.time}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone={presentation.fidelityTone}>
            {presentation.fidelityLabel}
          </StatusBadge>
          {presentation.translationLabel && presentation.translationTone ? (
            <StatusBadge tone={presentation.translationTone}>
              {presentation.translationLabel}
            </StatusBadge>
          ) : null}
        </div>
      </div>

      <div className="rounded-[1.3rem] bg-workspace-canvas-strong/80 px-4 py-4">
        <p className="text-xl font-semibold leading-9 text-text-primary">
          {presentation.primaryText}
        </p>
      </div>

      <div className="mt-4 rounded-[1.2rem] border border-border-subtle bg-surface-panel px-4 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          Source Preview
        </p>
        <p className="mt-2 text-sm leading-6 text-text-secondary">{message.original}</p>
      </div>
    </article>
  )
}
