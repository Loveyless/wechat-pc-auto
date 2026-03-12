/**
 * 单词释义展示组件
 * 
 * 提供统一的释义展示样式，供 WordPopover、WordBook 等组件复用
 */

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { Definition, Meaning } from "@/lib/tauri-api";
import { Skeleton } from "@/components/ui/skeleton";
import { TranslatedText } from "@/components/ui/press-to-reveal";

// ==================== DefinitionItem ====================

interface DefinitionItemProps {
  definition: Definition;
  /** 是否正在翻译中 */
  translating?: boolean;
  /** 是否显示例句 */
  showExample?: boolean;
}

/**
 * 单个释义项
 * 
 * 显示：中文释义 → 英文例句 → 例句中文翻译
 */
export function DefinitionItem({ 
  definition, 
  translating = false,
  showExample = true,
}: DefinitionItemProps) {
  return (
    <div className="py-1.5 border-b border-border last:border-b-0">
      {/* 中文释义为主，按住显示英文原文 */}
      {translating ? (
        <Skeleton className="h-4 w-3/4" />
      ) : (
        <p className="text-xs text-foreground leading-relaxed">
          <TranslatedText
            chinese={definition.chinese}
            english={definition.english}
          />
        </p>
      )}
      
      {/* 英文例句 */}
      {showExample && definition.example && (
        <p className="text-[11px] text-muted-foreground mt-1 italic">
          例: {definition.example}
        </p>
      )}
      
      {/* 例句中文翻译，按住显示英文原文 */}
      {showExample && definition.example && (
        translating ? (
          <Skeleton className="h-3 w-2/3 mt-0.5" />
        ) : definition.example_chinese ? (
          <p className="text-[11px] text-primary/70 mt-0.5">
            <TranslatedText
              chinese={definition.example_chinese}
              english={definition.example}
            />
          </p>
        ) : null
      )}
    </div>
  );
}

// ==================== MeaningItem ====================

interface MeaningItemProps {
  meaning: Meaning;
  /** 是否正在翻译中 */
  translating?: boolean;
  /** 最多显示几个释义 */
  maxDefinitions?: number;
  /** 是否显示例句 */
  showExample?: boolean;
  /** 是否显示同义词 */
  showSynonyms?: boolean;
}

/**
 * 词性分组释义
 * 
 * 显示：词性标签 + 释义列表 + 同义词
 */
export function MeaningItem({ 
  meaning, 
  translating = false,
  maxDefinitions = 3,
  showExample = true,
  showSynonyms = true,
}: MeaningItemProps) {
  const [expanded, setExpanded] = useState(false);
  const hasMore = meaning.definitions.length > maxDefinitions;
  const displayedDefs = expanded 
    ? meaning.definitions 
    : meaning.definitions.slice(0, maxDefinitions);

  return (
    <div className="mb-3 last:mb-0">
      {/* 词性标签 */}
      <div className="flex items-center gap-1.5 mb-1">
        <span className="text-[10px] font-medium text-primary-foreground bg-primary px-1.5 py-0.5 rounded">
          {meaning.part_of_speech}
        </span>
        <span className="text-[10px] text-muted-foreground">
          {meaning.part_of_speech_zh}
        </span>
      </div>
      
      {/* 释义列表 */}
      <div className="pl-2 border-l-2 border-primary/30">
        {displayedDefs.map((def, i) => (
          <DefinitionItem
            key={i}
            definition={def}
            translating={translating}
            showExample={showExample}
          />
        ))}
        {hasMore && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-0.5 text-[10px] text-primary hover:text-primary/80 py-1 transition-colors"
          >
            {expanded ? (
              <>
                <ChevronUp className="w-3 h-3" />
                收起释义
              </>
            ) : (
              <>
                <ChevronDown className="w-3 h-3" />
                +{meaning.definitions.length - maxDefinitions} 更多释义
              </>
            )}
          </button>
        )}
      </div>
      
      {/* 同义词 */}
      {showSynonyms && meaning.synonyms.length > 0 && (
        <p className="text-[10px] text-muted-foreground mt-1">
          <span className="opacity-70">同义词:</span> {meaning.synonyms.slice(0, 5).join(", ")}
        </p>
      )}
    </div>
  );
}

// ==================== WordMeaningsCard ====================

interface WordMeaningsCardProps {
  /** 释义列表 */
  meanings: Meaning[];
  /** 中文总释义 */
  summaryZh?: string;
  /** 是否正在翻译中 */
  translating?: boolean;
  /** 最多显示几个词性分组 */
  maxMeanings?: number;
  /** 每个词性最多显示几个释义 */
  maxDefinitions?: number;
  /** 是否显示例句 */
  showExample?: boolean;
  /** 是否显示同义词 */
  showSynonyms?: boolean;
  /** 是否紧凑模式（用于列表卡片） */
  compact?: boolean;
}

/**
 * 完整的单词释义卡片
 * 
 * 包含：中文总释义 + 词性分组释义
 */
export function WordMeaningsCard({
  meanings,
  summaryZh,
  translating = false,
  maxMeanings = 10,
  maxDefinitions = 3,
  showExample = true,
  showSynonyms = true,
  compact = false,
}: WordMeaningsCardProps) {
  const displayedMeanings = meanings.slice(0, maxMeanings);

  // 紧凑模式：显示词性 + 中文释义列表
  if (compact) {
    // 无释义数据时的回退
    if (displayedMeanings.length === 0) {
      if (summaryZh) {
        return (
          <p className="text-sm text-primary font-medium">
            {summaryZh}
          </p>
        );
      }
      return null;
    }
    
    // 显示前 2 个词性分组，每个词性显示前 2 个释义
    // 紧凑模式下点击卡片会进入详情，所以这里不需要展开功能
    return (
      <div className="space-y-1.5">
        {displayedMeanings.slice(0, 2).map((meaning, i) => (
          <div key={i} className="text-sm">
            <span className="text-[10px] font-medium text-primary-foreground bg-primary px-1 py-0.5 rounded mr-1.5">
              {meaning.part_of_speech_zh || meaning.part_of_speech}
            </span>
            <span className="text-foreground">
              {meaning.definitions
                .slice(0, 2)
                .map((d, idx) => (
                  <span key={idx}>
                    {idx > 0 && "；"}
                    <TranslatedText
                      chinese={d.chinese}
                      english={d.english}
                    />
                  </span>
                ))}
            </span>
          </div>
        ))}
        {displayedMeanings.length > 2 && (
          <p className="text-[10px] text-primary/70">
            点击查看 +{displayedMeanings.length - 2} 更多词性
          </p>
        )}
      </div>
    );
  }

  // 完整模式
  return (
    <div className="space-y-3">
      {/* 中文总释义 */}
      {summaryZh && (
        <p className="text-sm text-primary font-medium border-b border-border pb-2">
          {summaryZh}
        </p>
      )}
      
      {/* 词性分组 */}
      {displayedMeanings.map((meaning, i) => (
        <MeaningItem
          key={i}
          meaning={meaning}
          translating={translating}
          maxDefinitions={maxDefinitions}
          showExample={showExample}
          showSynonyms={showSynonyms}
        />
      ))}
      
      {/* 无释义时的提示 */}
      {displayedMeanings.length === 0 && !summaryZh && (
        <p className="text-xs text-muted-foreground italic">
          暂无释义
        </p>
      )}
    </div>
  );
}
