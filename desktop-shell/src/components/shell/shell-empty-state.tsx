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
    <div className="grid min-h-[200px] place-items-center rounded-[1.15rem] border border-dashed border-border-strong bg-workspace-canvas-strong/75 p-5 text-center">
      <div className="max-w-md space-y-2.5">
        <div className="mx-auto grid h-10 w-10 place-items-center rounded-[0.85rem] bg-surface-panel text-base text-text-secondary">
          {icon ?? "·"}
        </div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          {eyebrow}
        </p>
        <h3 className="text-xl font-semibold tracking-[-0.03em] text-text-primary">
          {title}
        </h3>
        <p className="text-[13px] leading-6 text-text-secondary">{detail}</p>
      </div>
    </div>
  )
}
