import { listen } from "@tauri-apps/api/event";
import { create } from "zustand";
import type { AppRuntime, TaskState, TranslatorServiceStatus } from "@/lib/types";

const defaultTaskState: TaskState = {
  monitoring: false,
  sidebar: false,
};

const defaultTranslatorStatus: TranslatorServiceStatus = {
  enabled: false,
  configured: false,
  checking: false,
  healthy: null,
  last_error: null,
  provider: "",
};

interface RuntimeStoreState {
  runtime: AppRuntime;
  setRuntime: (runtime: AppRuntime) => void;
  setTaskState: (tasks: TaskState) => void;
  setTranslatorStatus: (translator: TranslatorServiceStatus) => void;
  setCloseToTray: (enabled: boolean) => void;
  initRuntimeListener: () => Promise<() => void>;
}

export const useRuntimeStore = create<RuntimeStoreState>((set) => ({
  runtime: {
    tasks: defaultTaskState,
    translator: defaultTranslatorStatus,
    close_to_tray: true,
  },

  setRuntime: (runtime) => set({ runtime }),

  setTaskState: (tasks) =>
    set((state) => ({
      runtime: {
        ...state.runtime,
        tasks,
      },
    })),

  setTranslatorStatus: (translator) =>
    set((state) => ({
      runtime: {
        ...state.runtime,
        translator,
      },
    })),

  setCloseToTray: (enabled) =>
    set((state) => ({
      runtime: {
        ...state.runtime,
        close_to_tray: enabled,
      },
    })),

  initRuntimeListener: async () => {
    const unlisten = await listen<AppRuntime>("runtime-updated", (event) => {
      useRuntimeStore.getState().setRuntime(event.payload);
    });

    return unlisten;
  },
}));
