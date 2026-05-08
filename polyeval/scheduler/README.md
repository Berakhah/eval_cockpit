# scheduler

PolyEval trial scheduler. Rust 1.83, tokio, axum, redis-rs.

## What it owns (per spec §5)

- Reads from Redis Stream `polyeval:trials`
- Claims a runner from a per-language gVisor pool
- Pins cgroup limits (`memory.max`, `pids.max`, `cpu.weight`, cpuset)
- Measures wall time externally (`clock_gettime(CLOCK_MONOTONIC)`)
- Writes a raw `TrialResult{wall_ns, mem_kb, exit, sandbox_violation}` back to
  Redis Stream `polyeval:trial_results`

## Slice 0 status

Stub. Boots, connects to Redis, exposes:

- `GET /healthz` — liveness
- `GET /readyz`  — Redis ping
- `GET /metrics` — prometheus

A 5-second heartbeat writes `polyeval:scheduler:heartbeat = unix_ts` (TTL 30s).
`/readyz` from the API will check this key in Slice 1.

## Slice 1+

Real Redis Streams consumer + runner pool dispatch. See spec §5 sequence diagram.
