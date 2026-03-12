import { ReactNode, forwardRef } from "react";
import { Button } from "@/components/ui/button";
import { Check, RotateCcw, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface SettingsSectionProps {
  id?: string;
  icon: ReactNode;
  iconBg: string;
  title: string;
  description: string;
  isDirty: boolean;
  isSaving: boolean;
  onApply: () => void;
  onReset: () => void;
  children: ReactNode;
}

export const SettingsSection = forwardRef<HTMLElement, SettingsSectionProps>(
  function SettingsSection(
    {
      id,
      icon,
      iconBg,
      title,
      description,
      isDirty,
      isSaving,
      onApply,
      onReset,
      children,
    },
    ref
  ) {
    return (
      <section id={id} ref={ref} className="glass-card rounded-2xl p-6 shadow-sm space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-xl ${iconBg} flex items-center justify-center`}>
            {icon}
          </div>
          <div className="flex items-center gap-2">
            <div>
              <h3 className="text-sm font-semibold">{title}</h3>
              <p className="text-[11px] text-muted-foreground">{description}</p>
            </div>
            <AnimatePresence>
              {isDirty && (
                <motion.span
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0, opacity: 0 }}
                  className="w-2 h-2 rounded-full bg-amber-500"
                  title="有未应用的更改"
                />
              )}
            </AnimatePresence>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <AnimatePresence>
            {isDirty && (
              <motion.div
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="flex items-center gap-2"
              >
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 text-xs"
                  onClick={onReset}
                  disabled={isSaving}
                >
                  <RotateCcw className="w-3 h-3 mr-1" />
                  撤销
                </Button>
                <Button
                  size="sm"
                  className="h-8 text-xs"
                  onClick={onApply}
                  disabled={isSaving}
                >
                  {isSaving ? (
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                  ) : (
                    <Check className="w-3 h-3 mr-1" />
                  )}
                  {isSaving ? "应用中..." : "应用"}
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {children}
    </section>
    );
  }
);
