import { create } from "zustand";
import { humanizeError } from "@/lib/error-messages";

interface ToastData {
  text: string;
  ok: boolean;
}

interface ToastStoreState {
  toast: ToastData | null;
  showToast: (text: string, ok: boolean) => void;
  dismissToast: () => void;
}

let timer: ReturnType<typeof setTimeout> | null = null;

export const useToastStore = create<ToastStoreState>((set) => ({
  toast: null,

  showToast: (text, ok) => {
    if (timer) clearTimeout(timer);
    const display = ok ? text : humanizeError(text);
    set({ toast: { text: display, ok } });
    timer = setTimeout(() => {
      set({ toast: null });
      timer = null;
    }, 3500);
  },

  dismissToast: () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    set({ toast: null });
  },
}));
