import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { AppShell } from "@/ui/components/Shell";
import { Card, Pill, Stat } from "@/ui/components/Stat";
import { listSubmissionsFn } from "@/infrastructure/fns/list.functions";
import { formatPct, formatMultiplier } from "@/lib/fmt";
import { cn } from "@/lib/cn";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "PolyEval — Dashboard" },
      { name: "description", content: "Recent evaluation runs across tenants and models." },
    ],
  }),
  loader: () => listSubmissionsFn(),
  component: DashboardPage,
});

type Filter = "all" | "scored" | "running" | "queued" | "failed";

function DashboardPage() {
  const initial = Route.useLoaderData();
  const { data: rows = [] } = useQuery({
    queryKey: ["submissions", "list"],
    queryFn: () => listSubmissionsFn(),
    initialData: initial,
    refetchInterval: 1500,
    refetchIntervalInBackground: false,
  });

  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (filter !== "all" && r.status !== filter) return false;
      if (q && !`${r.id} ${r.modelId} ${r.tenantId} ${r.language}`.toLowerCase().includes(q.toLowerCase()))
        return false;
      return true;
    });
  }, [rows, filter, q]);

  const stats = useMemo(() => {
    const total = rows.length;
    const scored = rows.filter((r) => r.status === "scored");
    const active = rows.filter((r) => r.status === "running" || r.status === "queued").length;
    const avgCorrect =
      scored.length === 0
        ? 0
        : scored.reduce((a, b) => a + (b.correctness ?? 0), 0) / scored.length;
    const avgPerf =
      scored.length === 0
        ? 0
        : scored.reduce((a, b) => a + (b.perfNormalized ?? 0), 0) / scored.length;
    return { total, scored: scored.length, active, avgCorrect, avgPerf };
  }, [rows]);

  return (
    <AppShell>
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card title="total runs">
            <Stat label="" value={stats.total.toString()} caption={`${stats.active} active`} />
          </Card>
          <Card title="scored">
            <Stat label="" value={stats.scored.toString()} />
          </Card>
          <Card title="avg correctness">
            <Stat
              label=""
              value={stats.scored ? formatPct(stats.avgCorrect, 1) : "—"}
              tone={stats.avgCorrect >= 0.9 ? "success" : stats.avgCorrect >= 0.7 ? "warn" : "danger"}
            />
          </Card>
          <Card title="avg perf vs rust">
            <Stat
              label=""
              value={stats.scored ? formatMultiplier(stats.avgPerf) : "—"}
              tone={stats.avgPerf <= 1.5 ? "success" : stats.avgPerf <= 4 ? "warn" : "danger"}
              caption="median normalized"
            />
          </Card>
        </div>

        <Card
          title="submissions"
          hint={
            <div className="flex items-center gap-2">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="filter…"
                className="bg-surface-2 border border-border rounded px-2 h-6 text-[11px] font-mono outline-none focus:border-primary w-40"
              />
              {(["all", "scored", "running", "queued", "failed"] as Filter[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={cn(
                    "h-6 px-2 rounded text-[11px] font-mono",
                    f === filter
                      ? "bg-surface-3 text-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-surface-2",
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          }
        >
          {filtered.length === 0 ? (
            <div className="px-4 py-10 text-center text-xs font-mono text-muted-foreground">
              no submissions yet ·{" "}
              <Link to="/" className="text-primary hover:underline">submit one</Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  <tr className="border-b border-border">
                    <Th>id</Th>
                    <Th>tenant</Th>
                    <Th>model</Th>
                    <Th>lang</Th>
                    <Th className="text-right">trials</Th>
                    <Th>status</Th>
                    <Th className="text-right">correctness</Th>
                    <Th className="text-right">reliability</Th>
                    <Th className="text-right">perf</Th>
                    <Th className="text-right">created</Th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r) => (
                    <tr key={r.id} className="border-b border-border/50 hover:bg-surface-2 transition-colors">
                      <Td>
                        <Link to="/s/$id" params={{ id: r.id }} className="text-primary hover:underline">
                          {r.id.slice(0, 8)}
                        </Link>
                      </Td>
                      <Td>{r.tenantId}</Td>
                      <Td>{r.modelId}</Td>
                      <Td>{r.language}</Td>
                      <Td className="text-right tabular-nums">{r.trialsTotal ?? "—"}</Td>
                      <Td>
                        <Pill
                          tone={
                            r.status === "scored"
                              ? "success"
                              : r.status === "failed"
                                ? "danger"
                                : r.status === "running"
                                  ? "info"
                                  : "warn"
                          }
                        >
                          {r.status}
                        </Pill>
                      </Td>
                      <Td className="text-right tabular-nums">
                        {r.correctness == null ? "—" : formatPct(r.correctness, 1)}
                      </Td>
                      <Td className="text-right tabular-nums">
                        {r.reliability == null ? "—" : formatPct(r.reliability, 1)}
                      </Td>
                      <Td className="text-right tabular-nums">
                        {r.perfNormalized == null ? "—" : formatMultiplier(r.perfNormalized)}
                      </Td>
                      <Td className="text-right text-muted-foreground">
                        {relativeTime(new Date(r.createdAt).getTime())}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={cn("text-left font-medium px-3 py-2", className)}>{children}</th>;
}
function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cn("px-3 py-2", className)}>{children}</td>;
}

function relativeTime(ts: number): string {
  const d = Date.now() - ts;
  if (d < 60_000) return `${Math.max(1, Math.floor(d / 1000))}s ago`;
  if (d < 3_600_000) return `${Math.floor(d / 60_000)}m ago`;
  if (d < 86_400_000) return `${Math.floor(d / 3_600_000)}h ago`;
  return `${Math.floor(d / 86_400_000)}d ago`;
}