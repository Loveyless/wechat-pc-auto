// Intl.Segmenter 类型声明
// Safari 16.4+ / Chrome 87+ 支持

declare namespace Intl {
  interface SegmenterOptions {
    localeMatcher?: "best fit" | "lookup";
    granularity?: "grapheme" | "word" | "sentence";
  }

  interface SegmentData {
    segment: string;
    index: number;
    input: string;
    isWordLike?: boolean;
  }

  interface Segments {
    containing(index?: number): SegmentData | undefined;
    [Symbol.iterator](): IterableIterator<SegmentData>;
  }

  class Segmenter {
    constructor(locales?: string | string[], options?: SegmenterOptions);
    segment(input: string): Segments;
    resolvedOptions(): {
      locale: string;
      granularity: "grapheme" | "word" | "sentence";
    };
    static supportedLocalesOf(
      locales: string | string[],
      options?: { localeMatcher?: "best fit" | "lookup" }
    ): string[];
  }
}
