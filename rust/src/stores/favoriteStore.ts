import { create } from "zustand";
import * as api from "@/lib/tauri-api";
import type { WordEntry } from "@/lib/tauri-api";

interface FavoriteStoreState {
  // 缓存已知的收藏状态（避免重复查询）
  favoriteCache: Map<string, boolean>;
  
  // 正在进行的请求（防重复）
  pendingChecks: Set<string>;
  
  // Actions
  checkFavorite: (word: string) => Promise<boolean>;
  checkFavoritesBatch: (words: string[]) => Promise<void>;
  toggleFavorite: (word: string, entry?: WordEntry) => Promise<boolean>;
  invalidateCache: (word?: string) => void;
  isCached: (word: string) => boolean;
  getCachedStatus: (word: string) => boolean | undefined;
}

export const useFavoriteStore = create<FavoriteStoreState>((set, get) => ({
  favoriteCache: new Map(),
  pendingChecks: new Set(),

  checkFavorite: async (word) => {
    const normalized = word.toLowerCase().trim();
    if (!normalized) return false;
    
    // 检查缓存
    const cached = get().favoriteCache.get(normalized);
    if (cached !== undefined) {
      return cached;
    }
    
    // 防重复请求
    if (get().pendingChecks.has(normalized)) {
      return false;
    }
    
    set((s) => ({
      pendingChecks: new Set(s.pendingChecks).add(normalized),
    }));
    
    try {
      const isFavorited = await api.isWordFavorited(normalized);
      set((s) => {
        const newCache = new Map(s.favoriteCache);
        newCache.set(normalized, isFavorited);
        return { favoriteCache: newCache };
      });
      return isFavorited;
    } catch {
      return false;
    } finally {
      set((s) => {
        const next = new Set(s.pendingChecks);
        next.delete(normalized);
        return { pendingChecks: next };
      });
    }
  },

  checkFavoritesBatch: async (words) => {
    const normalized = words
      .map((w) => w.toLowerCase().trim())
      .filter((w) => w && !get().favoriteCache.has(w));
    
    if (normalized.length === 0) return;
    
    try {
      const results = await api.getFavoritesBatch(normalized);
      set((s) => {
        const newCache = new Map(s.favoriteCache);
        for (const [word, isFavorited] of Object.entries(results)) {
          newCache.set(word, isFavorited);
        }
        return { favoriteCache: newCache };
      });
    } catch {
      // 静默失败
    }
  },

  toggleFavorite: async (word, entry) => {
    const normalized = word.toLowerCase().trim();
    if (!normalized) return false;
    
    try {
      const newStatus = await api.toggleFavorite(normalized, entry);
      set((s) => {
        const newCache = new Map(s.favoriteCache);
        newCache.set(normalized, newStatus);
        return { favoriteCache: newCache };
      });
      return newStatus;
    } catch {
      return get().favoriteCache.get(normalized) ?? false;
    }
  },

  invalidateCache: (word) => {
    if (word) {
      set((s) => {
        const newCache = new Map(s.favoriteCache);
        newCache.delete(word.toLowerCase().trim());
        return { favoriteCache: newCache };
      });
    } else {
      set({ favoriteCache: new Map() });
    }
  },

  isCached: (word) => {
    return get().favoriteCache.has(word.toLowerCase().trim());
  },

  getCachedStatus: (word) => {
    return get().favoriteCache.get(word.toLowerCase().trim());
  },
}));
