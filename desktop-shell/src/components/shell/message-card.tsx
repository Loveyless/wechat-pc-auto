import { StatusBadge } from "@/components/ui/status-badge"
import { resolveMessagePresentation } from "@/components/shell/shell-view-model"
import type { ShellMessage } from "@/lib/shell-types"

type MessageCardProps = {
  message: ShellMessage
  showOriginal: boolean
}

export function MessageCard({ message, showOriginal }: MessageCardProps) {
  const presentation = resolveMessagePresentation(message)
  const canShowOriginal = Boolean(
    message.original && message.original !== presentation.primaryText,
  )

  return (
    <article className="w-full max-w-[820px] rounded-[0.9rem] border border-border-subtle bg-surface-panel-strong/96 px-3 py-2.5">
      <div className="flex items-start justify-between gap-4">
        <p className="text-[12px] font-medium text-text-secondary">
          [{message.time}] {message.sender}
        </p>
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

      <p className="mt-1.5 whitespace-pre-wrap break-words text-[13px] font-medium leading-6 text-text-primary">
        {presentation.primaryText}
      </p>

      {showOriginal && canShowOriginal ? (
        <div className="mt-2 border-l-2 border-border-subtle pl-2.5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">
            原始预览
          </p>
          <p className="mt-0.5 whitespace-pre-wrap break-words text-[11px] leading-5 text-text-secondary">
            {message.original}
          </p>
        </div>
      ) : null}
    </article>
  )
}
