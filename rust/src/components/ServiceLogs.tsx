import { useRef, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { useEventStore } from "@/stores/eventStore";
import { LogCardTitle } from "@/components/LogCardTitle";

export function ServiceLogs() {
  const events = useEventStore((s) => s.events);
  const scrollRef = useRef<HTMLDivElement>(null);

  const logEvents = events.filter(
    (e) => e.type === "log" || e.type === "error" || e.type === "status",
  );
  const recent = logEvents.slice(-200);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [recent.length]);

  return (
    <div className="glass-card rounded-2xl shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center justify-between">
        <LogCardTitle
          title="服务日志"
          summary="这里聚焦后台服务层的执行输出，适合查看日志记录、状态反馈和错误信息，定位任务为什么成功、失败或卡住。"
          highlights={[
            "只保留 log、error、status 这类服务视角事件，不会展示全部消息型事件。",
            "更适合排查调用结果、异常堆栈、服务返回和后台流程推进情况。",
            "当事件流提示有异常时，通常可以在这里看到更接近根因的线索。",
          ]}
        />
        <Badge variant="secondary" className="text-[10px] font-normal">
          {logEvents.length}
        </Badge>
      </div>
      <div
        ref={scrollRef}
        className="max-h-72 overflow-y-auto p-4 font-mono text-[11px] space-y-0.5"
      >
        {recent.length === 0 && (
          <p className="text-muted-foreground text-xs py-10 text-center font-sans">
            暂无日志
          </p>
        )}
        {recent.map((evt) => (
          <div key={evt.id} className="flex items-start gap-2 py-0.5">
            <span className="text-muted-foreground shrink-0 w-[120px]">
              {evt.timestamp}
            </span>
            <span
              className={`${
                evt.type === "error" ? "text-destructive" : "text-foreground/80"
              } break-all`}
            >
              [{evt.source}] {JSON.stringify(evt.payload)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
