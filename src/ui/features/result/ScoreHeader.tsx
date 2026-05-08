import type { ScoredResult } from "@/domain/submission";
import { Card, Stat, Pill } from "@/ui/components/Stat";
import { formatPct, formatCi, formatMultiplier } from "@/lib/fmt";

function perfTone(x: number): "success" | "warn" | "danger" | "default" {
  if (x <= 1.5) return "success";
  if (x <= 4) return "warn";
  return "danger";
}

function corrTone(x: number): "success" | "warn" | "danger" {
  if (x >= 0.9) return "success";
  if (x >= 0.7) return "warn";
  return "danger";
}

export function ScoreHeader({ result }: { result: ScoredResult }) {
  const ci = result.correctness_ci;
  const perfNorm = result.perf_normalized;
  const perfCi = result.perf_ci;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <Card title="correctness" hint="bootstrap 95% ci">
        <Stat
          label=""
          value={formatPct(result.correctness, 1)}
          caption={`ci ${formatCi(ci.lo, ci.hi, 2)}`}
          tone={corrTone(result.correctness)}
        />
        <CIBar lo={ci.lo} hi={ci.hi} mid={result.correctness} />
      </Card>

      <Card title="reliability" hint={result.flaky ? "flaky" : "stable"}>
        <Stat
          label=""
          value={formatPct(result.reliability, 1)}
          caption={result.flaky ? "flaky detected" : "stable"}
          tone={result.reliability >= 0.9 ? "success" : result.reliability >= 0.75 ? "warn" : "danger"}
        />
        <div className="px-4 pb-3">
          <div className="h-1 w-full bg-surface-2 rounded overflow-hidden">
            <div
              className="h-full bg-info"
              style={{ width: `${Math.min(100, Math.max(0, result.reliability * 100))}%` }}
            />
          </div>
        </div>
      </Card>

      <Card title="perf vs rust" hint="median normalized">
        {perfNorm != null ? (
          <>
            <Stat
              label=""
              value={formatMultiplier(perfNorm)}
              caption={
                <>
                  {perfCi ? `ci ${formatCi(perfCi.lo, perfCi.hi, 2)} · ` : ""}lower is faster
                </>
              }
              tone={perfTone(perfNorm)}
            />
            <div className="px-4 pb-3 flex items-center gap-2">
              <Pill tone={perfTone(perfNorm)}>
                {perfNorm <= 1.5 ? "near-baseline" : perfNorm <= 4 ? "moderate" : "slow"}
              </Pill>
            </div>
          </>
        ) : (
          <div className="px-4 py-3 text-xs font-mono text-muted-foreground">
            baseline not yet available (Slice 2)
          </div>
        )}
      </Card>
    </div>
  );
}

function CIBar({ lo, hi, mid }: { lo: number; hi: number; mid: number }) {
  const clamp = (x: number) => Math.max(0, Math.min(1, x));
  const a = clamp(lo);
  const b = clamp(hi);
  const m = clamp(mid);
  return (
    <div className="px-4 pb-3">
      <div className="relative h-1.5 w-full bg-surface-2 rounded overflow-hidden">
        <div
          className="absolute top-0 bottom-0 bg-primary/40"
          style={{ left: `${a * 100}%`, width: `${(b - a) * 100}%` }}
        />
        <div
          className="absolute top-[-3px] bottom-[-3px] w-px bg-primary"
          style={{ left: `${m * 100}%` }}
        />
      </div>
      <div className="flex justify-between text-[10px] font-mono text-muted-foreground mt-1 tabular-nums">
        <span>0.0</span>
        <span>0.5</span>
        <span>1.0</span>
      </div>
    </div>
  );
}
