import { useState, useMemo, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { useWordSegmenter, isSegmenterSupported } from "@/hooks/useWordSegmenter";
import { useDictionaryStore } from "@/stores/dictionaryStore";
import { useFavoriteStore } from "@/stores/favoriteStore";

interface WordSpanProps {
  word: string;
  isActive: boolean;
  isFavorited: boolean;
  onClick: (e: React.MouseEvent) => void;
}

function WordSpan({ word, isActive, isFavorited, onClick }: WordSpanProps) {
  // 样式优先级：收藏 > 点击激活 > 普通
  const getClassName = () => {
    const base = "cursor-pointer select-none transition-colors duration-150";
    
    if (isFavorited) {
      // 收藏状态优先：橙黄色 + 实线下划线
      return `${base} text-amber-600 dark:text-amber-400 underline underline-offset-2 decoration-amber-500`;
    }
    
    if (isActive) {
      // 点击激活状态：天蓝色 + 下划线
      return `${base} text-sky-600 dark:text-sky-400 underline underline-offset-2 decoration-sky-500`;
    }
    
    // 普通状态
    return `${base} hover:text-sky-600 dark:hover:text-sky-400 hover:underline hover:underline-offset-2 hover:decoration-sky-400/60`;
  };

  return (
    <motion.span
      className={getClassName()}
      whileTap={{ scale: 0.96 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      onClick={onClick}
    >
      {word}
    </motion.span>
  );
}

export interface SegmentedTextProps {
  text: string;
  className?: string;
  onWordClick?: (word: string, index: number) => void;
}

export function SegmentedText({ text, className, onWordClick }: SegmentedTextProps) {
  const { segment, supported } = useWordSegmenter("en");
  const segments = useMemo(() => segment(text), [text, segment]);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const lookupWord = useDictionaryStore((s) => s.lookupWord);
  
  // 订阅整个 favoriteCache 以确保收藏状态变化时触发重渲染
  const favoriteCache = useFavoriteStore((s) => s.favoriteCache);
  const checkFavoritesBatch = useFavoriteStore((s) => s.checkFavoritesBatch);

  // 批量预加载收藏状态
  useEffect(() => {
    const words = segments
      .filter((s) => s.isWord)
      .map((s) => s.text.toLowerCase());
    if (words.length > 0) {
      checkFavoritesBatch(words);
    }
  }, [segments, checkFavoritesBatch]);

  const handleWordClick = useCallback(
    (e: React.MouseEvent, word: string, arrayIndex: number) => {
      e.stopPropagation();
      setActiveIndex(arrayIndex);
      
      // 触发查词弹窗
      const rect = (e.target as HTMLElement).getBoundingClientRect();
      lookupWord(word, { x: rect.left, y: rect.bottom });
      
      onWordClick?.(word, arrayIndex);
    },
    [onWordClick, lookupWord]
  );

  const handleContainerClick = useCallback(() => {
    setActiveIndex(null);
  }, []);

  // 不支持分词时，直接渲染纯文本
  if (!supported) {
    return (
      <span className={className}>
        {text}
      </span>
    );
  }

  return (
    <span className={className} onClick={handleContainerClick}>
      {segments.map((seg, i) =>
        seg.isWord ? (
          <WordSpan
            key={`${i}-${seg.index}`}
            word={seg.text}
            isActive={activeIndex === i}
            isFavorited={favoriteCache.get(seg.text.toLowerCase()) ?? false}
            onClick={(e) => handleWordClick(e, seg.text, i)}
          />
        ) : (
          <span key={`${i}-${seg.index}`}>{seg.text}</span>
        )
      )}
    </span>
  );
}

export { isSegmenterSupported };
