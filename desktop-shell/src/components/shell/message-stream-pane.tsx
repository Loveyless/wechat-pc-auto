import { MessageCard } from "@/components/shell/message-card"
import { ShellEmptyState } from "@/components/shell/shell-empty-state"
import type { ShellDataEmptyState } from "@/components/shell/shell-view-model"
import type { ShellMessage, ShellSession } from "@/lib/shell-types"

type MessageStreamPaneProps = {
  sessions: ShellSession[]
  selectedSessionId: string
  selectedMessages: ShellMessage[]
  emptyState: ShellDataEmptyState
}

export function MessageStreamPane({
  sessions,
  selectedSessionId,
  selectedMessages,
  emptyState,
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

      {emptyState === "no-sessions" ? (
        <ShellEmptyState
          eyebrow="No Sessions"
          title="还没有会话可读"
          detail="当前消息阅读区会跟随左侧会话导航；没有会话时，不应该继续显示空壳卡片。"
          icon="◌"
        />
      ) : emptyState === "no-messages" ? (
        <ShellEmptyState
          eyebrow="No Messages"
          title={`“${selectedSession?.name ?? "当前会话"}” 暂无消息`}
          detail="会话已经选中，但当前还没有可展示的消息流；等下一次 hydrate 或事件推送即可。"
          icon="◍"
        />
      ) : (
        <div className="grid gap-4">
          {selectedMessages.map((message) => (
            <MessageCard key={message.id} message={message} />
          ))}
        </div>
      )}
    </section>
  )
}
