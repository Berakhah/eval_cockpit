# runners/base

Common base image for all language runners.

Defines:

- gVisor (`runsc`) runtime expectations
- non-root `runner` UID 65534
- read-only rootfs + tmpfs `/work`
- seccomp profile (`seccomp.json`) — denies `clone`, `unshare`, `ptrace`, `socket`, `mount`, etc.
- cgroupv2 controllers: `cpu.weight`, `memory.max`, `pids.max`
- LD_PRELOAD shim that seeds `/dev/urandom`, `getrandom`, `srand` from `POLYEVAL_DETERMINISM_SEED`

The base image is built once and used as the parent for every per-language runner
(`runners/python`, `runners/javascript`, `runners/java`, `runners/cpp`, `runners/rust`).

Filled in **Slice 1** alongside the Python runner. Slice 0 only reserves the path.

See `docs/sandbox-threat-model.md` and `docs/determinism.md` for the rationale.
