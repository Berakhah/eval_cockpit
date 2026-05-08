import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Trial } from "@/domain/submission";
import { formatNs, quantile } from "@/lib/fmt";

export function LatencyDistribution({ trials }: { trials: Trial[] }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const { bins, p50, p95, p99 } = useMemo(() => {
    const samples = trials.map((t) => t.wall_ns).sort((a, b) => a - b);
    if (samples.length === 0)
      return { bins: [] as { x: number; n: number; label: string }[], p50: 0, p95: 0, p99: 0 };
    const min = samples[0];
    const max = samples[samples.length - 1];
    const binCount = Math.min(24, Math.max(8, Math.ceil(Math.sqrt(samples.length))));
    const w = Math.max(1, (max - min) / binCount);
    const counts = new Array(binCount).fill(0);
    for (const s of samples) {
      const idx = Math.min(binCount - 1, Math.floor((s - min) / w));
      counts[idx]++;
    }
    const out = counts.map((n, i) => {
      const x = min + i * w;
      return { x, n, label: formatNs(x) };
    });
    return {
      bins: out,
      p50: quantile(samples, 0.5),
      p95: quantile(samples, 0.95),
      p99: quantile(samples, 0.99),
    };
  }, [trials]);

  if (bins.length === 0) {
    return <div className="px-4 py-6 text-xs font-mono text-muted-foreground">no samples</div>;
  }

  if (!mounted) {
    return <div className="px-4 py-6 h-56 text-xs font-mono text-muted-foreground">rendering chart…</div>;
  }

  return (
    <div className="px-2 pt-2 pb-3 h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={bins} margin={{ top: 8, right: 12, left: 4, bottom: 16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--muted-foreground)", fontSize: 10, fontFamily: "var(--font-mono)" }}
            stroke="var(--border)"
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: "var(--muted-foreground)", fontSize: 10, fontFamily: "var(--font-mono)" }}
            stroke="var(--border)"
            allowDecimals={false}
            width={28}
          />
          <Tooltip
            cursor={{ fill: "var(--surface-2)" }}
            contentStyle={{
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              borderRadius: 4,
              fontSize: 11,
              fontFamily: "var(--font-mono)",
            }}
            formatter={(v: number) => [String(v), "trials"]}
            labelFormatter={(l) => `latency ≥ ${l}`}
          />
          <Bar dataKey="n" fill="var(--primary)" radius={[2, 2, 0, 0]} />
          {[
            { v: p50, label: "p50", color: "var(--info)" },
            { v: p95, label: "p95", color: "var(--warn)" },
            { v: p99, label: "p99", color: "var(--danger)" },
          ].map((m) => {
            const i = bins.findIndex((b, idx) => b.x <= m.v && (bins[idx + 1]?.x ?? Infinity) > m.v);
            const lbl = bins[Math.max(0, i)]?.label;
            return (
              <ReferenceLine
                key={m.label}
                x={lbl}
                stroke={m.color}
                strokeDasharray="3 3"
                label={{ value: m.label, fill: m.color, fontSize: 10, position: "top" }}
              />
            );
          })}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}