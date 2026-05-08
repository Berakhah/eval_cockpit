import { createServerFn } from "@tanstack/react-start";

/**
 * Public-shape config the cockpit needs to know about.
 *
 * IMPORTANT: this is the only data shipped to the browser. The HMAC secret
 * (`POLYEVAL_HMAC_SECRET`) is read by signing helpers that run inside the
 * Worker only — never returned from a server-fn, never embedded in a bundle.
 */
export interface CockpitConfig {
  apiBaseUrl: string;
  tenantId: string;
  hmacKeyId: string;
  environment: "dev" | "prod";
}

const DEFAULTS: CockpitConfig = {
  apiBaseUrl: "http://localhost:8000",
  tenantId: "demo",
  hmacKeyId: "key_local_dev",
  environment: "dev",
};

function readEnv(name: string): string | undefined {
  // Worker runtime exposes bindings via process.env (with nodejs_compat) and
  // also via globalThis. Prefer process.env so Vite's SSR dev server matches.
  if (typeof process !== "undefined" && process.env && process.env[name]) {
    return process.env[name];
  }
  const g = globalThis as Record<string, unknown>;
  const v = g[name];
  return typeof v === "string" ? v : undefined;
}

export const getCockpitConfigFn = createServerFn({ method: "GET" }).handler(
  async (): Promise<CockpitConfig> => {
    const apiBaseUrl = readEnv("POLYEVAL_API_BASE_URL") ?? DEFAULTS.apiBaseUrl;
    const tenantId = readEnv("POLYEVAL_TENANT_ID") ?? DEFAULTS.tenantId;
    const hmacKeyId = readEnv("POLYEVAL_HMAC_KEY_ID") ?? DEFAULTS.hmacKeyId;
    const environment =
      readEnv("POLYEVAL_ENVIRONMENT") === "prod" ? "prod" : "dev";

    return { apiBaseUrl, tenantId, hmacKeyId, environment };
  },
);
