import { useRef, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { motion, AnimatePresence } from "framer-motion";
import { useEventStore } from "@/stores/eventStore";
import { LogCardTitle } from "@/components/LogCardTitle";

const typeStyles: Record<string, string> = {
  status: "bg-blue-100 text-blue-700",
  message: "bg-emerald-100 text-emerald-700",
  log: "bg-slate-100 text-slate-600",
  error: "bg-red-100 text-red-700",
  task_state: "bg-violet-100 text-violet-700",
};

export function EventStream() {
  const events = useEventStore((s) => s.events);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events.length]);

  const recent = events.slice(-120);

  return (
    <div className="glass-card rounded-2xl shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center justify-between">
        <LogCardTitle
          title="事件流"
          summary="这里展示前端收到的实时事件总线，适合快速判断监听链路、侧边栏推送和任务状态切换是否正在正常流动。"
          highlights={[
            "会混合展示 status、message、log、error、task_state 等不同事件类型。",
            "更偏运行态监控入口，适合先看系统有没有在动、哪一段开始异常。",
            "如果要看服务层输出和错误详情，配合下方“服务日志”一起判断更准确。",
          ]}
        />
        <Badge variant="secondary" className="text-[10px] font-normal">
          {events.length}
        </Badge>
      </div>
      <div
        ref={scrollRef}
        className="max-h-72 overflow-y-auto p-4 space-y-1 font-mono text-[11px]"
      >
        {recent.length === 0 && (
          <div className="text-center text-muted-foreground py-10 text-xs font-sans">
            启动任务后将显示实时事件
          </div>
        )}
        <AnimatePresence initial={false}>
          {recent.map((evt) => (
            <motion.div
              key={evt.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-start gap-2 py-0.5"
            >
              <span className="text-muted-foreground shrink-0 w-[120px]">
                {evt.timestamp}
              </span>
              <span
                className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${typeStyles[evt.type] ?? "bg-gray-100 text-gray-600"}`}
              >
                {evt.type}/{evt.source}
              </span>
              <span className="text-foreground/80 break-all">
                {JSON.stringify(evt.payload)}
              </span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
