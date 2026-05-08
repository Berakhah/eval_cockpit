# Determinism contract

Spec §8. Drafted in Slice 0, expanded in Slice 5.

## Goals

A submission re-run with the same `(prompt, tests, language, runner_image_digest)`
must produce byte-identical correctness, identical structure of `framework_passed`
output, and a perf reading whose trimmed-mean wall time is within ±2% of the
prior reading.

## Mechanism

1. **External clock** — the runner does **not** time itself. The scheduler measures
   `clock_gettime(CLOCK_MONOTONIC)` immediately before `execve` and immediately
   after the runner process exits. This dodges in-sandbox time tampering.
2. **CPU pinning** — runners are pinned to a dedicated cpuset; cgroup `cpu.weight`
   set to 1000; sibling SMT threads are excluded.
3. **Warmup discard** — N=trials+2 runs. Top and bottom run by wall time are dropped
   before reduction. Trimmed mean (10/90 quantile clip) is the reported perf.
4. **Seeded RNG** — LD_PRELOAD shim seeds `/dev/urandom`, `getrandom(2)`, libc
   `srand`, and Python's `random` module from `POLYEVAL_DETERMINISM_SEED` (per
   trial: `sha256(submission_id || trial_index)[:8]` little-endian).
5. **Filesystem** — read-only rootfs; `/work` is a tmpfs sized at `cgroup.memory.max`.
6. **Network** — denied at runtime via gVisor netstack with no interfaces attached.

Determinism property tests live in `polyeval/api/tests/property/test_determinism.py`
and run on every CI PR.

## Known sources of nondeterminism we accept

- JIT warmup variance for languages that JIT (Java, JS): mitigated by warmup discard.
- ASLR: enabled. We do not measure addresses.
- TSC drift across reboots: irrelevant — wall time is measured on a single host.
