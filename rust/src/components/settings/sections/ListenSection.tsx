import { forwardRef } from "react";
import { Headphones } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { SettingsSection } from "@/components/SettingsSection";
import type { SidebarWindowMode } from "@/stores/formStore";
import type { SettingsDraft } from "@/stores/settingsStore";

interface ListenSectionProps {
  draft: SettingsDraft;
  sectionDirty: boolean;
  isSaving: boolean;
  monitoring: boolean;
  sidebarRunning: boolean;
  sidebarWindowMode: SidebarWindowMode;
  onApply: () => void;
  onReset: () => void;
  onMonitoringToggle: (checked: boolean) => void;
  onSidebarModeChange: (mode: SidebarWindowMode) => void;
  updateDraft: (updates: Partial<SettingsDraft>) => void;
  monitoringBusy: boolean;
}

export const ListenSection = forwardRef<HTMLElement, ListenSectionProps>(
  function ListenSection(
    {
      draft,
      sectionDirty,
      isSaving,
      monitoring,
      sidebarRunning,
      sidebarWindowMode,
      onApply,
      onReset,
      onMonitoringToggle,
      onSidebarModeChange,
      updateDraft,
      monitoringBusy,
    },
    ref
  ) {
    return (
      <SettingsSection
        id="listen"
        ref={ref}
        icon={<Headphones className="w-4 h-4 text-emerald-600" />}
        iconBg="bg-emerald-50"
        title="消息监听"
        description="轮询控制与浮窗联动"
        isDirty={sectionDirty}
        isSaving={isSaving}
        onApply={onApply}
        onReset={onReset}
      >
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-medium">消息监听</h4>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              关闭后只暂停轮询；若浮窗已开启，会保留当前窗口和翻译状态，恢复监听后继续收流
            </p>
          </div>
          <Switch
            checked={monitoring}
            onCheckedChange={onMonitoringToggle}
            disabled={monitoringBusy}
          />
        </div>

        {!monitoring && sidebarRunning && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/8 px-4 py-3">
            <div className="text-sm font-medium text-amber-700 dark:text-amber-300">
              监听已暂停，浮窗仍在运行
            </div>
            <p className="text-[11px] text-amber-700/80 dark:text-amber-300/80 mt-1">
              当前不会接收新消息；重新打开监听后，浮窗会自动继续展示和翻译新内容。
            </p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">轮询间隔</Label>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min="0.3"
                step="0.1"
                value={draft.pollInterval}
                onChange={(e) => updateDraft({ pollInterval: e.target.value })}
              />
              <span className="text-xs text-muted-foreground shrink-0">秒</span>
            </div>
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">浮窗宽度</Label>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min="200"
                step="10"
                value={draft.displayWidth}
                onChange={(e) => updateDraft({ displayWidth: e.target.value })}
              />
              <span className="text-xs text-muted-foreground shrink-0">px</span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-4 rounded-xl border border-border/60 bg-background/40 px-4 py-3">
          <div>
            <h4 className="text-sm font-medium">右侧详情补充</h4>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              关闭时只监听左侧列表最新预览；开启后读取右侧消息区补充详情。无论开关状态，都会读取右侧标题区区分群聊和私聊。
            </p>
          </div>
          <Switch
            checked={draft.useRightPanelDetails}
            onCheckedChange={(v) => updateDraft({ useRightPanelDetails: v })}
          />
        </div>

        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">浮窗模式</Label>
          <div className="grid grid-cols-2 gap-3">
            {([
              { value: "follow" as SidebarWindowMode, label: "跟随微信", desc: "贴在微信窗口右侧，层级与微信一致" },
              { value: "independent" as SidebarWindowMode, label: "独立置顶", desc: "屏幕右上角，最高层级，可拖拽和折叠" },
            ]).map((opt) => (
              <button
                key={opt.value}
                onClick={() => onSidebarModeChange(opt.value)}
                className={`text-left rounded-xl border p-3 transition-all duration-150 ${
                  sidebarWindowMode === opt.value
                    ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                    : "border-border hover:border-muted-foreground/30"
                }`}
              >
                <span className={`text-sm font-medium ${
                  sidebarWindowMode === opt.value ? "text-primary" : ""
                }`}>{opt.label}</span>
                <p className="text-[11px] text-muted-foreground mt-0.5">{opt.desc}</p>
              </button>
            ))}
          </div>
          {sidebarRunning && (
            <p className="text-[11px] text-amber-600 dark:text-amber-400">
              浮窗运行中，切换模式需要重新开启浮窗后生效
            </p>
          )}
        </div>
      </SettingsSection>
    );
  }
);
