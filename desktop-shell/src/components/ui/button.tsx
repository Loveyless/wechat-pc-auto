import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
  {
    variants: {
      variant: {
        default: "bg-state-progress text-text-inverse shadow-sm hover:bg-state-progress/90",
        secondary: "bg-surface-panel-muted text-text-primary hover:bg-surface-panel-muted/80",
        outline:
          "border border-border-subtle bg-surface-panel-strong text-text-secondary hover:border-border-strong hover:bg-surface-selected hover:text-text-primary",
        panel:
          "border border-border-subtle bg-surface-panel-strong text-text-primary shadow-sm hover:border-border-strong hover:bg-surface-panel",
        quiet:
          "bg-transparent text-text-secondary hover:bg-surface-selected/70 hover:text-text-primary",
        warning:
          "border border-state-warning/20 bg-state-warning-soft text-state-warning hover:bg-state-warning-soft/80",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-lg px-3",
        lg: "h-11 rounded-xl px-6",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  },
)
Button.displayName = "Button"

export { Button, buttonVariants }
