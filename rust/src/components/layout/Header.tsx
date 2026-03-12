import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import type { TaskState } from "@/lib/types";
import { useRuntimeStore } from "@/stores/runtimeStore";
import * as api from "@/lib/tauri-api";
import { motion } from "framer-motion";

const taskLabels: { key: keyof TaskState; label: string }[] = [
  { key: "monitoring", label: "监听" },
  { key: "sidebar", label: "浮窗" },
];

export function Header() {
  const taskState = useRuntimeStore((s) => s.runtime.tasks);
  const closeToTray = useRuntimeStore((s) => s.runtime.close_to_tray);

  function handleToggle(checked: boolean) {
    api.setCloseToTray(checked).catch(() => {});
  }

  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">WeChat PC Auto</h1>
          <p className="text-sm text-muted-foreground mt-1">
            macOS 微信自动化工具 · Rust + Tauri
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <Switch
              id="close-to-tray"
              checked={closeToTray}
              onCheckedChange={handleToggle}
            />
            <Label htmlFor="close-to-tray" className="text-xs text-muted-foreground cursor-pointer">
              关闭时最小化到托盘
            </Label>
          </div>
          <Badge variant="outline" className="text-xs">
            macOS
          </Badge>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-4">
        {taskLabels.map(({ key, label }) => (
          <Badge
            key={key}
            variant={taskState[key] ? "default" : "secondary"}
            className={
              taskState[key]
                ? "bg-primary text-primary-foreground"
                : ""
            }
          >
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 ${
                taskState[key] ? "bg-white animate-pulse" : "bg-muted-foreground/40"
              }`}
            />
            {label}
          </Badge>
        ))}
      </div>
    </motion.header>
  );
}
