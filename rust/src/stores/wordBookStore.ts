import { create } from "zustand";
import * as api from "@/lib/tauri-api";
import type { FavoriteWord, ReviewSession, ReviewStats } from "@/lib/tauri-api";

interface WordBookStoreState {
  // 单词列表
  wordList: FavoriteWord[];
  totalCount: number;
  loading: boolean;
  
  // 复习状态
  currentSession: ReviewSession | null;
  reviewWords: FavoriteWord[];
  currentWordIndex: number;
  isReviewing: boolean;
  
  // 统计
  stats: ReviewStats | null;
  
  // Actions
  fetchWordList: (offset?: number, limit?: number) => Promise<void>;
  fetchStats: () => Promise<void>;
  deleteWord: (word: string) => Promise<void>;
  updateNote: (word: string, note: string) => Promise<void>;
  
  // 复习 Actions
  startReview: (mode: string, wordCount: number) => Promise<void>;
  submitFeedback: (feedback: number, responseTimeMs?: number) => Promise<FavoriteWord | null>;
  nextWord: () => void;
  finishReview: () => Promise<ReviewSession | null>;
  cancelReview: () => void;
}

export const useWordBookStore = create<WordBookStoreState>((set, get) => ({
  wordList: [],
  totalCount: 0,
  loading: false,
  currentSession: null,
  reviewWords: [],
  currentWordIndex: 0,
  isReviewing: false,
  stats: null,

  fetchWordList: async (offset = 0, limit = 50) => {
    set({ loading: true });
    try {
      const [words, count] = await Promise.all([
        api.listFavorites({ offset, limit }),
        api.countFavorites(),
      ]);
      set({ wordList: words, totalCount: count });
    } catch (e) {
      console.error("Failed to fetch word list:", e);
    } finally {
      set({ loading: false });
    }
  },

  fetchStats: async () => {
    try {
      const stats = await api.getReviewStats();
      set({ stats });
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    }
  },

  deleteWord: async (word) => {
    try {
      await api.toggleFavorite(word);
      // 重新获取列表
      get().fetchWordList();
      get().fetchStats();
    } catch (e) {
      console.error("Failed to delete word:", e);
    }
  },

  updateNote: async (word, note) => {
    try {
      await api.updateFavoriteNote(word, note);
      // 更新本地状态
      set((s) => ({
        wordList: s.wordList.map((w) =>
          w.word === word ? { ...w, note } : w
        ),
      }));
    } catch (e) {
      console.error("Failed to update note:", e);
    }
  },

  startReview: async (mode, wordCount) => {
    try {
      // 获取待复习单词
      const words = await api.getWordsForReview(wordCount);
      if (words.length === 0) {
        return;
      }
      
      // 开始会话
      const sessionId = await api.startReviewSession(mode, words.length);
      
      set({
        currentSession: {
          id: sessionId,
          started_at: new Date().toISOString(),
          mode,
          total_words: words.length,
          completed_words: 0,
          correct_count: 0,
          wrong_count: 0,
          fuzzy_count: 0,
        },
        reviewWords: words,
        currentWordIndex: 0,
        isReviewing: true,
      });
    } catch (e) {
      console.error("Failed to start review:", e);
    }
  },

  submitFeedback: async (feedback, responseTimeMs) => {
    const { currentSession, reviewWords, currentWordIndex } = get();
    if (!currentSession || currentWordIndex >= reviewWords.length) {
      return null;
    }

    const word = reviewWords[currentWordIndex];
    
    try {
      const updatedWord = await api.recordReviewFeedback({
        sessionId: currentSession.id,
        word: word.word,
        feedback,
        responseTimeMs,
      });

      // 更新会话统计
      set((s) => ({
        currentSession: s.currentSession
          ? {
              ...s.currentSession,
              completed_words: s.currentSession.completed_words + 1,
              correct_count:
                s.currentSession.correct_count + (feedback === 2 ? 1 : 0),
              fuzzy_count:
                s.currentSession.fuzzy_count + (feedback === 1 ? 1 : 0),
              wrong_count:
                s.currentSession.wrong_count + (feedback === 0 ? 1 : 0),
            }
          : null,
        // 更新单词列表中的状态
        reviewWords: s.reviewWords.map((w, i) =>
          i === currentWordIndex ? updatedWord : w
        ),
      }));

      return updatedWord;
    } catch (e) {
      console.error("Failed to submit feedback:", e);
      return null;
    }
  },

  nextWord: () => {
    const { currentWordIndex, reviewWords } = get();
    if (currentWordIndex < reviewWords.length - 1) {
      set({ currentWordIndex: currentWordIndex + 1 });
    }
  },

  finishReview: async () => {
    const { currentSession } = get();
    if (!currentSession) return null;

    try {
      const session = await api.finishReviewSession(currentSession.id);
      set({
        currentSession: null,
        reviewWords: [],
        currentWordIndex: 0,
        isReviewing: false,
      });
      // 刷新统计和列表
      get().fetchStats();
      get().fetchWordList();
      return session;
    } catch (e) {
      console.error("Failed to finish review:", e);
      return null;
    }
  },

  cancelReview: () => {
    set({
      currentSession: null,
      reviewWords: [],
      currentWordIndex: 0,
      isReviewing: false,
    });
  },
}));
