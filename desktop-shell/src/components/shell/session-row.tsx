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
  return (
    <button
      className={[
        "w-full rounded-[0.9rem] border border-transparent px-2.5 py-2.5 text-left transition-colors",
        selected
          ? "bg-surface-selected/90"
          : "bg-transparent hover:bg-workspace-canvas-strong/72",
      ].join(" ")}
      onClick={() => onSelect(session.id)}
      type="button"
    >
      <div className="flex items-start gap-2.5">
        <div
          className={[
            "grid h-9 w-9 shrink-0 place-items-center rounded-[0.8rem] text-[13px] font-semibold",
            selected
              ? "bg-state-progress text-text-inverse"
              : "bg-surface-panel-muted text-text-primary",
          ].join(" ")}
        >
          {resolveSessionMonogram(session)}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <span className="block truncate text-[13px] font-semibold text-text-primary">
                {session.name}
              </span>
            </div>

            <span className="shrink-0 pt-0.5 text-[11px] text-text-muted">{session.updatedAt}</span>
          </div>

          <p className="mt-0.5 truncate text-[12px] leading-5 text-text-secondary">
            {session.preview || "暂无预览"}
          </p>

          <div className="mt-1.5 flex items-center justify-end text-[10px]">
            {session.unread > 0 ? (
              <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-state-progress px-1.5 py-0.5 font-semibold text-text-inverse">
                {session.unread}
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </button>
  )
}
