import { MessageCard } from "@/components/shell/message-card"
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
        <div className="rounded-[1rem] border border-border-subtle bg-workspace-canvas-strong/75 px-3 py-2 text-right">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            Messages
          </p>
          <p className="text-lg font-semibold text-text-primary">{selectedMessages.length}</p>
        </div>
      </div>

      <div className="grid gap-4">
        {selectedMessages.map((message) => (
          <MessageCard key={message.id} message={message} />
        ))}
      </div>
    </section>
  )
}
