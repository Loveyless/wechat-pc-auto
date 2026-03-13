import { StatusBadge } from "@/components/ui/status-badge"
import {
  resolveSessionFidelityBadge,
  resolveSessionKindBadge,
  resolveUnreadTone,
} from "@/components/shell/shell-view-model"
import type { ShellSession } from "@/lib/shell-types"

type SessionRowProps = {
  session: ShellSession
  selected: boolean
  onSelect: (sessionId: string) => void
}

function resolveSessionMonogram(session: ShellSession) {
  return session.name.trim().slice(0, 1).toUpperCase() || "?"
}

export function SessionRow({ session, selected, onSelect }: SessionRowProps) {
  const kindBadge = resolveSessionKindBadge(session.kind)
  const fidelityBadge = resolveSessionFidelityBadge(session)

  return (
    <button
      className={[
        "w-full rounded-[1.45rem] border px-4 py-4 text-left transition",
        selected
          ? "border-state-progress/20 bg-surface-selected shadow-[0_16px_36px_rgba(37,105,199,0.14)]"
          : "border-border-subtle bg-surface-panel-strong hover:border-border-strong hover:bg-workspace-canvas-strong/80",
      ].join(" ")}
      onClick={() => onSelect(session.id)}
      type="button"
    >
      <div className="flex items-start gap-3">
        <div
          className={[
            "grid h-11 w-11 shrink-0 place-items-center rounded-[1rem] text-sm font-semibold",
            selected
              ? "bg-state-progress text-text-inverse"
              : "bg-surface-panel-muted text-text-primary",
          ].join(" ")}
        >
          {resolveSessionMonogram(session)}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate text-base font-semibold text-text-primary">
                  {session.name}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <StatusBadge tone={kindBadge.tone}>{kindBadge.label}</StatusBadge>
                {fidelityBadge ? (
                  <StatusBadge tone={fidelityBadge.tone}>
                    {fidelityBadge.label}
                  </StatusBadge>
                ) : null}
              </div>
            </div>

            <div className="flex shrink-0 flex-col items-end gap-2">
              <span className="text-xs text-text-muted">{session.updatedAt}</span>
              {session.unread > 0 ? (
                <StatusBadge tone={resolveUnreadTone(session.unread)}>
                  {session.unread}
                </StatusBadge>
              ) : null}
            </div>
          </div>

          <p className="mt-3 line-clamp-2 text-sm leading-6 text-text-secondary">
            {session.preview}
          </p>
        </div>
      </div>
    </button>
  )
}
