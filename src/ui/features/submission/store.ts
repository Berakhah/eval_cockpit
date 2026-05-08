import { create } from "zustand";
import type { Language, TestSuite } from "@/domain/submission";
import { LANGUAGE_FRAMEWORK } from "@/domain/submission";
import { useSettings } from "@/ui/features/settings/store";
import { useEffect } from "react";

interface SubmissionDraft {
  modelId: string;
  language: Language;
  prompt: string;
  code: string;
  testSuite: TestSuite;
  trials: number;
  timeoutSeconds: number;
  memoryLimitMb: number;
  setLanguage: (l: Language) => void;
  setField: <K extends Exclude<keyof SubmissionDraft, keyof SubmissionDraftActions>>(
    k: K,
    v: SubmissionDraft[K],
  ) => void;
  setTestSuite: (ts: TestSuite) => void;
}

type SubmissionDraftActions = {
  setLanguage: SubmissionDraft["setLanguage"];
  setField: SubmissionDraft["setField"];
  setTestSuite: SubmissionDraft["setTestSuite"];
};

const STARTER_CODE: Record<Language, string> = {
  python: `def add(a, b):\n    return a + b\n`,
  javascript: `function add(a, b) {\n  return a + b;\n}\nmodule.exports = { add };\n`,
  java: `class Solution {\n  static int add(int a, int b) { return a + b; }\n}\n`,
  cpp: `int add(int a, int b) { return a + b; }\n`,
  rust: `pub fn add(a: i64, b: i64) -> i64 { a + b }\n`,
};

function defaultTestSuite(language: Language): TestSuite {
  const framework = LANGUAGE_FRAMEWORK[language];
  switch (language) {
    case "python":
      return {
        framework,
        files: [
          {
            name: "test_add.py",
            content: `from solution import add\n\ndef test_basic():\n    assert add(1, 2) == 3\n    assert add(0, 0) == 0\n    assert add(-1, 1) == 0\n`,
          },
        ],
        entrypoint: "test_add.py",
      };
    case "javascript":
      return {
        framework,
        files: [
          {
            name: "add.test.js",
            content: `const { add } = require('./solution');\ntest('add', () => {\n  expect(add(1, 2)).toBe(3);\n  expect(add(0, 0)).toBe(0);\n});\n`,
          },
        ],
        entrypoint: "add.test.js",
      };
    default:
      return {
        framework,
        files: [
          {
            name: `test_${language}.txt`,
            content: `# Add test file for ${language}\n`,
          },
        ],
        entrypoint: `test_${language}.txt`,
      };
  }
}

export const useDraft = create<SubmissionDraft>((set) => ({
  modelId: "claude-sonnet-4.5",
  language: "python",
  prompt: "Write a function add(a, b) that returns a + b.",
  code: STARTER_CODE.python,
  testSuite: defaultTestSuite("python"),
  trials: 10,
  timeoutSeconds: 5,
  memoryLimitMb: 256,
  setLanguage: (l) =>
    set((s) => ({
      language: l,
      code: s.code === STARTER_CODE[s.language] ? STARTER_CODE[l] : s.code,
      testSuite: s.testSuite.framework === LANGUAGE_FRAMEWORK[s.language]
        ? defaultTestSuite(l)
        : s.testSuite,
    })),
  setField: (k, v) => set({ [k]: v } as never),
  setTestSuite: (ts) => set({ testSuite: ts }),
}));

export function useApplySettingsToDraft() {
  const settings = useSettings();
  useEffect(() => {
    const d = useDraft.getState();
    const patch: Partial<SubmissionDraft> = {};
    if (d.modelId === "claude-sonnet-4.5" && settings.modelId) patch.modelId = settings.modelId;
    if (d.trials === 10) patch.trials = settings.defaultTrials;
    if (d.timeoutSeconds === 5) patch.timeoutSeconds = settings.defaultTimeoutMs / 1000;
    if (d.memoryLimitMb === 256) patch.memoryLimitMb = settings.defaultMemoryMb;
    if (d.language === "python" && d.code === STARTER_CODE.python) {
      patch.language = settings.defaultLanguage;
      patch.code = STARTER_CODE[settings.defaultLanguage];
      patch.testSuite = defaultTestSuite(settings.defaultLanguage);
    }
    if (Object.keys(patch).length > 0) useDraft.setState(patch);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    settings.modelId,
    settings.defaultTrials,
    settings.defaultTimeoutMs,
    settings.defaultMemoryMb,
    settings.defaultLanguage,
  ]);
}
