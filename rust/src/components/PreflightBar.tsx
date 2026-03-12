import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, XCircle, ExternalLink } from "lucide-react";
import { usePreflightStore } from "@/stores/preflightStore";

export function PreflightBar() {
  const result = usePreflightStore((s) => s.result);
  const check = usePreflightStore((s) => s.check);
  const promptingAccessibility = usePreflightStore((s) => s.promptingAccessibility);
  const awaitingUserAction = usePreflightStore((s) => s.awaitingUserAction);
  const settingsOpened = usePreflightStore((s) => s.settingsOpened);
  const justRecovered = usePreflightStore((s) => s.justRecovered);
  const openAccessibilitySettings = usePreflightStore((s) => s.openAccessibilitySettings);
  const retryAccessibilityCheck = usePreflightStore((s) => s.retryAccessibilityCheck);

  useEffect(() => {
    check();
    const timer = setInterval(check, 5000);
    return () => clearInterval(timer);
  }, [check]);

  if (!result) return null;

  const wechatAccessible = result.wechat_accessible ?? result.accessibility_ok;
  const allGood = result.wechat_running && result.accessibility_ok && wechatAccessible && result.wechat_has_window;

  if (allGood && !justRecovered) return null;

  const items: { text: string; level: "warn" | "error"; action?: () => void; actionLabel?: string }[] = [];

  if (allGood && justRecovered) {
    items.push({
      text: "已授权，正在继续初始化",
      level: "warn",
    });
  } else if (!result.wechat_running) {
    items.push({ text: "请先启动微信并登录", level: "warn" });
  } else if (!result.accessibility_ok) {
    if (promptingAccessibility) {
      items.push({
        text: "正在请求辅助功能权限...",
        level: "warn",
      });
    } else if (awaitingUserAction) {
      items.push({
        text: "请在刚刚打开的系统设置页面中勾选本应用",
        level: "error",
      });
    } else {
      items.push({
        text: "正在准备辅助功能授权引导...",
        level: "warn",
      });
    }
  } else if (!wechatAccessible) {
    items.push({
      text: "辅助功能已授权，但当前还读不到微信窗口；如果刚授权，请完全退出并重新打开本应用和微信。",
      level: "warn",
    });
  } else if (!result.wechat_has_window) {
    items.push({ text: "微信已运行但未检测到窗口，请确认已登录并打开主窗口", level: "warn" });
  }

  return (
    <AnimatePresence>
      {items.map((item, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className={`mb-3 px-4 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2 ${
            item.level === "error"
              ? "bg-red-50 text-red-800 border border-red-200"
              : "bg-amber-50 text-amber-800 border border-amber-200"
          }`}
        >
          {item.level === "error" ? (
            <XCircle className="w-4 h-4 shrink-0" />
          ) : (
            <AlertTriangle className="w-4 h-4 shrink-0" />
          )}
          <span className="flex-1">{item.text}</span>
          {(!result.accessibility_ok && result.wechat_running) && (
            <>
              <button
                onClick={retryAccessibilityCheck}
                className="flex items-center gap-1 text-xs underline underline-offset-2 hover:opacity-80 shrink-0"
              >
                重新检测
              </button>
              <button
                onClick={openAccessibilitySettings}
                className="flex items-center gap-1 text-xs underline underline-offset-2 hover:opacity-80 shrink-0"
              >
                {settingsOpened ? "再次打开设置页" : "打开系统设置"}
                <ExternalLink className="w-3 h-3" />
              </button>
            </>
          )}
        </motion.div>
      ))}
    </AnimatePresence>
  );
}
