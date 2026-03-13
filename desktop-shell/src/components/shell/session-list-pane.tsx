import { StatusBadge } from "@/components/ui/status-badge"
import {
  resolveSessionFidelityBadge,
  resolveSessionKindBadge,
  resolveUnreadTone,
} from "@/components/shell/shell-view-model"
import type { ShellSession } from "@/lib/shell-types"

type SessionListPaneProps = {
  sessions: ShellSession[]
  selectedSessionId: string
  onSelect: (sessionId: string) => void
}

export function SessionListPane({
  sessions,
  selectedSessionId,
  onSelect,
}: SessionListPaneProps) {
  return (
    <aside className="flex h-full flex-col rounded-[1.75rem] border border-border-subtle bg-surface-panel/95 p-4 shadow-[0_18px_48px_rgba(29,38,50,0.08)]">
      <div className="mb-4 space-y-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          Session Navigation
        </p>
        <p className="text-sm text-text-secondary">
          先走 <code>/api/sessions</code> 引导，再订阅
          <code className="ml-1">session.list.updated</code>。
        </p>
      </div>

      <div className="space-y-2">
        {sessions.map((session) => {
          const selected = session.id === selectedSessionId
          const kindBadge = resolveSessionKindBadge(session.kind)
          const fidelityBadge = resolveSessionFidelityBadge(session)

          return (
            <button
              key={session.id}
              className={[
                "w-full rounded-[1.35rem] border px-4 py-3 text-left transition",
                selected
                  ? "border-state-progress/20 bg-surface-selected shadow-sm"
                  : "border-border-subtle bg-surface-panel-strong hover:border-border-strong hover:bg-workspace-canvas-strong/75",
              ].join(" ")}
              onClick={() => onSelect(session.id)}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate font-medium text-text-primary">{session.name}</span>
                    <StatusBadge tone={kindBadge.tone}>{kindBadge.label}</StatusBadge>
                    {fidelityBadge ? (
                      <StatusBadge tone={fidelityBadge.tone}>
                        {fidelityBadge.label}
                      </StatusBadge>
                    ) : null}
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-text-secondary">
                    {session.preview}
                  </p>
                </div>
                <StatusBadge tone={resolveUnreadTone(session.unread)}>
                  {session.unread}
                </StatusBadge>
              </div>
            </button>
          )
        })}
      </div>
    </aside>
  )
}
