import { useMemo } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useDraft, useApplySettingsToDraft } from "./store";
import { CodeEditor } from "./CodeEditor";
import { TestSuiteEditor } from "./TestSuiteEditor";
import { Card, Pill, Kbd } from "@/ui/components/Stat";
import { LANGUAGES, type Language } from "@/domain/submission";
import { submissionInputSchema } from "@/domain/schemas";
import { createSubmissionFn } from "@/infrastructure/fns/submissions.functions";
import { cn } from "@/lib/cn";

export function Cockpit() {
  const draft = useDraft();
  const navigate = useNavigate();
  useApplySettingsToDraft();

  const dto = useMemo(
    () => ({
      modelId: draft.modelId,
      language: draft.language,
      prompt: draft.prompt,
      code: draft.code,
      testSuite: draft.testSuite,
      trials: draft.trials,
      timeoutSeconds: draft.timeoutSeconds,
      memoryLimitMb: draft.memoryLimitMb,
    }),
    [draft],
  );

  const validation = useMemo(() => submissionInputSchema.safeParse(dto), [dto]);

  const submit = useMutation({
    mutationFn: async () => {
      const parsed = submissionInputSchema.parse(dto);
      return createSubmissionFn({ data: parsed });
    },
    onSuccess: ({ id }) => {
      navigate({ to: "/s/$id", params: { id } });
    },
  });

  const onSubmit = () => {
    if (!validation.success || submit.isPending) return;
    submit.mutate();
  };

  return (
    <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-px bg-border">
      {/* Left: editor */}
      <div className="bg-background flex flex-col min-h-0">
        <div className="h-9 border-b border-border bg-surface-1 flex items-center px-2 gap-1 shrink-0">
          {LANGUAGES.map((l) => (
            <button
              key={l}
              onClick={() => draft.setLanguage(l)}
              className={cn(
                "h-6 px-2 text-xs font-mono rounded transition-colors",
                l === draft.language
                  ? "bg-surface-3 text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-surface-2",
              )}
            >
              {l}
            </button>
          ))}
          <div className="ml-auto text-[11px] text-muted-foreground font-mono flex items-center gap-2">
            <Kbd>⌘</Kbd>
            <Kbd>↵</Kbd>
            <span>submit</span>
          </div>
        </div>
        <div className="flex-1 min-h-0">
          <CodeEditor
            value={draft.code}
            onChange={(v) => draft.setField("code", v)}
            language={draft.language}
            onSubmit={onSubmit}
          />
        </div>
      </div>

      {/* Right: controls */}
      <aside className="bg-background flex flex-col min-h-0 overflow-y-auto">
        <ControlsPanel />
        <TestSuiteEditor
          value={draft.testSuite}
          onChange={(ts) => draft.setTestSuite(ts)}
        />
        <div className="mt-auto sticky bottom-0 border-t border-border bg-surface-1 px-3 py-3 flex items-center gap-3 shrink-0">
          <ValidationSummary issues={validation.success ? [] : validation.error.issues} />
          <button
            onClick={onSubmit}
            disabled={!validation.success || submit.isPending}
            className={cn(
              "ml-auto h-9 px-4 rounded text-sm font-medium font-mono transition-colors",
              validation.success && !submit.isPending
                ? "bg-primary text-primary-foreground hover:bg-primary-glow"
                : "bg-surface-2 text-muted-foreground cursor-not-allowed",
            )}
          >
            {submit.isPending ? "submitting…" : "evaluate"}
          </button>
        </div>
      </aside>
    </div>
  );
}

function ValidationSummary({ issues }: { issues: { path: (string | number)[]; message: string }[] }) {
  if (issues.length === 0)
    return (
      <div className="text-[11px] font-mono text-muted-foreground">
        <Pill tone="success">ready</Pill>
        <span className="ml-2">all checks passed</span>
      </div>
    );
  return (
    <div
      className="text-[11px] font-mono text-danger truncate"
      title={issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("\n")}
    >
      <Pill tone="danger">{issues.length} issue{issues.length === 1 ? "" : "s"}</Pill>
      <span className="ml-2 text-muted-foreground">
        {issues[0].path.join(".") || "input"}: {issues[0].message}
      </span>
    </div>
  );
}

function ControlsPanel() {
  const d = useDraft();
  return (
    <Card title="run config" className="rounded-none border-0 border-b">
      <div className="grid grid-cols-2 gap-px bg-border">
        <Field label="model" value={d.modelId} onChange={(v) => d.setField("modelId", v)} className="col-span-2" />
        <Field
          label="prompt"
          value={d.prompt}
          onChange={(v) => d.setField("prompt", v)}
          className="col-span-2"
        />
        <NumField label="trials" value={d.trials} min={1} max={50} onChange={(v) => d.setField("trials", v)} />
        <NumField
          label="timeout (s)"
          value={d.timeoutSeconds}
          min={0.5}
          max={30}
          step={0.5}
          onChange={(v) => d.setField("timeoutSeconds", v)}
        />
        <NumField
          label="memory (mb)"
          value={d.memoryLimitMb}
          min={16}
          max={1024}
          step={32}
          onChange={(v) => d.setField("memoryLimitMb", v)}
        />
        <SelectLang value={d.language} onChange={(l) => d.setLanguage(l)} />
      </div>
    </Card>
  );
}

function Field({
  label, value, onChange, className,
}: {
  label: string; value: string; onChange: (v: string) => void; className?: string;
}) {
  return (
    <label className={cn("bg-card flex flex-col gap-1 px-3 py-2", className)}>
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-transparent outline-none text-sm font-mono text-foreground focus:text-primary"
      />
    </label>
  );
}

function NumField({
  label, value, onChange, min, max, step = 1,
}: {
  label: string; value: number; onChange: (v: number) => void; min: number; max: number; step?: number;
}) {
  return (
    <label className="bg-card flex flex-col gap-1 px-3 py-2">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => {
          const n = Number(e.target.value);
          if (Number.isFinite(n)) onChange(n);
        }}
        className="bg-transparent outline-none text-sm font-mono text-foreground tabular-nums focus:text-primary"
      />
    </label>
  );
}

function SelectLang({ value, onChange }: { value: Language; onChange: (l: Language) => void }) {
  return (
    <label className="bg-card flex flex-col gap-1 px-3 py-2">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">language</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as Language)}
        className="bg-transparent outline-none text-sm font-mono text-foreground focus:text-primary"
      >
        {LANGUAGES.map((l) => (
          <option key={l} value={l} className="bg-surface-2">
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}
