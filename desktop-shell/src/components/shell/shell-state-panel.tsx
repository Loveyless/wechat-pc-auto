import type { PropsWithChildren } from "react"

import type { StatusBadgeTone } from "@/components/ui/status-badge"
import { StatusBadge } from "@/components/ui/status-badge"
import { cn } from "@/lib/utils"

type ShellStatePanelProps = PropsWithChildren<{
  eyebrow: string
  title: string
  detail?: string
  badge?: {
    label: string
    tone: StatusBadgeTone
  }
  className?: string
}>

export function ShellStatePanel({
  eyebrow,
  title,
  detail,
  badge,
  className,
  children,
}: ShellStatePanelProps) {
  return (
    <section
      className={cn(
        "rounded-[1.75rem] border border-border-subtle bg-surface-panel-strong/95 p-5 shadow-[0_18px_48px_rgba(29,38,50,0.08)]",
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            {eyebrow}
          </p>
          <h2 className="text-xl font-semibold tracking-[-0.03em] text-text-primary">
            {title}
          </h2>
          {detail ? <p className="max-w-2xl text-sm leading-6 text-text-secondary">{detail}</p> : null}
        </div>
        {badge ? <StatusBadge tone={badge.tone}>{badge.label}</StatusBadge> : null}
      </div>
      {children ? <div className="mt-4">{children}</div> : null}
    </section>
  )
}
