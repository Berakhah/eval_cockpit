import type { Trial } from "@/domain/submission";
import { memo } from "react";
import { formatNs, formatKb } from "@/lib/fmt";

type TrialStatus = "pass" | "fail" | "timeout" | "error";

function trialStatus(t: Trial): TrialStatus {
  if (t.sandbox_violation) return "error";
  if (t.exit_code === 124) return "timeout";
  if (t.framework_passed) return "pass";
  return "fail";
}

const toneFor = (s: TrialStatus) =>
  s === "pass" ? "bg-success" : s === "fail" ? "bg-danger" : s === "timeout" ? "bg-warn" : "bg-info";

export const TrialMatrix = memo(function TrialMatrix({
  trials,
  total,
}: {
  trials: Trial[];
  total: number;
}) {
  const cells: (Trial | null)[] = Array.from({ length: total }, (_, i) => trials[i] ?? null);
  return (
    <div className="px-3 py-3">
      <div className="grid grid-cols-[repeat(auto-fill,minmax(14px,1fr))] gap-1">
        {cells.map((t, i) => {
          const s = t ? trialStatus(t) : null;
          return (
            <div
              key={i}
              title={
                t && s
                  ? `#${t.index + 1} · ${s} · ${formatNs(t.wall_ns)} · ${formatKb(t.mem_kb)} · exit ${t.exit_code}`
                  : `#${i + 1} pending`
              }
              className={
                s
                  ? `aspect-square rounded-sm ${toneFor(s)}`
                  : "aspect-square rounded-sm bg-surface-2 border border-border"
              }
            />
          );
        })}
      </div>
    </div>
  );
});
