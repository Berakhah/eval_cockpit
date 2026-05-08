import { useMemo, useState } from "react";
import type { Trial } from "@/domain/submission";
import { formatNs, formatKb } from "@/lib/fmt";
import { Pill } from "@/ui/components/Stat";
import { cn } from "@/lib/cn";

type TrialStatus = "pass" | "fail" | "timeout" | "error";
type SortKey = "index" | "wall_ns" | "mem_kb" | "exit_code";

function trialStatus(t: Trial): TrialStatus {
  if (t.sandbox_violation) return "error";
  if (t.exit_code === 124) return "timeout";
  if (t.framework_passed) return "pass";
  return "fail";
}

const tone = (s: TrialStatus): "success" | "danger" | "warn" | "info" =>
  s === "pass" ? "success" : s === "fail" ? "danger" : s === "timeout" ? "warn" : "info";

export function TrialTable({ trials }: { trials: Trial[] }) {
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: "index",
    dir: "asc",
  });

  const sorted = useMemo(() => {
    const arr = [...trials];
    arr.sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (av === bv) return 0;
      const cmp = av > bv ? 1 : -1;
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [trials, sort]);

  const onSort = (k: SortKey) =>
    setSort((s) => (s.key === k ? { key: k, dir: s.dir === "asc" ? "desc" : "asc" } : { key: k, dir: "asc" }));

  return (
    <div className="text-xs font-mono">
      <div className="grid grid-cols-[48px_90px_1fr_1fr_60px_2fr] px-3 h-7 items-center bg-surface-2 border-b border-border text-[10px] uppercase tracking-wider text-muted-foreground">
        <SortHead k="index" sort={sort} onSort={onSort}>#</SortHead>
        <div>status</div>
        <SortHead k="wall_ns" sort={sort} onSort={onSort}>wall</SortHead>
        <SortHead k="mem_kb" sort={sort} onSort={onSort}>mem</SortHead>
        <SortHead k="exit_code" sort={sort} onSort={onSort}>exit</SortHead>
        <div>stderr</div>
      </div>
      <div className="max-h-[360px] overflow-y-auto divide-y divide-border">
        {sorted.map((t) => (
          <Row key={t.index} t={t} />
        ))}
      </div>
    </div>
  );
}

function SortHead({
  k, sort, onSort, children,
}: {
  k: SortKey;
  sort: { key: SortKey; dir: "asc" | "desc" };
  onSort: (k: SortKey) => void;
  children: React.ReactNode;
}) {
  const active = sort.key === k;
  return (
    <button onClick={() => onSort(k)} className={cn("text-left hover:text-foreground", active && "text-foreground")}>
      {children}{active ? (sort.dir === "asc" ? " ↑" : " ↓") : ""}
    </button>
  );
}

function Row({ t }: { t: Trial }) {
  const [open, setOpen] = useState(false);
  const s = trialStatus(t);
  const stderr = t.stderr_snippet ?? "";
  return (
    <div
      className="grid grid-cols-[48px_90px_1fr_1fr_60px_2fr] px-3 py-1.5 items-start hover:bg-surface-2 cursor-default"
      onClick={() => stderr && setOpen((o) => !o)}
    >
      <div className="tabular-nums text-muted-foreground">{t.index + 1}</div>
      <div><Pill tone={tone(s)}>{s}</Pill></div>
      <div className="tabular-nums">{formatNs(t.wall_ns)}</div>
      <div className="tabular-nums">{formatKb(t.mem_kb)}</div>
      <div className="tabular-nums text-muted-foreground">{t.exit_code}</div>
      <div className="text-muted-foreground break-all">
        {stderr
          ? (open ? stderr : stderr.slice(0, 80) + (stderr.length > 80 ? "…" : ""))
          : "—"}
      </div>
    </div>
  );
}
