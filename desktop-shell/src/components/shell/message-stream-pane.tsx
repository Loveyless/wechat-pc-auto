import { StatusBadge } from "@/components/ui/status-badge"
import { resolveMessagePresentation } from "@/components/shell/shell-view-model"
import type { ShellMessage, ShellSession } from "@/lib/shell-types"

type MessageStreamPaneProps = {
  sessions: ShellSession[]
  selectedSessionId: string
  selectedMessages: ShellMessage[]
}

export function MessageStreamPane({
  sessions,
  selectedSessionId,
  selectedMessages,
}: MessageStreamPaneProps) {
  const selectedSession = sessions.find((session) => session.id === selectedSessionId)

  return (
    <section className="flex h-full flex-col rounded-[1.75rem] border border-border-subtle bg-surface-panel/95 p-5 shadow-[0_18px_48px_rgba(29,38,50,0.08)]">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-border-subtle pb-4">
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            Message Reading
          </p>
          <h2 className="text-3xl font-semibold tracking-[-0.04em] text-text-primary">
            {selectedSession?.name ?? "未选择会话"}
          </h2>
          <p className="text-sm text-text-secondary">
            按会话分组，点左侧切换消息流并同步 active session。
          </p>
        </div>
      </div>

      <div className="grid gap-4">
        {selectedMessages.map((message) => {
          const presentation = resolveMessagePresentation(message)

          return (
            <article
              key={message.id}
              className="rounded-[1.45rem] border border-border-subtle bg-surface-panel-strong/95 p-4"
            >
              <div className="mb-3 flex items-center justify-between gap-4">
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

              <p className="text-lg font-semibold leading-8 text-text-primary">
                {presentation.primaryText}
              </p>
              <p className="mt-3 text-sm leading-6 text-text-secondary">
                原始预览：{message.original}
              </p>
            </article>
          )
        })}
      </div>
    </section>
  )
}
