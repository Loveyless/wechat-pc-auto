import type { PropsWithChildren } from "react"

import { cn } from "@/lib/utils"

type StatusBadgeTone = "primary" | "neutral" | "accent"

const toneClassName: Record<StatusBadgeTone, string> = {
  primary: "border-primary/20 bg-primary/15 text-primary",
  neutral: "border-border bg-muted/60 text-muted-foreground",
  accent: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
}

type StatusBadgeProps = PropsWithChildren<{
  tone?: StatusBadgeTone
}>

export function StatusBadge({ children, tone = "neutral" }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        toneClassName[tone],
      )}
    >
      {children}
    </span>
  )
}
