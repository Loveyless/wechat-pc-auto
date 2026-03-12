import { create } from "zustand";
import { listen } from "@tauri-apps/api/event";
import type { ServiceEvent } from "@/lib/types";
import { useSidebarStore } from "./sidebarStore";
import { useRuntimeStore } from "./runtimeStore";

const MAX_EVENTS = 500;
const TRIM_TO = 300;

interface EventStoreState {
  events: ServiceEvent[];
  addEvent: (event: ServiceEvent) => void;
  initEventListener: () => Promise<() => void>;
}

export const useEventStore = create<EventStoreState>((set) => ({
  events: [],

  addEvent: (event) =>
    set((state) => {
      const next = [...state.events, event];
      return {
        events: next.length > MAX_EVENTS ? next.slice(next.length - TRIM_TO) : next,
      };
    }),

  initEventListener: async () => {
    const unlisten = await listen<ServiceEvent>("wechat-event", (e) => {
      const event = e.payload;
      const { addEvent } = useEventStore.getState();
      addEvent(event);

      if (event.type === "task_state") {
        const payload = event.payload as Record<string, unknown>;
        const state = payload.state as
          | { monitoring: boolean; sidebar: boolean }
          | undefined;
        const translator = payload.translator as
          | {
              enabled: boolean;
              configured: boolean;
              checking: boolean;
              healthy: boolean | null;
              last_error: string | null;
              provider: string;
            }
          | undefined;
        if (state) {
          useRuntimeStore.getState().setTaskState(state);
        }
        if (translator) {
          useRuntimeStore.getState().setTranslatorStatus(translator);
        }
      }

      // sidebar-refresh 事件：数据库提交成功后触发，前端拉取快照
      if (event.type === "status" && event.source === "sidebar") {
        const p = event.payload as Record<string, unknown>;
        if (p.type === "sidebar-refresh") {
          const chatName = typeof p.chat_name === "string" ? p.chat_name : undefined;
          const refreshVersion = typeof p.refresh_version === "number" ? p.refresh_version : undefined;
          useSidebarStore.getState().requestRefresh(chatName, refreshVersion);
        }
      }

      // chat_switched 事件：更新当前聊天标题（保持兼容）
      if (event.type === "status" && event.source === "monitor") {
        const p = event.payload as Record<string, unknown>;
        if (p.type === "chat_switched" && typeof p.chat_name === "string") {
          useSidebarStore.getState().setCurrentChat(p.chat_name);
        }
      }
    });

    return unlisten;
  },
}));
