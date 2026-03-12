import { create } from "zustand";
import type { SidebarMessage, StoredMessage } from "@/lib/types";

const MAX_MESSAGES = 200;
const TRIM_TO = 150;

interface SidebarStoreState {
  items: SidebarMessage[];
  currentChat: string;
  refreshVersion: number;
  remoteRefreshVersion: number;
  setCurrentChat: (chatName: string) => void;
  requestRefresh: (chatName?: string, remoteVersion?: number) => void;
  hydrateSnapshot: (chatName: string, dbMessages: StoredMessage[], remoteVersion?: number) => void;
  updateMessageTranslation: (messageId: number, textEn: string, translateError: string) => void;
  clearMessages: () => void;
}

function storedToSidebar(message: StoredMessage): SidebarMessage {
  return {
    id: message.id,  // 使用数据库 ID 作为稳定的 key，避免 UI 闪烁
    chatName: message.chat_name,
    chatType: message.chat_type || undefined,
    sender: message.sender,
    textCn: message.content,
    textEn: message.content_en || "",
    translateError: "",
    timestamp: message.detected_at,
    isSelf: message.is_self,
    imagePath: message.image_path || undefined,
  };
}

export const useSidebarStore = create<SidebarStoreState>((set) => ({
  items: [],
  currentChat: "",
  refreshVersion: 0,
  remoteRefreshVersion: 0,

  setCurrentChat: (chatName) =>
    set((state) => {
      if (!chatName || state.currentChat === chatName) {
        return state;
      }
      // 只更新标题，不递增 refreshVersion
      // 快照拉取完全由 sidebar-refresh 事件驱动
      return { currentChat: chatName };
    }),

  requestRefresh: (chatName, remoteVersion) =>
    set((state) => ({
      currentChat: chatName || state.currentChat,
      refreshVersion: state.refreshVersion + 1,
      remoteRefreshVersion: remoteVersion ?? state.remoteRefreshVersion,
    })),

  hydrateSnapshot: (chatName, dbMessages, remoteVersion) =>
    set((state) => {
      // 防止"标题变了但内容空"的闪断
      // 如果返回空列表但当前聊天非空且一致，保留旧列表
      if (dbMessages.length === 0 && chatName && chatName === state.currentChat && state.items.length > 0) {
        return {
          remoteRefreshVersion: remoteVersion ?? state.remoteRefreshVersion,
        };
      }

      const nextItems = dbMessages
        .slice()
        .reverse()
        .map(storedToSidebar);

      return {
        items:
          nextItems.length > MAX_MESSAGES
            ? nextItems.slice(nextItems.length - TRIM_TO)
            : nextItems,
        currentChat: chatName || state.currentChat,
        remoteRefreshVersion: remoteVersion ?? state.remoteRefreshVersion,
      };
    }),

  updateMessageTranslation: (messageId, textEn, translateError) =>
    set((state) => {
      const items = state.items.map((item) =>
        item.id === messageId
          ? { ...item, textEn, translateError }
          : item
      );
      return { items };
    }),

  clearMessages: () =>
    set((state) => ({
      items: [],
      currentChat: "",
      refreshVersion: state.refreshVersion + 1,
      remoteRefreshVersion: 0,
    })),
}));
