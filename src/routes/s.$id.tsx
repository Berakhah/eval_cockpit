import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/ui/components/Shell";
import { Card, Pill } from "@/ui/components/Stat";
import { ScoreHeader } from "@/ui/features/result/ScoreHeader";
import { TrialMatrix } from "@/ui/features/result/TrialMatrix";
import { LatencyDistribution } from "@/ui/features/result/LatencyDistribution";
import { PerfVsBaseline } from "@/ui/features/result/PerfVsBaseline";
import { TrialTable } from "@/ui/features/result/TrialTable";
import { getSubmissionFn } from "@/infrastructure/fns/submissions.functions";
import type { Submission, Trial } from "@/domain/submission";
import { useVisibility } from "@/lib/useAdaptivePoll";
import { quantile } from "@/lib/fmt";
import { useMemo } from "react";

export const Route = createFileRoute("/s/$id")({
  head: () => ({ meta: [{ title: "PolyEval — Result" }] }),
  loader: ({ params }) => getSubmissionFn({ data: { id: params.id } }),
  component: ResultPage,
});

function ResultPage() {
  const { id } = Route.useParams();
  const initial = Route.useLoaderData() as Submission | null;
  const visible = useVisibility();

  const { data: sub } = useQuery({
    queryKey: ["submission", id],
    queryFn: () => getSubmissionFn({ data: { id } }),
    initialData: initial ?? undefined,
    refetchInterval: (q) => {
      if (!visible) return false;
      const s = q.state.data?.status;
      if (!s || s === "scored" || s === "failed") return false;
      if (s === "queued") return 250;
      return 500;
    },
    refetchIntervalInBackground: false,
  });

  if (!sub) {
    return (
      <AppShell>
        <div className="p-6 text-sm font-mono text-muted-foreground">
          submission not found.{" "}
          <Link to="/" className="text-primary hover:underline">return to cockpit</Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <Header sub={sub} />
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
        {sub.status !== "scored" ? (
          <RunningView sub={sub} />
        ) : (
          <ScoredView sub={sub} />
        )}
      </div>
    </AppShell>
  );
}

function Header({ sub }: { sub: Submission }) {
  const tone =
    sub.status === "scored"
      ? "success"
      : sub.status === "failed"
        ? "danger"
        : sub.status === "running"
          ? "info"
          : "warn";
  return (
    <div className="border-b border-border bg-surface-1 px-4 h-10 flex items-center gap-3 shrink-0">
      <Link to="/" className="text-xs font-mono text-muted-foreground hover:text-foreground">
        ← cockpit
      </Link>
      <div className="text-xs font-mono text-muted-foreground">submission</div>
      <code className="text-xs font-mono text-foreground">{sub.id}</code>
      <Pill tone={tone}>{sub.status}</Pill>
      {sub.replay && <Pill tone="info">replay · cache hit</Pill>}
      <div className="ml-auto flex items-center gap-2 text-[11px] font-mono text-muted-foreground">
        <span>{sub.language}</span>
        <span>·</span>
        <span>{sub.modelId}</span>
        <span>·</span>
        <span>tenant {sub.tenantId}</span>
      </div>
    </div>
  );
}

function RunningView({ sub }: { sub: Submission }) {
  const total = sub.result?.trials_total ?? 0;
  const completed = sub.result?.raw_trials.length ?? 0;
  const pct = total > 0 ? (completed / total) * 100 : 0;
  return (
    <div className="space-y-4">
      <Card
        title={sub.status === "queued" ? "queued" : "running trials"}
        hint={total > 0 ? `${completed}/${total}` : ""}
      >
        <div className="px-4 py-4 space-y-3">
          <div className="h-1 w-full bg-surface-2 rounded overflow-hidden">
            <div className="h-full bg-primary transition-[width] duration-200" style={{ width: `${pct}%` }} />
          </div>
          <div className="text-[11px] font-mono text-muted-foreground">
            {sub.status === "queued"
              ? "waiting for scheduler claim…"
              : "executing in cgroup-pinned sandbox · cpu=performance · seed locked"}
          </div>
        </div>
      </Card>
      {sub.result && sub.result.raw_trials.length > 0 && (
        <Card title="trial matrix" hint="streaming">
          <TrialMatrix trials={sub.result.raw_trials} total={total} />
        </Card>
      )}
    </div>
  );
}

function ScoredView({ sub }: { sub: Submission }) {
  const result = sub.result!;
  const submissionMedianNs = useMemo(() => {
    const sorted = result.raw_trials.map((t: Trial) => t.wall_ns).sort((a, b) => a - b);
    return quantile(sorted, 0.5);
  }, [result.raw_trials]);

  return (
    <>
      <ScoreHeader result={result} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="latency distribution" hint={`n=${result.raw_trials.length}`}>
          <LatencyDistribution trials={result.raw_trials} />
        </Card>
        {result.perf_normalized != null && (
          <Card title="perf vs rust baseline" hint="median wall">
            <PerfVsBaseline
              submissionMedianNs={submissionMedianNs}
              baselineMedianNs={submissionMedianNs} // placeholder until Slice 2 baseline
              multiplier={result.perf_normalized}
            />
          </Card>
        )}
      </div>

      <Card
        title="trial matrix"
        hint={`${result.trials_passed} / ${result.trials_total} pass`}
      >
        <TrialMatrix trials={result.raw_trials} total={result.trials_total} />
      </Card>

      <Card title="trials" hint="click row for stderr">
        <TrialTable trials={result.raw_trials} />
      </Card>

      <Card title="attestation" hint="ed25519">
        <div className="px-4 py-3 text-xs font-mono text-muted-foreground break-all">
          pubkey_id{" "}
          <span className="text-foreground">{result.attestation_pubkey_id}</span>
          <span className="ml-4">
            scored {new Date(result.scored_at).toLocaleString()}
          </span>
        </div>
      </Card>
    </>
  );
}
