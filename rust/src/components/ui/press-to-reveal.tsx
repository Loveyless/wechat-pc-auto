/**
 * TranslatedText 组件
 * 
 * 用于显示翻译内容，hover 时通过 Tooltip 显示英文原文
 * 
 * 使用场景：
 * - 词典释义：中文释义 → hover 显示英文原文
 * - 例句翻译：中文翻译 → hover 显示英文例句
 */

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * 用于释义的翻译文本组件
 * 
 * 交互方式：
 * - 默认显示中文翻译
 * - hover / 长按：Tooltip 显示英文原文
 * - 视觉提示：底部虚线 + hover 变色
 */
interface TranslatedTextProps {
  /** 中文翻译 */
  chinese?: string;
  /** 英文原文 */
  english: string;
  /** 额外的样式类名 */
  className?: string;
}

export function TranslatedText({
  chinese,
  english,
  className,
}: TranslatedTextProps) {
  // 如果没有中文翻译，直接显示英文（无需 Tooltip）
  if (!chinese) {
    return <span className={className}>{english}</span>;
  }

  // 如果中英文相同，直接显示（无需 Tooltip）
  if (chinese === english) {
    return <span className={className}>{chinese}</span>;
  }

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              // 基础样式
              "cursor-help",
              // 底部虚线提示（表示可 hover 查看原文）
              "border-b border-dotted border-muted-foreground/40",
              // hover 效果
              "hover:border-primary hover:text-primary",
              // 过渡动画
              "transition-colors duration-150",
              // 用户自定义样式
              className,
            )}
          >
            {chinese}
          </span>
        </TooltipTrigger>
        <TooltipContent 
          side="top" 
          className="px-2 py-1.5 text-xs bg-zinc-800 text-zinc-100 border-zinc-700"
        >
          <p className="font-normal italic whitespace-nowrap">{english}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
