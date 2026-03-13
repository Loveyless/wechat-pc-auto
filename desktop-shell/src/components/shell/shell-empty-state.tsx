import type { ReactNode } from "react"

type ShellEmptyStateProps = {
  eyebrow: string
  title: string
  detail: string
  icon?: ReactNode
}

export function ShellEmptyState({
  eyebrow,
  title,
  detail,
  icon,
}: ShellEmptyStateProps) {
  return (
    <div className="grid min-h-[240px] place-items-center rounded-[1.55rem] border border-dashed border-border-strong bg-workspace-canvas-strong/75 p-6 text-center">
      <div className="max-w-md space-y-3">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-[1rem] bg-surface-panel text-lg text-text-secondary">
          {icon ?? "·"}
        </div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          {eyebrow}
        </p>
        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-text-primary">
          {title}
        </h3>
        <p className="text-sm leading-6 text-text-secondary">{detail}</p>
      </div>
    </div>
  )
}
