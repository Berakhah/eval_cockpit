import Editor from "@monaco-editor/react";
import type { Language } from "@/domain/submission";

const monacoLang: Record<Language, string> = {
  python: "python",
  javascript: "javascript",
  java: "java",
  cpp: "cpp",
  rust: "rust",
};

export function CodeEditor({
  value,
  onChange,
  language,
  onSubmit,
}: {
  value: string;
  onChange: (v: string) => void;
  language: Language;
  onSubmit: () => void;
}) {
  return (
    <Editor
      value={value}
      language={monacoLang[language]}
      theme="vs-dark"
      onChange={(v) => onChange(v ?? "")}
      onMount={(editor, monaco) => {
        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
          onSubmit();
        });
      }}
      options={{
        minimap: { enabled: false },
        fontFamily: "JetBrains Mono, ui-monospace, monospace",
        fontSize: 13,
        lineNumbers: "on",
        renderLineHighlight: "line",
        scrollBeyondLastLine: false,
        smoothScrolling: false,
        cursorBlinking: "solid",
        automaticLayout: true,
        padding: { top: 12, bottom: 12 },
        tabSize: 2,
      }}
      loading={
        <div className="h-full w-full flex items-center justify-center text-xs text-muted-foreground font-mono">
          loading editor…
        </div>
      }
    />
  );
}