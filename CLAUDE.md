# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What this repo is

A **monorepo** for PolyEval — a multi-language LLM code evaluation harness. Two independently deployable products share the same git history:

| Subtree | Technology | Deploy target |
|---|---|---|
| `src/` | TanStack Start + React + Vite | Cloudflare Workers (cockpit UI) |
| `polyeval/` | FastAPI + Rust + Python + Docker | WSL2 / Fly.io (backend) |

**`polyeval-spec.pdf`** (repo root) is the absolute source of truth for all protocol decisions. Read it before touching API contracts, scoring formulas, HMAC auth, or attestation formats.

---

## Commands

### Cockpit UI (run from Windows host, repo root)

```sh
bun dev              # start dev server
bun build            # production build (runs codegen first via prebuild)
bun run codegen      # regenerate src/infrastructure/api/generated.ts from polyeval/api/openapi.json
bun lint             # eslint
```

`bun run codegen` must be re-run whenever `polyeval/api/openapi.json` changes. CI fails the build if the generated file is out of sync (`git diff --quiet src/infrastructure/api/generated.ts`).

### Backend (run from inside WSL2, repo root)

```sh
make -C polyeval dev           # boot full local stack + tail api logs
make -C polyeval up            # boot detached
make -C polyeval down          # stop (keep volumes)
make -C polyeval clean         # stop + wipe volumes (DESTRUCTIVE)
make -C polyeval openapi       # regenerate polyeval/api/openapi.json from the FastAPI app
make -C polyeval test          # run api unit tests inside container
make -C polyeval seed-baselines  # (Slice 2+) pre-compute Rust baselines
```

### API unit tests (Python, inside api container or local venv)

```sh
# from polyeval/api/
pytest -q                    # all tests
pytest -q tests/test_health.py   # one file
pytest -k "test_healthz"     # one test
pytest --cov=polyeval_api    # coverage
```

### Rust scheduler (from polyeval/scheduler/)

```sh
cargo build
cargo test
cargo clippy -- -D warnings
cargo fmt --check
```

### Linters / type checkers

```sh
ruff check polyeval/api/src       # Python lint
mypy --strict polyeval/api/src    # Python types
tsc --noEmit                      # TS types (from root)
eslint .                          # TS/TSX lint (from root)
```

---

## Architecture

### Data flow

```
Browser
  └─→ TanStack server-fn (Cloudflare Worker)
        └─→ signs with POLYEVAL_HMAC_SECRET via WebCrypto
              └─→ FastAPI gateway (polyeval/api/)
                    ├─→ HMAC verify + nonce check (Redis)
                    ├─→ cache lookup (Redis, content-addressed)
                    ├─→ Postgres INSERT + Redis XADD eval:queue
                    └─→ Rust scheduler (polyeval/scheduler/)
                          └─→ docker run --runtime=runsc (gVisor)
                                └─→ language runner (polyeval/runners/<lang>/)
                                      └─→ Python aggregator (polyeval/aggregator/)
                                            ├─→ scoring (correctness, reliability, perf)
                                            ├─→ bootstrap CI (NumPy, 10k resamples)
                                            └─→ Ed25519 attestation → Postgres UPDATE
```

### Key invariants

- **HMAC secret never reaches the browser.** `POLYEVAL_HMAC_SECRET` is a Cloudflare Worker secret; all signing happens server-side in `src/infrastructure/api/sign.ts` (WebCrypto). The browser calls TanStack server-fns only.
- **OpenAPI is the single contract.** Pydantic models in `polyeval/api/src/polyeval_api/schemas/` → `polyeval/api/openapi.json` (via `make openapi`) → `src/infrastructure/api/generated.ts` (via `bun run codegen`). Never hand-edit `generated.ts`.
- **Aggregator owns all scoring.** Runners emit raw `{wall_ns, mem_kb, exit, framework_passed, sandbox_violation}`; aggregator produces scores. No score computation elsewhere.
- **Sandbox from day 1.** All runners use `--runtime=runsc` (gVisor) + cgroupv2 + seccomp + `--cap-drop=ALL` + `--read-only`. No "dev bypass" mode.
- **Determinism is a contract (spec §7.3).** Wallclock measured outside the sandbox (`clock_gettime(CLOCK_MONOTONIC)` around `clone3`/`wait4`); LD_PRELOAD shim seeds RNG from `determinism_seed`; 2-of-N warmup trials dropped; trimmed mean (drop top/bottom 10%) for perf.
- **Single-tenant cockpit.** `POLYEVAL_TENANT_ID` env var on the Worker; `X-Polyeval-Tenant` injected automatically. Tenant is not user-editable.

### Cockpit source layout (`src/`)

```
src/
├── domain/               # shared types: Language, Status, Submission, ScoredResult…
├── infrastructure/
│   ├── api/              # generated.ts (auto), client.ts, sign.ts, errors.ts, ledger.ts
│   └── server/           # TanStack createServerFn wrappers (Worker-side only)
├── ui/
│   ├── components/       # Shell.tsx (nav shell), Stat.tsx (Card/Pill/Stat)
│   └── features/
│       ├── submission/   # Cockpit.tsx, CodeEditor.tsx, TestSuiteEditor.tsx, store.ts
│       ├── result/       # ScoreHeader, TrialMatrix, LatencyDistribution, PerfVsBaseline, TrialTable, AttestationViewer
│       └── settings/     # store.ts (Zustand, persisted to localStorage)
├── routes/               # TanStack file-routes: __root, index, dashboard, s.$id, settings
├── lib/                  # useAdaptivePoll.ts, fmt.ts, cn.ts, utils.ts
└── router.tsx            # QueryClient + router factory
```

Routes use TanStack router's `loader` for initial SSR data then React Query for live polling. The `s.$id` route polls at 250 ms (queued) → 500 ms (running) → stops on terminal status.

### Backend source layout (`polyeval/`)

```
polyeval/
├── api/src/polyeval_api/
│   ├── main.py           # FastAPI app factory + lifespan
│   ├── settings.py       # Pydantic Settings, POLYEVAL_* env prefix
│   ├── telemetry.py      # structlog JSON + OTLP gRPC tracer
│   ├── routes/           # health.py (done); submissions.py, baselines.py (Slice 1/2)
│   ├── schemas/          # health.py (done); submission.py, result.py… (Slice 1)
│   ├── auth/             # HMAC middleware (Slice 1)
│   ├── db/               # SQLAlchemy async (Slice 1)
│   └── cache/            # Redis content-addressed cache (Slice 1)
├── scheduler/src/        # Rust: consumer.rs, runner_pool.rs, cgroup.rs
├── runners/              # base/, python/, javascript/, java/, cpp/, rust/ Dockerfiles
├── aggregator/src/polyeval_agg/   # score/, stats/, attestation/, pipeline.py
└── infra/                # docker-compose.yml, prometheus, otel, grafana, loki, tempo
```

### Submission status lifecycle

`queued` → `running` → `scored` | `failed`

Postgres `version` column (1→2→3) is the optimistic-lock claim: scheduler claims by `UPDATE WHERE version=1`, aggregator completes at version=3.

### API auth (spec §12.1)

Every request to the backend carries:
- `X-Polyeval-Signature: hmac-sha256:<hex>` — HMAC-SHA-256 over the raw body
- `X-Polyeval-Timestamp` — epoch seconds; rejected if `|now - ts| > 300 s`
- `X-Polyeval-Nonce` — random UUID; stored in Redis 600 s for replay protection
- `X-Polyeval-Tenant` — fixed tenant ID from Worker env

### Cache key structure (spec §5.2)

```
poly:cache:v1:{tenant_id}:{model_id}:{lang}:sha256(prompt || test_suite || runner_image_digest)
```

Bumping a runner image digest automatically invalidates affected cache entries.

### Scoring formulas (spec §8)

- **correctness** = `trials_passed / trials_scored`
- **correctness CI** = Wilson score interval, 95%
- **reliability** = `1 - (stddev / mean)` of wall times; `flaky=true` when < 0.95
- **perf_normalized** = `median(trimmed_wall) / baseline.median_wall_time_ns` (Rust baseline)
- All CIs: bootstrap, `np.random.default_rng(seed)`, 10k resamples, percentile method

---

## Environment variables

### Cloudflare Worker (`wrangler.jsonc` + Cloudflare secrets)

| Variable | Purpose |
|---|---|
| `POLYEVAL_API_BASE_URL` | Backend URL (e.g. `https://api.polyeval.example.com`) |
| `POLYEVAL_HMAC_SECRET` | Signing secret — **Worker secret, never in code/browser** |
| `POLYEVAL_TENANT_ID` | Fixed tenant for this cockpit deployment |

Copy `.dev.vars.example` to `.dev.vars` for local Worker dev.

### Backend (`POLYEVAL_*` env prefix, see `polyeval/api/src/polyeval_api/settings.py`)

| Variable | Default | Notes |
|---|---|---|
| `POLYEVAL_DB_URL` | postgres://… | Async Postgres URL |
| `POLYEVAL_REDIS_URL` | redis://redis:6379/0 | |
| `POLYEVAL_HMAC_SECRET` | — | Same secret as Worker |
| `POLYEVAL_ED25519_PRIVKEY_PATH` | `/run/secrets/eval-signer.key` | Attestation signing key |
| `POLYEVAL_OTEL_ENDPOINT` | `http://otel-collector:4317` | OTLP gRPC |
| `POLYEVAL_ENVIRONMENT` | `dev` | `dev/test/staging/prod` |

---

## Build slices (current state)

Work proceeds as gated vertical slices — each slice must be CI-green before the next starts:

- **Slice 0** — Monorepo bootstrap + codegen pipeline *(~30% done; `polyeval/api/` + Makefile exist)*
- **Slice 1** — Python end-to-end: POST/GET submissions, Postgres, Redis queue, Rust scheduler, Python runner under gVisor, aggregator scoring, Ed25519 attestation, cockpit rewired to real API *(mock store deleted here)*
- **Slice 2** — Rust baselines + `perf_normalized`
- **Slice 3** — JavaScript runner
- **Slice 4** — Java, C++, Rust runners
- **Slice 5** — Determinism replay, adversarial corpus, Postgres RLS, security scans
- **Slice 6** — OTEL spans, Prometheus metrics, 5 Grafana dashboards
- **Slice 7** — `polyeval verify` CLI, Locust load tests, Toxiproxy chaos, Fly.io deploy

Acceptance target for Slice 1: spec §13.2 — submit Python `add(a,b)` → `correctness=1.0`, replay returns `replay:true`, attestation JSON passes Ed25519 verification.
