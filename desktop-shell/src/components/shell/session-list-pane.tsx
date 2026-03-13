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
    <aside className="flex h-full flex-col rounded-[1.75rem] border border-border-subtle bg-surface-panel/95 p-4 shadow-[0_18px_48px_rgba(29,38,50,0.08)]">
      <div className="mb-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              Session Navigation
            </p>
            <p className="text-sm text-text-secondary">
              会话导航先看最新变化，再决定读哪条消息流。
            </p>
          </div>
          <div className="rounded-[1rem] border border-border-subtle bg-workspace-canvas-strong/75 px-3 py-2 text-right">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              Sessions
            </p>
            <p className="text-lg font-semibold text-text-primary">{sessions.length}</p>
          </div>
        </div>
        <p className="text-sm text-text-secondary">
          先走 <code>/api/sessions</code> 引导，再订阅
          <code className="ml-1">session.list.updated</code>。
        </p>
      </div>

      {showNoSessionsState ? (
        <ShellEmptyState
          eyebrow="No Sessions"
          title="当前还没有可导航的会话"
          detail="先确认 backend 已经产出会话快照，再看 session.list.updated 是否开始推送。"
          icon="◎"
        />
      ) : (
        <div className="space-y-2">
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
