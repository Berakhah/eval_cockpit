import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/ui/components/Shell";
import { Card, Pill } from "@/ui/components/Stat";
import { useSettings, SUPPORTED_LANGUAGES } from "@/ui/features/settings/store";
import type { Language } from "@/domain/submission";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { useQuery } from "@tanstack/react-query";
import {
  getCockpitConfigFn,
  type CockpitConfig,
} from "@/infrastructure/fns/config.functions";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "PolyEval — Settings" },
      { name: "description", content: "Configure runtime, identity, and editor preferences." },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  // Hydration guard for persisted store
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <AppShell>
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 max-w-3xl w-full mx-auto">
        <header className="flex items-baseline justify-between">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Settings</h1>
            <p className="text-xs text-muted-foreground font-mono">
              Persisted to this browser · scoped to current device
            </p>
          </div>
          <ResetButton disabled={!mounted} />
        </header>

        {mounted ? (
          <>
            <IdentitySection />
            <DefaultsSection />
            <RuntimeSection />
            <EditorSection />
          </>
        ) : (
          <div className="text-xs text-muted-foreground font-mono">loading settings…</div>
        )}
      </div>
    </AppShell>
  );
}

function ResetButton({ disabled }: { disabled?: boolean }) {
  const reset = useSettings((s) => s.reset);
  return (
    <button
      onClick={() => {
        if (confirm("Reset all settings to defaults?")) reset();
      }}
      disabled={disabled}
      className="h-7 px-3 rounded text-[11px] font-mono text-muted-foreground hover:text-danger hover:bg-surface-2 disabled:opacity-50"
    >
      reset to defaults
    </button>
  );
}

function IdentitySection() {
  const s = useSettings();
  const { data: config, isLoading, isError } = useQuery<CockpitConfig>({
    queryKey: ["cockpit-config"],
    queryFn: () => getCockpitConfigFn(),
    staleTime: Infinity,
  });

  return (
    <Card
      title="identity & endpoint"
      hint={<Pill tone="info">applied to all submissions</Pill>}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-border">
        <ReadOnlyField
          label="api base url"
          value={config?.apiBaseUrl}
          loading={isLoading}
          error={isError}
          mono
        />
        <ReadOnlyField
          label="tenant id"
          value={config?.tenantId}
          loading={isLoading}
          error={isError}
        />
        <ReadOnlyField
          label="hmac key id"
          value={config?.hmacKeyId}
          loading={isLoading}
          error={isError}
          mono
        />
        <ReadOnlyField
          label="environment"
          value={config?.environment}
          loading={isLoading}
          error={isError}
        />
        <TextField
          label="model id"
          value={s.modelId}
          onChange={(v) => s.set("modelId", v)}
        />
      </div>
      <div className="px-3 py-2 text-[11px] font-mono text-muted-foreground border-t border-border">
        Endpoint, tenant, and HMAC key id come from Worker env vars and cannot
        be edited here. The HMAC <em>secret</em> never leaves the Worker —
        signing happens server-side, referenced by{" "}
        <code className="text-foreground">{config?.hmacKeyId ?? "—"}</code>.
      </div>
    </Card>
  );
}

function DefaultsSection() {
  const s = useSettings();
  return (
    <Card title="submission defaults">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-px bg-border">
        <SelectField
          label="language"
          value={s.defaultLanguage}
          onChange={(v) => s.set("defaultLanguage", v as Language)}
          options={SUPPORTED_LANGUAGES.map((l) => ({ value: l, label: l }))}
        />
        <NumField label="trials" value={s.defaultTrials} min={1} max={50} onChange={(v) => s.set("defaultTrials", v)} />
        <NumField label="timeout (ms)" value={s.defaultTimeoutMs} min={100} max={30000} step={100} onChange={(v) => s.set("defaultTimeoutMs", v)} />
        <NumField label="memory (mb)" value={s.defaultMemoryMb} min={32} max={1024} step={32} onChange={(v) => s.set("defaultMemoryMb", v)} />
      </div>
    </Card>
  );
}

function RuntimeSection() {
  const s = useSettings();
  return (
    <Card title="runtime">
      <div className="grid grid-cols-2 gap-px bg-border">
        <NumField label="poll fast (ms)" value={s.pollFastMs} min={100} max={2000} step={50} onChange={(v) => s.set("pollFastMs", v)} />
        <NumField label="poll slow (ms)" value={s.pollSlowMs} min={250} max={5000} step={50} onChange={(v) => s.set("pollSlowMs", v)} />
        <ToggleField label="show stderr preview in trials" value={s.showStderrPreview} onChange={(v) => s.set("showStderrPreview", v)} />
      </div>
    </Card>
  );
}

function EditorSection() {
  const s = useSettings();
  return (
    <Card title="editor">
      <div className="grid grid-cols-2 gap-px bg-border">
        <NumField label="font size" value={s.editorFontSize} min={10} max={24} onChange={(v) => s.set("editorFontSize", v)} />
        <NumField label="tab size" value={s.editorTabSize} min={2} max={8} onChange={(v) => s.set("editorTabSize", v)} />
      </div>
    </Card>
  );
}

function ReadOnlyField({
  label, value, loading, error, mono,
}: { label: string; value?: string; loading?: boolean; error?: boolean; mono?: boolean }) {
  let display: string;
  let tone = "text-foreground";
  if (loading) { display = "loading…"; tone = "text-muted-foreground"; }
  else if (error) { display = "unreachable"; tone = "text-danger"; }
  else { display = value ?? "—"; }
  return (
    <div className="bg-card flex flex-col gap-1 px-3 py-2">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
        {label} <span className="text-[9px] text-muted-foreground/70">· server</span>
      </span>
      <span className={cn("text-sm select-all", mono ? "font-mono" : "", tone)}>
        {display}
      </span>
    </div>
  );
}

function TextField({
  label, value, onChange, hint, mono,
}: { label: string; value: string; onChange: (v: string) => void; hint?: string; mono?: boolean }) {
  return (
    <label className="bg-card flex flex-col gap-1 px-3 py-2">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "bg-transparent outline-none text-sm text-foreground focus:text-primary",
          mono ? "font-mono" : "",
        )}
      />
      {hint && <span className="text-[10px] text-muted-foreground font-mono">{hint}</span>}
    </label>
  );
}

function NumField({
  label, value, onChange, min, max, step = 1,
}: { label: string; value: number; onChange: (v: number) => void; min: number; max: number; step?: number }) {
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

function SelectField({
  label, value, onChange, options,
}: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <label className="bg-card flex flex-col gap-1 px-3 py-2">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-transparent outline-none text-sm font-mono text-foreground focus:text-primary"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-surface-2">{o.label}</option>
        ))}
      </select>
    </label>
  );
}

function ToggleField({
  label, value, onChange,
}: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="bg-card flex items-center justify-between px-3 py-3 cursor-pointer">
      <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={value}
        onClick={() => onChange(!value)}
        className={cn(
          "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
          value ? "bg-primary" : "bg-surface-3",
        )}
      >
        <span
          className={cn(
            "inline-block h-3.5 w-3.5 rounded-full bg-background transition-transform",
            value ? "translate-x-5" : "translate-x-1",
          )}
        />
      </button>
    </label>
  );
}
