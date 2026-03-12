import { listen } from "@tauri-apps/api/event";
import { create } from "zustand";
import type { AppSettings } from "@/lib/types";

export interface SettingsDraft {
  translateEnabled: boolean;
  translateProvider: string;
  deeplxUrl: string;
  // AI 翻译相关
  aiInputMode: "registry" | "custom"; // registry = models.dev, custom = 自定义
  aiProviderId: string;
  aiModelId: string;
  aiApiKey: string;
  aiBaseUrl: string;
  // 通用配置
  sourceLang: string;
  targetLang: string;
  translateTimeout: string;
  translateMaxConcurrency: string;
  translateMaxRequestsPerSecond: string;
  pollInterval: string;
  useRightPanelDetails: boolean;
  displayWidth: string;
  collapsedDisplayCount: string;
  ghostMode: boolean;
  // 浮窗外观
  bgOpacity: string;
  blur: string;
  cardStyle: string;
  textEnhance: string;
  // 词典设置
  dictProvider: string;
}


export function draftFromSettings(settings: AppSettings): SettingsDraft {
  // 判断是否为自定义模式：如果有 base_url 但没有 provider_id，或者 provider_id 不在已知列表中
  const isCustomMode = settings.translate.ai_base_url && !settings.translate.ai_provider_id;
  return {
    translateEnabled: settings.translate.enabled,
    translateProvider: settings.translate.provider,
    deeplxUrl: settings.translate.deeplx_url,
    aiInputMode: isCustomMode ? "custom" : "registry",
    aiProviderId: settings.translate.ai_provider_id || "",
    aiModelId: settings.translate.ai_model_id || "",
    aiApiKey: settings.translate.ai_api_key || "",
    aiBaseUrl: settings.translate.ai_base_url || "",
    sourceLang: settings.translate.source_lang,
    targetLang: settings.translate.target_lang,
    translateTimeout: String(settings.translate.timeout_seconds),
    translateMaxConcurrency: String(settings.translate.max_concurrency),
    translateMaxRequestsPerSecond: String(settings.translate.max_requests_per_second),
    pollInterval: String(settings.listen.interval_seconds),
    useRightPanelDetails: settings.listen.use_right_panel_details,
    displayWidth: String(settings.display.width),
    collapsedDisplayCount: String(settings.display.collapsed_display_count || 3),
    ghostMode: settings.display.ghost_mode ?? false,
    bgOpacity: String(settings.display.sidebar_appearance?.bg_opacity ?? 0.8),
    blur: settings.display.sidebar_appearance?.blur ?? "strong",
    cardStyle: settings.display.sidebar_appearance?.card_style ?? "standard",
    textEnhance: settings.display.sidebar_appearance?.text_enhance ?? "none",
    dictProvider: settings.dict?.provider || "cambridge",
  };
}

export function settingsFromDraft(
  settings: AppSettings,
  draft: SettingsDraft,
): AppSettings {
  return {
    ...settings,
    listen: {
      ...settings.listen,
      interval_seconds: parseFloat(draft.pollInterval) || 1,
      use_right_panel_details: draft.useRightPanelDetails,
    },
    translate: {
      ...settings.translate,
      enabled: draft.translateEnabled,
      provider: draft.translateProvider,
      deeplx_url: draft.deeplxUrl,
      ai_provider_id: draft.aiProviderId,
      ai_model_id: draft.aiModelId,
      ai_api_key: draft.aiApiKey,
      ai_base_url: draft.aiBaseUrl,
      source_lang: draft.sourceLang,
      target_lang: draft.targetLang,
      timeout_seconds: parseFloat(draft.translateTimeout) || 15,
      max_concurrency: Math.max(1, parseInt(draft.translateMaxConcurrency, 10) || 1),
      max_requests_per_second: Math.max(1, parseInt(draft.translateMaxRequestsPerSecond, 10) || 1),
    },
    display: {
      ...settings.display,
      width: parseInt(draft.displayWidth, 10) || 420,
      collapsed_display_count: Math.max(1, parseInt(draft.collapsedDisplayCount, 10) || 3),
      ghost_mode: draft.ghostMode,
      sidebar_appearance: {
        bg_opacity: Math.max(0.2, Math.min(1.0, parseFloat(draft.bgOpacity) || 0.8)),
        blur: draft.blur as "none" | "weak" | "medium" | "strong",
        card_style: draft.cardStyle as "transparent" | "light" | "standard" | "dark",
        text_enhance: draft.textEnhance as "none" | "shadow" | "bold",
      },
    },
    dict: {
      ...settings.dict,
      provider: draft.dictProvider,
    },
  };
}

export type SettingsSection = "listen" | "translate" | "display";

interface SectionDirtyState {
  listen: boolean;
  translate: boolean;
  display: boolean;
}

interface SettingsStoreState {
  settings: AppSettings | null;
  draft: SettingsDraft;
  sectionDirty: SectionDirtyState;
  setSettings: (settings: AppSettings) => void;
  updateDraft: (patch: Partial<SettingsDraft>, section?: SettingsSection) => void;
  resetDraft: () => void;
  resetSection: (section: SettingsSection) => void;
  markSectionClean: (section: SettingsSection) => void;
  initSettingsListener: () => Promise<() => void>;
}

const SECTION_FIELDS: Record<SettingsSection, (keyof SettingsDraft)[]> = {
  listen: ["pollInterval", "useRightPanelDetails"],
  translate: [
    "translateEnabled",
    "translateProvider",
    "deeplxUrl",
    "aiProviderId",
    "aiModelId",
    "aiApiKey",
    "aiBaseUrl",
    "sourceLang",
    "targetLang",
    "translateTimeout",
    "translateMaxConcurrency",
    "translateMaxRequestsPerSecond",
  ],
  display: ["displayWidth", "collapsedDisplayCount", "ghostMode", "bgOpacity", "blur", "cardStyle", "textEnhance"],
};

function createEmptyDraft(): SettingsDraft {
  return {
    translateEnabled: false,
    translateProvider: "deeplx",
    deeplxUrl: "",
    aiInputMode: "registry",
    aiProviderId: "",
    aiModelId: "",
    aiApiKey: "",
    aiBaseUrl: "",
    sourceLang: "auto",
    targetLang: "EN",
    translateTimeout: "15",
    translateMaxConcurrency: "3",
    translateMaxRequestsPerSecond: "3",
    pollInterval: "1",
    useRightPanelDetails: false,
    displayWidth: "420",
    collapsedDisplayCount: "3",
    ghostMode: false,
    bgOpacity: "0.8",
    blur: "strong",
    cardStyle: "standard",
    textEnhance: "none",
    dictProvider: "cambridge",
  };
}

export const useSettingsStore = create<SettingsStoreState>((set, get) => ({
  settings: null,
  draft: createEmptyDraft(),
  sectionDirty: { listen: false, translate: false, display: false },

  setSettings: (settings) =>
    set({
      settings,
      draft: draftFromSettings(settings),
      sectionDirty: { listen: false, translate: false, display: false },
    }),

  updateDraft: (patch, section) =>
    set((state) => {
      const nextDraft = { ...state.draft, ...patch };
      const nextDirty = { ...state.sectionDirty };

      if (section) {
        nextDirty[section] = true;
      } else {
        // Auto-detect section from patch keys
        for (const key of Object.keys(patch) as (keyof SettingsDraft)[]) {
          for (const sec of Object.keys(SECTION_FIELDS) as SettingsSection[]) {
            if (SECTION_FIELDS[sec].includes(key)) {
              nextDirty[sec] = true;
            }
          }
        }
      }

      return { draft: nextDraft, sectionDirty: nextDirty };
    }),

  resetDraft: () => {
    const settings = get().settings;
    if (!settings) return;
    set({
      draft: draftFromSettings(settings),
      sectionDirty: { listen: false, translate: false, display: false },
    });
  },

  resetSection: (section) => {
    const settings = get().settings;
    if (!settings) return;
    const baseline = draftFromSettings(settings);
    const patch: Partial<SettingsDraft> = {};
    for (const key of SECTION_FIELDS[section]) {
      (patch as Record<string, unknown>)[key] = baseline[key];
    }
    set((state) => ({
      draft: { ...state.draft, ...patch },
      sectionDirty: { ...state.sectionDirty, [section]: false },
    }));
  },

  markSectionClean: (section) =>
    set((state) => ({
      sectionDirty: { ...state.sectionDirty, [section]: false },
    })),

  initSettingsListener: async () => {
    const unlisten = await listen<AppSettings>("settings-updated", (event) => {
      useSettingsStore.getState().setSettings(event.payload);
    });

    return unlisten;
  },
}));
