# syntax=docker/dockerfile:1.7
# Base runner image: non-root UID 65534, LD_PRELOAD seed shim, gVisor-safe.
# All language-specific runner images extend this.

FROM debian:bookworm-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    LD_PRELOAD=/usr/lib/libpolyeval_seed.so

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev libdl-dev \
    && rm -rf /var/lib/apt/lists/*

# Build the LD_PRELOAD determinism shim.
COPY libpolyeval_seed.c /src/
RUN gcc -shared -fPIC -O2 -o /usr/lib/libpolyeval_seed.so /src/libpolyeval_seed.c -ldl \
    && rm -rf /src

# Non-root user UID 65534 (nobody) — spec §7.2.
RUN useradd -u 65534 -g 65534 -M -s /usr/sbin/nologin polyeval 2>/dev/null || true

WORKDIR /work
