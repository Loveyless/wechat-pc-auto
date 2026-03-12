import { create } from "zustand";
import { persist } from "zustand/middleware";

export type DisplayMode = "translated" | "original" | "bilingual";
export type SidebarWindowMode = "follow" | "independent";

interface FormStoreState {
  displayMode: DisplayMode;
  sidebarWindowMode: SidebarWindowMode;
  imageCapture: boolean;
  setSettings: (patch: Partial<Omit<FormStoreState, "setSettings">>) => void;
}

export const useFormStore = create<FormStoreState>()(
  persist(
    (set) => ({
      displayMode: "bilingual",
      sidebarWindowMode: "follow",
      imageCapture: false,
      setSettings: (patch) => set(patch),
    }),
    {
      name: "wechat-ui-preferences",
      partialize: (state) => ({
        displayMode: state.displayMode,
        sidebarWindowMode: state.sidebarWindowMode,
        imageCapture: state.imageCapture,
      }),
    },
  ),
);
