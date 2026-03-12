import { create } from "zustand";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import type { WordEntry } from "@/lib/tauri-api";
import * as api from "@/lib/tauri-api";

interface FieldTranslatedEvent {
  word: string;
  field: string;
}

interface TranslationDoneEvent {
  word: string;
  total: number;
  translated: number;
  success: boolean;
}

interface DictionaryStoreState {
  // UI 状态
  currentWord: string | null;
  currentEntry: WordEntry | null;
  loading: boolean;
  error: string | null;
  translating: boolean;
  
  // 弹窗位置
  popoverPosition: { x: number; y: number } | null;
  
  // 正在进行的请求（防重复）
  pendingLookups: Set<string>;
  
  // Actions
  lookupWord: (word: string, position?: { x: number; y: number }) => Promise<WordEntry | null>;
  refreshCurrentEntry: () => Promise<void>;
  clearCurrent: () => void;
  setPopoverPosition: (position: { x: number; y: number } | null) => void;
  setTranslating: (translating: boolean) => void;
  updateCurrentEntry: (entry: WordEntry) => void;
}

export const useDictionaryStore = create<DictionaryStoreState>((set, get) => ({
  currentWord: null,
  currentEntry: null,
  loading: false,
  error: null,
  translating: false,
  popoverPosition: null,
  pendingLookups: new Set(),

  lookupWord: async (word, position) => {
    const normalized = word.toLowerCase().trim();
    if (!normalized) return null;
    
    // 防重复请求
    if (get().pendingLookups.has(normalized)) {
      return get().currentEntry;
    }
    
    set((s) => ({
      currentWord: normalized,
      loading: true,
      error: null,
      translating: false,
      popoverPosition: position ?? s.popoverPosition,
      pendingLookups: new Set(s.pendingLookups).add(normalized),
    }));
    
    try {
      const entry = await api.wordLookup(normalized);
      // 如果未翻译完成，标记为正在翻译
      const isTranslating = !entry.translation_completed;
      set({ currentEntry: entry, loading: false, translating: isTranslating });
      return entry;
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : String(e);
      set({ error: errorMsg, loading: false, translating: false });
      return null;
    } finally {
      set((s) => {
        const next = new Set(s.pendingLookups);
        next.delete(normalized);
        return { pendingLookups: next };
      });
    }
  },

  refreshCurrentEntry: async () => {
    const { currentWord } = get();
    if (!currentWord) return;
    
    try {
      const entry = await api.wordLookup(currentWord);
      set({ currentEntry: entry });
    } catch {
      // 静默失败
    }
  },
  
  clearCurrent: () => set({
    currentWord: null,
    currentEntry: null,
    loading: false,
    error: null,
    translating: false,
    popoverPosition: null,
  }),

  setPopoverPosition: (position) => set({ popoverPosition: position }),
  
  setTranslating: (translating) => set({ translating }),
  
  updateCurrentEntry: (entry) => set({ currentEntry: entry }),
}));

// 事件监听器（在模块加载时初始化）
let unlistenField: UnlistenFn | null = null;
let unlistenDone: UnlistenFn | null = null;

export async function initDictionaryEventListeners() {
  // 监听单字段翻译完成
  unlistenField = await listen<FieldTranslatedEvent>(
    "dictionary:field_translated",
    async (event) => {
      const { word } = event.payload;
      const store = useDictionaryStore.getState();
      
      // 只处理当前查看的单词
      if (word !== store.currentWord) return;
      
      // 重新获取最新数据
      await store.refreshCurrentEntry();
    }
  );

  // 监听翻译完成
  unlistenDone = await listen<TranslationDoneEvent>(
    "dictionary:translation_done",
    async (event) => {
      const { word } = event.payload;
      const store = useDictionaryStore.getState();
      
      // 只处理当前查看的单词
      if (word !== store.currentWord) return;
      
      // 标记翻译完成
      store.setTranslating(false);
      
      // 获取最终数据
      await store.refreshCurrentEntry();
    }
  );
}

export function cleanupDictionaryEventListeners() {
  unlistenField?.();
  unlistenDone?.();
  unlistenField = null;
  unlistenDone = null;
}
