import type { PropsWithChildren } from "react"

import { cn } from "@/lib/utils"

export type StatusBadgeTone =
  | "primary"
  | "neutral"
  | "accent"
  | "success"
  | "info"
  | "warning"
  | "danger"
  | "preview"
  | "unread"

const toneClassName: Record<StatusBadgeTone, string> = {
  primary: "border-state-progress/15 bg-state-progress-soft text-state-progress",
  neutral: "border-border-subtle bg-surface-panel-muted/80 text-text-secondary",
  accent: "border-state-info/15 bg-state-info-soft text-state-info",
  success: "border-state-ready/15 bg-state-ready-soft text-state-ready",
  info: "border-state-info/15 bg-state-info-soft text-state-info",
  warning: "border-state-warning/15 bg-state-warning-soft text-state-warning",
  danger: "border-state-danger/15 bg-state-danger-soft text-state-danger",
  preview: "border-state-preview/20 bg-state-preview-soft text-state-preview",
  unread: "border-state-progress/20 bg-state-progress text-text-inverse shadow-sm",
}

type StatusBadgeProps = PropsWithChildren<{
  tone?: StatusBadgeTone
}>

export function StatusBadge({ children, tone = "neutral" }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-[0.04em]",
        toneClassName[tone],
      )}
    >
      {children}
    </span>
  )
}
