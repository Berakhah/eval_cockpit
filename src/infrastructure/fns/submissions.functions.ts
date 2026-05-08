import { createServerFn } from "@tanstack/react-start";
import { submissionInputSchema } from "@/domain/schemas";
import { submitEvaluation, getEvaluation } from "@/infrastructure/api/client";
import type { Submission } from "@/domain/submission";

export const createSubmissionFn = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => submissionInputSchema.parse(input))
  .handler(async ({ data }) => {
    return submitEvaluation(data);
  });

export const getSubmissionFn = createServerFn({ method: "GET" })
  .inputValidator((input: { id: string }) => {
    if (!input || typeof input.id !== "string" || input.id.length > 64) {
      throw new Error("invalid id");
    }
    return input;
  })
  .handler(async ({ data }): Promise<Submission | null> => {
    return getEvaluation(data.id);
  });
