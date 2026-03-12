import { create } from "zustand";
import * as api from "@/lib/tauri-api";
import type { PreflightResult } from "@/lib/tauri-api";

const PROMPT_RECHECK_DELAY_MS = 900;
const PREFLIGHT_LOG_PREFIX = "[preflight]";

function logPreflight(message: string, extra?: unknown) {
  if (extra) {
    console.info(PREFLIGHT_LOG_PREFIX, message, extra);
    return;
  }
  console.info(PREFLIGHT_LOG_PREFIX, message);
}

interface PreflightStoreState {
  result: PreflightResult | null;
  loading: boolean;
  promptingAccessibility: boolean;
  accessibilityFlowStarted: boolean;
  lastPromptAt: number | null;
  settingsOpened: boolean;
  awaitingUserAction: boolean;
  justRecovered: boolean;
  check: () => Promise<void>;
  runAccessibilityFlow: () => Promise<void>;
  openAccessibilitySettings: () => Promise<void>;
  retryAccessibilityCheck: () => Promise<void>;
}

export const usePreflightStore = create<PreflightStoreState>((set, get) => {
  const fetchPreflight = async (): Promise<PreflightResult> => {
    set({ loading: true });
    try {
      const result = await api.preflightCheck();
      const previous = get().result;
      const recovered =
        !!previous &&
        previous.accessibility_ok === false &&
        result.accessibility_ok === true &&
        get().awaitingUserAction;

      set({
        result,
        loading: false,
        justRecovered: recovered,
        awaitingUserAction: recovered ? false : get().awaitingUserAction,
      });
      logPreflight("check result", {
        wechat_running: result.wechat_running,
        accessibility_ok: result.accessibility_ok,
        wechat_has_window: result.wechat_has_window,
        recovered,
      });
      return result;
    } catch {
      const fallback = { wechat_running: false, accessibility_ok: false, wechat_has_window: false };
      set({ result: fallback, loading: false });
      logPreflight("check failed, use fallback result");
      return fallback;
    }
  };

  const runAccessibilityFlow = async () => {
    const state = get();
    const current = state.result;
    if (!current || !current.wechat_running || current.accessibility_ok) {
      return;
    }
    if (state.accessibilityFlowStarted || state.promptingAccessibility) {
      logPreflight("flow already started, skip auto trigger");
      return;
    }

    set({
      accessibilityFlowStarted: true,
      promptingAccessibility: true,
      lastPromptAt: Date.now(),
      justRecovered: false,
    });
    logPreflight("start accessibility flow");

    try {
      const promptResult = await api.accessibilityRequestAccess();
      logPreflight("prompt attempted", promptResult);
      await new Promise((resolve) => setTimeout(resolve, PROMPT_RECHECK_DELAY_MS));
      const afterPrompt = await fetchPreflight();
      if (!afterPrompt.accessibility_ok && !get().settingsOpened) {
        await get().openAccessibilitySettings();
      }
      if (!afterPrompt.accessibility_ok) {
        set({ awaitingUserAction: true });
        logPreflight("awaiting user action in system settings");
      }
    } finally {
      set({ promptingAccessibility: false });
      logPreflight("flow step finished");
    }
  };

  return {
    result: null,
    loading: false,
    promptingAccessibility: false,
    accessibilityFlowStarted: false,
    lastPromptAt: null,
    settingsOpened: false,
    awaitingUserAction: false,
    justRecovered: false,

    check: async () => {
      const result = await fetchPreflight();
      if (result.wechat_running && !result.accessibility_ok) {
        await get().runAccessibilityFlow();
      } else if (result.accessibility_ok) {
        set({ awaitingUserAction: false, promptingAccessibility: false });
      }
    },

    runAccessibilityFlow,

    openAccessibilitySettings: async () => {
      try {
        const response = await api.accessibilityOpenSettings();
        logPreflight("open settings result", response);
        if (response.ok) {
          set({ settingsOpened: true, awaitingUserAction: true });
        }
      } catch {
        // no-op: keep current state, user can retry manually
        logPreflight("open settings failed");
      }
    },

    retryAccessibilityCheck: async () => {
      set({ justRecovered: false });
      logPreflight("manual retry check");
      await get().check();
    },
  };
});
