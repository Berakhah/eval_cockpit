import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { LANGUAGES, type Language } from "@/domain/submission";

/**
 * User-editable cockpit preferences. Stored in localStorage.
 *
 * Identity fields (apiBaseUrl, hmacKeyId, environment) are NOT here —
 * those come from the Worker via `getCockpitConfigFn` and are read-only
 * on the client (see infrastructure/fns/config.functions.ts).
 *
 * `tenantId` is kept here for now because the submission draft seeds from it.
 * It moves out in Slice 1 once the Worker injects the tenant header itself
 * and the submission UI's tenant field is removed.
 */
export interface SettingsState {
  // Identity (cockpit-side, transitional — see note above)
  tenantId: string;
  modelId: string;

  // Defaults applied to new submissions
  defaultLanguage: Language;
  defaultTrials: number;
  defaultTimeoutMs: number;
  defaultMemoryMb: number;

  // Runtime / cockpit behavior
  pollFastMs: number;
  pollSlowMs: number;
  editorFontSize: number;
  editorTabSize: number;
  showStderrPreview: boolean;

  // mutators
  set: <K extends keyof SettingsState>(k: K, v: SettingsState[K]) => void;
  reset: () => void;
}

const defaults = {
  tenantId: "demo",
  modelId: "claude-sonnet-4.5",

  defaultLanguage: "python" as Language,
  defaultTrials: 10,
  defaultTimeoutMs: 5000,
  defaultMemoryMb: 256,

  pollFastMs: 250,
  pollSlowMs: 500,
  editorFontSize: 13,
  editorTabSize: 2,
  showStderrPreview: true,
};

export const useSettings = create<SettingsState>()(
  persist(
    (set) => ({
      ...defaults,
      set: (k, v) => set({ [k]: v } as never),
      reset: () => set({ ...defaults }),
    }),
    {
      name: "polyeval.settings.v1",
      storage: createJSONStorage(() => {
        if (typeof window === "undefined") {
          return {
            getItem: () => null,
            setItem: () => {},
            removeItem: () => {},
          };
        }
        return window.localStorage;
      }),
    },
  ),
);

export const SUPPORTED_LANGUAGES = LANGUAGES;
