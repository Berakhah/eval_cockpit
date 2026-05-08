# Attestation format

Spec §12.2. Drafted in Slice 0, signing wired in Slice 1.

## Wire shape

```
{
  "version": 1,
  "submission_id": "uuid",
  "tenant_id": "string",
  "model_id": "string",
  "language": "python|javascript|java|cpp|rust",
  "runner_image_digest": "sha256:...",
  "scheduler_image_digest": "sha256:...",
  "aggregator_image_digest": "sha256:...",
  "input_hash": "sha256(prompt || tests)",
  "result": {
    "correctness": <float>,
    "perf_ratio": <float>,
    "trial_count": <int>,
    "ci95": [<float>, <float>]
  },
  "completed_at": "rfc3339",
  "signature": "base64(ed25519(canonical_json(everything_above)))"
}
```

`canonical_json` is RFC 8785 (JSON Canonicalization Scheme).

## Key handling (v1)

- One global Ed25519 key per environment (dev, staging, prod).
- Public key shipped as `polyeval-pubkey.pem` next to the binary.
- Private key path read from `POLYEVAL_ED25519_PRIVKEY_PATH` (defaults to a
  Docker secret mount).

## Key rotation (deferred)

Out of v1 scope. Not implemented. The wire format reserves no `kid` field —
adding one is a breaking change tracked by `version: 2`.

## Verification

`polyeval verify <attestation.json> --pubkey polyeval-pubkey.pem` ships in
Slice 7 as a standalone CLI under `polyeval-api`'s `polyeval-verify` console
script.
