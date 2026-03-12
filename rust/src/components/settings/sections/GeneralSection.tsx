import { forwardRef } from "react";
import { Monitor } from "lucide-react";
import { Switch } from "@/components/ui/switch";

interface GeneralSectionProps {
  closeToTray: boolean;
  onCloseToTrayChange: (checked: boolean) => void;
}

export const GeneralSection = forwardRef<HTMLElement, GeneralSectionProps>(
  function GeneralSection({ closeToTray, onCloseToTrayChange }, ref) {
    return (
      <section
        id="general"
        ref={ref}
        className="glass-card rounded-2xl p-6 shadow-sm space-y-5"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-slate-100 flex items-center justify-center">
            <Monitor className="w-4 h-4 text-slate-600" />
          </div>
          <div>
            <h3 className="text-sm font-semibold">通用设置</h3>
            <p className="text-[11px] text-muted-foreground">应用基本行为</p>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-medium">关闭时最小化到托盘</h4>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              关闭窗口后应用在系统托盘中继续运行
            </p>
          </div>
          <Switch
            checked={closeToTray}
            onCheckedChange={onCloseToTrayChange}
          />
        </div>
      </section>
    );
  }
);
