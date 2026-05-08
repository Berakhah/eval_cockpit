# polyeval-api

FastAPI gateway for PolyEval. Implements §6 API surface from the spec:

- `POST /v1/submissions` — submit code for evaluation
- `GET /v1/submissions/{id}` — poll status + result
- `GET /v1/submissions/{id}/attestation` — download Ed25519-signed attestation
- `GET /v1/baselines/{test_suite_hash}` — inspect Rust baseline
- `POST /v1/baselines/refresh` — admin: re-run Rust baseline
- `GET /healthz`, `/readyz`, `/metrics`

All endpoints require `X-Polyeval-Signature` (HMAC-SHA-256 over raw body), `X-Polyeval-Timestamp`, and `X-Polyeval-Tenant`. See spec §12.1.

## Local development

From `polyeval/`:

```sh
make dev      # boots api, scheduler, postgres, redis, otel stack
make openapi  # regenerates openapi.json (consumed by cockpit codegen)
make test     # runs unit tests in container
```
