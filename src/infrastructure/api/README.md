# infrastructure/api

OpenAPI-derived TypeScript types and (later) HMAC-signed fetch helpers for
calling the polyeval backend.

## How `generated.ts` is produced

```
polyeval/api/  (Pydantic v2)
       │
       ├── python -m polyeval_api.openapi > openapi.json
       │           ↓
       └── openapi-typescript openapi.json -o src/infrastructure/api/generated.ts
```

This chain runs as `bun run codegen` (also wired into `predev` and `prebuild`).

## Drift policy

`bun run codegen:check` regenerates the types and `git diff --exit-code` fails
the build if anything moved. CI runs this on every PR. **Never edit
`generated.ts` by hand** — the change will be reverted on the next codegen.

## Slice 1 additions (planned)

- `client.ts` — typed fetch helpers using `paths`
- `signing.ts` — Web Crypto HMAC-SHA-256, runs only inside the Worker (server-fn)
