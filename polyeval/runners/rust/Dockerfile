# syntax=docker/dockerfile:1.7
# Rust runner — spec §7.4: rust:1-slim, cargo build --release --offline
# Forbidden syscalls: ptrace, bpf (see seccomp-rust.json).
# Two-phase: POLYEVAL_PHASE=compile (untimed) then POLYEVAL_PHASE=run (timed).

FROM rust:1-slim AS rust-toolchain

FROM debian:bookworm-slim AS rust-runner

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH \
    LD_PRELOAD=/usr/lib/libpolyeval_seed.so \
    PYTHONDONTWRITEBYTECODE=1

# System deps: gcc for LD_PRELOAD shim, python3 for entrypoint, libdl for dlsym.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc libc6-dev libdl-dev python3 \
    && rm -rf /var/lib/apt/lists/*

# Copy Rust toolchain from rust:1-slim.
COPY --from=rust-toolchain /usr/local/rustup /usr/local/rustup
COPY --from=rust-toolchain /usr/local/cargo  /usr/local/cargo

# Build LD_PRELOAD determinism shim.
COPY libpolyeval_seed.c /src/
RUN gcc -shared -fPIC -O2 -o /usr/lib/libpolyeval_seed.so /src/libpolyeval_seed.c -ldl \
    && rm -rf /src

# Non-root user UID 65534 (nobody) — spec §7.2.
RUN useradd -u 65534 -g 65534 -M -s /usr/sbin/nologin polyeval 2>/dev/null || true

COPY entrypoint.py /usr/local/bin/entrypoint.py
COPY seccomp-rust.json /etc/polyeval/seccomp-rust.json

RUN chmod +x /usr/local/bin/entrypoint.py

USER 65534
WORKDIR /work

CMD ["python3", "/usr/local/bin/entrypoint.py"]
