import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/ui/components/Shell";
import { Cockpit } from "@/ui/features/submission/Cockpit";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "PolyEval — Submit Evaluation" },
      {
        name: "description",
        content:
          "Compose, configure, and submit a code evaluation across five languages.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <AppShell>
      <Cockpit />
    </AppShell>
  );
}
