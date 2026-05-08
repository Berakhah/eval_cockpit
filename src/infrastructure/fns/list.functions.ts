import { createServerFn } from "@tanstack/react-start";
import { listEvaluations } from "@/infrastructure/api/client";

export const listSubmissionsFn = createServerFn({ method: "GET" }).handler(
  async () => listEvaluations(),
);
