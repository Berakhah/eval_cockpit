# Eval Cockpit (PolyEval)

**Secure, deterministic evaluation of LLM‑generated code — with a real‑time cockpit UI and cryptographic attestations.**

Eval Cockpit is a monorepo for **PolyEval**, a multi‑language code evaluation harness. It ships two deployable products:

| Subtree | Technology | Deploy target |
| --- | --- | --- |
| `src/` | TanStack Start + React + Vite | Cloudflare Workers (cockpit UI) |
| `polyeval/` | FastAPI + Rust + Python + Docker | WSL2 / Fly.io (backend) |

---

## Why it stands out

- **Sandbox‑first security**: gVisor (`runsc`) + seccomp‑bpf + cgroupv2 + read‑only rootfs + no‑network isolation.
- **Deterministic performance**: external wall‑clock measurement, RNG seeding, warmup discard, trimmed‑mean reduction.
- **Verifiable results**: Ed25519‑signed JSON attestations using canonical JSON.
- **Contract‑driven API**: OpenAPI generated from Pydantic → TypeScript codegen for the cockpit.
- **Multi‑language by design**: runners for Python, JavaScript, Java, C++, Rust.

---

## Architecture at a glance

```
Browser
  └─→ TanStack server‑fn (Cloudflare Worker)
        └─→ HMAC‑signs requests (WebCrypto)
              └─→ FastAPI gateway
                    ├─→ HMAC verify + nonce check (Redis)
                    ├─→ cache lookup (content‑addressed)
                    ├─→ Postgres INSERT + Redis XADD eval:queue
                    └─→ Rust scheduler (Redis Streams)
                          └─→ gVisor sandboxed runner
                                └─→ Python aggregator
                                      ├─→ scoring + bootstrap CI
                                      └─→ Ed25519 attestation
```

---

## Core guarantees

### Security model
- Submissions are treated as **fully adversarial**.
- Defense‑in‑depth: gVisor, seccomp‑bpf, cgroupv2 limits, no network, non‑root, read‑only rootfs.
- HMAC authentication with **timestamp + nonce replay protection** on every API call.

See: `polyeval/docs/sandbox-threat-model.md`.

### Determinism contract
- Wall time measured **outside** the sandbox (`CLOCK_MONOTONIC`) to prevent tampering.
- RNG seeded per trial; warmup discard + trimmed‑mean for stable perf metrics.

See: `polyeval/docs/determinism.md`.

### OpenAPI as the single contract
Pydantic → `openapi.json` → TypeScript types. The cockpit never hand‑edits generated types.

---

## Scoring + attestation

- **correctness** = `trials_passed / trials_scored`
- **reliability** = `1 - (stddev / mean)` of wall times
- **perf_normalized** = `median(trimmed_wall) / baseline.median_wall_time_ns`
- **CI95** via 10k‑resample bootstrap with seeded RNG

Attestations are **Ed25519‑signed** canonical JSON (RFC 8785).

See: `polyeval/docs/attestation-format.md`.

---

## API surface

- `POST /v1/submissions` — submit code for evaluation  
- `GET /v1/submissions/{id}` — poll status + results  
- `GET /v1/submissions/{id}/attestation` — download attestation  
- `GET /v1/baselines/{test_suite_hash}` — inspect Rust baseline  
- `POST /v1/baselines/refresh` — admin baseline refresh  
- `GET /healthz`, `/readyz`, `/metrics`

---

## Repository layout

```
src/            # Cockpit UI (TanStack Start + React)
polyeval/api/   # FastAPI gateway + OpenAPI schema
polyeval/scheduler/  # Rust scheduler (Redis Streams + gVisor dispatch)
polyeval/aggregator/ # Python aggregator (scoring + attestation)
polyeval/runners/    # Language runners (Dockerfiles)
polyeval/docs/       # Threat model, determinism, attestation format
```

---

## Local development

### Cockpit UI (repo root)
```sh
bun dev              # start dev server
bun build            # production build (runs codegen first via prebuild)
bun run codegen      # regenerate src/infrastructure/api/generated.ts
bun lint             # eslint
```

### Backend (from repo root)
```sh
make -C polyeval dev           # boot full local stack + tail api logs
make -C polyeval up            # boot detached
make -C polyeval down          # stop (keep volumes)
make -C polyeval clean         # stop + wipe volumes (DESTRUCTIVE)
make -C polyeval openapi       # regenerate polyeval/api/openapi.json
make -C polyeval test          # run api unit tests inside container
```

---

## Codegen pipeline (API → UI)

```
polyeval/api (Pydantic)
  └─ python -m polyeval_api.openapi > openapi.json
          └─ openapi-typescript openapi.json -o src/infrastructure/api/generated.ts
```

Run `bun run codegen` to refresh, or `bun run codegen:check` to enforce drift in CI.

---

## Configuration

### Cloudflare Worker (`wrangler.jsonc` + secrets)
| Variable | Purpose |
| --- | --- |
| `POLYEVAL_API_BASE_URL` | Backend URL |
| `POLYEVAL_HMAC_SECRET` | Worker secret (never in code or browser) |
| `POLYEVAL_TENANT_ID` | Fixed tenant ID |

Copy `.dev.vars.example` → `.dev.vars` for local development.

### Backend (`POLYEVAL_*` env prefix)
| Variable | Default | Notes |
| --- | --- | --- |
| `POLYEVAL_DB_URL` | postgres://… | Async Postgres URL |
| `POLYEVAL_REDIS_URL` | redis://redis:6379/0 | |
| `POLYEVAL_HMAC_SECRET` | — | Same secret as Worker |
| `POLYEVAL_ED25519_PRIVKEY_PATH` | `/run/secrets/eval-signer.key` | Attestation signing key |
| `POLYEVAL_OTEL_ENDPOINT` | `http://otel-collector:4317` | OTLP gRPC |
| `POLYEVAL_ENVIRONMENT` | `dev` | `dev/test/staging/prod` |

---

## Status / roadmap

Development is staged in **slices**. Current repo content includes **Slice 0** scaffolding for the API, scheduler, and aggregator. Later slices add full end‑to‑end evaluation, baselines, and production hardening.

---

## Key docs

- **Spec (source of truth):** `polyeval-spec.pdf`
- **Threat model:** `polyeval/docs/sandbox-threat-model.md`
- **Determinism:** `polyeval/docs/determinism.md`
- **Attestations:** `polyeval/docs/attestation-format.md`
