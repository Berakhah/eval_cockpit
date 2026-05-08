# fly

One `fly.toml` per service for production deploy.

Populated in **Slice 7 (Demo readiness)**:

- `fly.api.toml`         — FastAPI gateway
- `fly.scheduler.toml`   — Rust dispatcher
- `fly.aggregator.toml`  — Python scorer
- `fly.runner-python.toml` and one per language (separate apps so resource limits
  and machine sizing can differ; gVisor enabled per-app)
- `fly.postgres.toml` and `fly.redis.toml` are **not** here — those use Fly's
  managed Postgres + Upstash Redis, configured via dashboard.

Slice 0 reserves the path; nothing to deploy yet.
