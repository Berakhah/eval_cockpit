# syntax=docker/dockerfile:1.7
# JavaScript runner — spec §7.4: node:22-slim, jest, forbidden: process_vm_*, userfaultfd.

FROM node:22-slim AS js-runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    LD_PRELOAD=/usr/lib/libpolyeval_seed.so \
    NODE_OPTIONS="--no-addons"

# Build LD_PRELOAD determinism shim + install jest globally.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev libdl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY libpolyeval_seed.c /src/
RUN gcc -shared -fPIC -O2 -o /usr/lib/libpolyeval_seed.so /src/libpolyeval_seed.c -ldl \
    && rm -rf /src

# Install jest globally so entrypoint.js can call `jest` directly.
RUN npm install -g jest@29 --prefer-offline 2>/dev/null || npm install -g jest@29

# Non-root user UID 65534.
RUN useradd -u 65534 -g 65534 -M -s /usr/sbin/nologin polyeval 2>/dev/null || true

COPY entrypoint.js /usr/local/bin/entrypoint.js
COPY seccomp-js.json /etc/polyeval/seccomp-js.json

RUN chmod +x /usr/local/bin/entrypoint.js

USER 65534
WORKDIR /work

CMD ["node", "--no-addons", "/usr/local/bin/entrypoint.js"]
