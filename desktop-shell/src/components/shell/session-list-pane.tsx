import { ShellEmptyState } from "@/components/shell/shell-empty-state"
import { SessionRow } from "@/components/shell/session-row"
import type { ShellSession } from "@/lib/shell-types"

type SessionListPaneProps = {
  sessions: ShellSession[]
  selectedSessionId: string
  showNoSessionsState: boolean
  onSelect: (sessionId: string) => void
}

export function SessionListPane({
  sessions,
  selectedSessionId,
  showNoSessionsState,
  onSelect,
}: SessionListPaneProps) {
  return (
    <aside className="flex h-full min-h-0 flex-col border-r border-border-subtle bg-surface-panel/78">
      <div className="shrink-0 border-b border-border-subtle px-3 py-3">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              会话导航
            </p>
            <p className="text-[12px] leading-5 text-text-secondary">
              左侧会话按最近变化阅读，点击后同步当前 active session。
            </p>
          </div>
          <div className="rounded-[0.85rem] border border-border-subtle bg-workspace-canvas-strong/85 px-2.5 py-1.5 text-right">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              会话数
            </p>
            <p className="text-sm font-semibold text-text-primary">{sessions.length}</p>
          </div>
        </div>
      </div>

      {showNoSessionsState ? (
        <div className="flex min-h-0 flex-1 p-3">
          <ShellEmptyState
            eyebrow="No Sessions"
            title="当前还没有可导航的会话"
            detail="先确认 backend 已经产出会话快照，再看 session.list.updated 是否开始推送。"
            icon="◎"
          />
        </div>
      ) : (
        <div className="shell-scrollbar min-h-0 flex-1 space-y-1 overflow-y-auto px-1.5 py-2">
          {sessions.map((session) => {
            return (
              <SessionRow
                key={session.id}
                session={session}
                selected={session.id === selectedSessionId}
                onSelect={onSelect}
              />
            )
          })}
        </div>
      )}
    </aside>
  )
}
