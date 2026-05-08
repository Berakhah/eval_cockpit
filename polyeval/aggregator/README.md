# aggregator

Async Python service that reduces raw trial results into final scores.

## Slice 0 status

Stub. Boots, connects to Redis, exposes `/healthz`, `/readyz`, `/metrics` on :8002.
Writes `polyeval:aggregator:heartbeat` every 5s with a 30s TTL.

## Slice 1+ responsibilities (spec §5, §8)

- Consume `polyeval:trial_results` via XREADGROUP
- For each submission with N completed trials, compute:
  - `correctness ∈ [0, 1]` — mean over trials of `framework_passed`
  - `framework_passed_rate` — same, kept distinct from correctness once partial
    credit is added
  - `perf_ratio` — trimmed mean wall_ns / language baseline_ns
  - `ci95` — 10k-resample bootstrap of correctness with seeded RNG
- Persist via the API's submissions table (FK by `submission_id`)
- Sign attestation with Ed25519 (key path from settings, see attestation-format.md)
