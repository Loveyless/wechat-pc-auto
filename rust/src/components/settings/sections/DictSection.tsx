import { forwardRef } from "react";
import { BookOpen } from "lucide-react";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SettingsDraft } from "@/stores/settingsStore";

interface DictSectionProps {
  draft: SettingsDraft;
  updateDraft: (updates: Partial<SettingsDraft>) => void;
}

export const DictSection = forwardRef<HTMLElement, DictSectionProps>(
  function DictSection({ draft, updateDraft }, ref) {
    return (
      <section
        id="dict"
        ref={ref}
        className="glass-card rounded-2xl p-6 shadow-sm space-y-5"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold">词典设置</h3>
            <p className="text-[11px] text-muted-foreground">
              查词时使用的词典来源
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">词典渠道</Label>
          <Select
            value={draft.dictProvider}
            onValueChange={(v) => updateDraft({ dictProvider: v })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="cambridge">
                <div className="flex flex-col">
                  <span>Cambridge 词典</span>
                  <span className="text-[10px] text-muted-foreground">默认，离线可用，释义精准</span>
                </div>
              </SelectItem>
              <SelectItem value="free_dictionary">
                <div className="flex flex-col">
                  <span>Free Dictionary API</span>
                  <span className="text-[10px] text-muted-foreground">需全球网络，开源词典</span>
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
          <p className="text-[11px] text-muted-foreground/70">
            {draft.dictProvider === "cambridge"
              ? "Cambridge 词典内置于应用中，查词无需网络。释义和例句为英文，中文由翻译服务补充。"
              : "Free Dictionary API 需要访问国际网络。如遇查词失败，请检查网络连接或切换到 Cambridge 词典。"}
          </p>
        </div>
      </section>
    );
  }
);
