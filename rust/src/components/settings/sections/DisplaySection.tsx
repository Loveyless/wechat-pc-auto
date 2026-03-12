import { forwardRef } from "react";
import { MonitorPlay } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { SettingsSection } from "@/components/SettingsSection";
import type { SettingsDraft } from "@/stores/settingsStore";

interface DisplaySectionProps {
  draft: SettingsDraft;
  sectionDirty: boolean;
  isSaving: boolean;
  onApply: () => void;
  onReset: () => void;
  updateDraft: (updates: Partial<SettingsDraft>) => void;
}

export const DisplaySection = forwardRef<HTMLElement, DisplaySectionProps>(
  function DisplaySection(
    { draft, sectionDirty, isSaving, onApply, onReset, updateDraft },
    ref
  ) {
    const handleResetAll = () => {
      updateDraft({
        collapsedDisplayCount: "3",
        ghostMode: false,
        bgOpacity: "0.8",
        blur: "strong",
        cardStyle: "standard",
        textEnhance: "none",
      });
    };

    const handleResetAppearance = () => {
      updateDraft({
        bgOpacity: "0.8",
        blur: "strong",
        cardStyle: "standard",
        textEnhance: "none",
      });
    };

    return (
      <SettingsSection
        id="display"
        ref={ref}
        icon={<MonitorPlay className="w-4 h-4 text-sky-600" />}
        iconBg="bg-sky-50"
        title="独立浮窗设置"
        description="独立置顶模式的浮窗参数"
        isDirty={sectionDirty}
        isSaving={isSaving}
        onApply={onApply}
        onReset={onReset}
      >
        <div className="flex justify-end -mt-2 mb-2">
          <button
            onClick={handleResetAll}
            className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
          >
            全部恢复默认
          </button>
        </div>

        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">浮窗显示消息数</Label>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 flex-wrap">
              {["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"].map((n) => (
                <button
                  key={n}
                  onClick={() => updateDraft({ collapsedDisplayCount: n })}
                  className={`w-8 h-8 rounded-lg text-sm font-medium transition-all duration-150 ${
                    draft.collapsedDisplayCount === n
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
            <span className="text-xs text-muted-foreground">条</span>
          </div>
          <p className="text-[11px] text-muted-foreground">浮窗显示的消息数量，重新开启浮窗后生效</p>
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label className="text-sm font-medium">隐身模式</Label>
            <p className="text-[11px] text-muted-foreground">
              开启后浮窗不可点击，鼠标事件穿透到下层应用
            </p>
          </div>
          <Switch
            checked={draft.ghostMode}
            onCheckedChange={(checked) => updateDraft({ ghostMode: checked })}
          />
        </div>

        <div className="space-y-3 pt-2 border-t border-border/40">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium">浮窗外观</Label>
            <button
              onClick={handleResetAppearance}
              className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            >
              恢复默认
            </button>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs text-muted-foreground">背景透明度</Label>
              <span className="text-xs text-muted-foreground tabular-nums">
                {Math.round(parseFloat(draft.bgOpacity) * 100)}%
              </span>
            </div>
            <input
              type="range"
              min="0.2"
              max="1"
              step="0.05"
              value={draft.bgOpacity}
              onChange={(e) => updateDraft({ bgOpacity: e.target.value })}
              className="w-full h-1.5 bg-muted rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-sm"
            />
            <p className="text-[10px] text-muted-foreground">越低越能看清下层应用</p>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">背景模糊</Label>
            <div className="flex items-center gap-1">
              {([
                { value: "none", label: "关闭" },
                { value: "weak", label: "弱" },
                { value: "medium", label: "中" },
                { value: "strong", label: "强" },
              ] as const).map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => updateDraft({ blur: opt.value })}
                  className={`flex-1 px-2 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                    draft.blur === opt.value
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">文字增强</Label>
            <div className="flex items-center gap-1">
              {([
                { value: "none", label: "关闭" },
                { value: "shadow", label: "阴影" },
                { value: "bold", label: "加粗" },
              ] as const).map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => updateDraft({ textEnhance: opt.value })}
                  className={`flex-1 px-2 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                    draft.textEnhance === opt.value
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground">低透明度时建议开启，提高文字清晰度</p>
          </div>
        </div>
      </SettingsSection>
    );
  }
);
