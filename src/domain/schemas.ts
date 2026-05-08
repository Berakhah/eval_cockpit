import { z } from "zod";
import { LANGUAGES, LANGUAGE_FRAMEWORK } from "./submission";
import type { Language } from "./submission";

export const languageSchema = z.custom<Language>(
  (v) => typeof v === "string" && (LANGUAGES as readonly string[]).includes(v),
  { message: "invalid language" },
);

export const testFileSchema = z.object({
  name: z.string().min(1).max(128).regex(/^[A-Za-z0-9_./-]+$/, "alphanumeric, . _ / - only"),
  content: z.string().min(1).max(65_536),
});

export const testSuiteSchema = z.object({
  framework: z.string().min(1).max(32),
  files: z.array(testFileSchema).min(1).max(64),
  entrypoint: z.string().min(1).max(128),
}).superRefine((val, ctx) => {
  const names = new Set(val.files.map((f) => f.name));
  if (!names.has(val.entrypoint)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: `entrypoint '${val.entrypoint}' not found in files`,
      path: ["entrypoint"],
    });
  }
});

export const submissionInputSchema = z.object({
  modelId: z.string().trim().min(1).max(256),
  language: languageSchema,
  prompt: z.string().max(16_384).default(""),
  code: z.string().min(1).max(65_536),
  testSuite: testSuiteSchema,
  trials: z.number().int().min(1).max(50),
  timeoutSeconds: z.number().gt(0).max(30),
  memoryLimitMb: z.number().int().min(16).max(1024),
}).superRefine((val, ctx) => {
  const expected = LANGUAGE_FRAMEWORK[val.language as Language];
  if (expected && val.testSuite.framework !== expected) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: `language '${val.language}' requires framework '${expected}', got '${val.testSuite.framework}'`,
      path: ["testSuite", "framework"],
    });
  }
});

export type SubmissionInputDTO = z.infer<typeof submissionInputSchema>;
