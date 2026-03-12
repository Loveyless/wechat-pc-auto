import { useRef, useCallback, useMemo } from "react";

export interface WordSegment {
  text: string;
  index: number;
  isWord: boolean;
}

/**
 * 检测浏览器是否支持 Intl.Segmenter API
 */
export function isSegmenterSupported(): boolean {
  return typeof Intl !== "undefined" && typeof Intl.Segmenter === "function";
}

/**
 * 分词 Hook：使用 Intl.Segmenter API 对文本进行分词
 * 
 * @param locale 语言代码，默认 "en"
 * @returns segment 函数和支持状态
 */
export function useWordSegmenter(locale: string = "en") {
  const segmenterRef = useRef<Intl.Segmenter | null>(null);

  const supported = useMemo(() => isSegmenterSupported(), []);

  const getSegmenter = useCallback(() => {
    if (!supported) return null;
    if (!segmenterRef.current) {
      segmenterRef.current = new Intl.Segmenter(locale, { granularity: "word" });
    }
    return segmenterRef.current;
  }, [locale, supported]);

  const segment = useCallback(
    (text: string): WordSegment[] => {
      const segmenter = getSegmenter();
      if (!segmenter) {
        // 降级：返回整个文本作为单个非单词片段
        return [{ text, index: 0, isWord: false }];
      }

      return [...segmenter.segment(text)].map((seg) => ({
        text: seg.segment,
        index: seg.index,
        isWord: seg.isWordLike ?? false,
      }));
    },
    [getSegmenter]
  );

  return { segment, supported };
}
