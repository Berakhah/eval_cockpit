import { formatNs, formatMultiplier } from "@/lib/fmt";

export function PerfVsBaseline({
  submissionMedianNs,
  baselineMedianNs,
  multiplier,
}: {
  submissionMedianNs: number;
  baselineMedianNs: number;
  multiplier: number;
}) {
  const max = Math.max(submissionMedianNs, baselineMedianNs);
  const subPct = (submissionMedianNs / max) * 100;
  const basePct = (baselineMedianNs / max) * 100;
  return (
    <div className="px-4 py-4 space_3 flex flex-col gap-3">
      <Row label="rust baseline" pct={basePct} value={formatNs(baselineMedianNs)} tone="bg-success" />
      <Row label="this submission" pct={subPct} value={formatNs(submissionMedianNs)} tone="bg-primary" />
      <div className="text-[11px] font-mono text-muted-foreground mt-1">
        <span className="text-foreground">{formatMultiplier(multiplier)}</span> slower than rust median
      </div>
    </div>
  );
}

function Row({ label, pct, value, tone }: { label: string; pct: number; value: string; tone: string }) {
  return (
    <div className="grid grid-cols-[110px_1fr_70px] items-center gap-3">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">{label}</div>
      <div className="h-2 w-full bg-surface-2 rounded overflow-hidden">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="text-xs font-mono text-foreground tabular-nums text-right">{value}</div>
    </div>
  );
}