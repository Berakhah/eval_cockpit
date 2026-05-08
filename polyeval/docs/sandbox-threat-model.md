# Sandbox threat model

Spec §7. Drafted in Slice 0, hardened in Slice 5.

## Adversary

The submitted code is treated as **fully adversarial**. We assume the model under
evaluation may emit code crafted to escape, exfiltrate, or DoS. Static analysis
of submitted code is **not** a defense in depth — we rely on the sandbox alone.

## Defense layers (must all hold simultaneously)

1. **gVisor (`runsc`)** — userspace kernel; system call surface to host kernel
   reduced to a small allow-list.
2. **seccomp-bpf** — applied inside the sandbox; denies `mount`, `unshare`,
   `clone3` with new namespaces, `ptrace`, `bpf`, `kexec_load`, `init_module`,
   raw sockets, `AF_NETLINK`.
3. **Read-only rootfs** — only `/work` (tmpfs) and `/tmp` (tmpfs, 64MB) are
   writable. Both wiped between trials.
4. **No network** — no veth, no loopback to host. DNS denied.
5. **cgroupv2** — `memory.max`, `pids.max=64`, `cpu.weight`, `io.max=0` for any
   real block device.
6. **Non-root** — uid 65534, no capabilities (`--cap-drop=ALL`), no_new_privs.
7. **Wall clock** — runner cannot affect timing measurement (see `determinism.md`).

## Threats explicitly out of scope

- Speculative execution side channels across tenants — mitigated only by host
  kernel mitigations and CPU pinning. Not claimed as a security boundary.
- Power analysis or thermal side channels.
- Compromise of the runner image itself (supply chain) — addressed by SLSA L3
  build provenance in Slice 5, not here.

## Adversarial corpus

`polyeval/api/tests/adversarial/` holds 10 sandbox-escape attempts. CI fails the
build if any escape produces a sandbox_violation=false trial.
