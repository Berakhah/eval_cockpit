# syntax=docker/dockerfile:1.7
# C++ runner — spec §7.4: debian:bookworm-slim, g++17, no external test lib needed.
# Two-phase: POLYEVAL_PHASE=compile (untimed g++), POLYEVAL_PHASE=run (timed ./a.out).

FROM debian:bookworm-slim AS cpp-runner

ENV LD_PRELOAD=/usr/lib/libpolyeval_seed.so

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc g++ libc6-dev libdl-dev python3 \
    && rm -rf /var/lib/apt/lists/*

COPY libpolyeval_seed.c /src/
RUN gcc -shared -fPIC -O2 -o /usr/lib/libpolyeval_seed.so /src/libpolyeval_seed.c -ldl \
    && rm -rf /src

RUN useradd -u 65534 -g 65534 -M -s /usr/sbin/nologin polyeval 2>/dev/null || true

COPY entrypoint.py /usr/local/bin/entrypoint.py
COPY seccomp-cpp.json /etc/polyeval/seccomp-cpp.json

RUN chmod +x /usr/local/bin/entrypoint.py

USER 65534
WORKDIR /work

CMD ["python3", "/usr/local/bin/entrypoint.py"]
