# syntax=docker/dockerfile:1.7
FROM rust:1.83-slim-bookworm AS builder

WORKDIR /build
RUN apt-get update \
    && apt-get install -y --no-install-recommends pkg-config libssl-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Cache deps separately from sources for fast incremental builds.
COPY Cargo.toml ./
RUN mkdir -p src && echo 'fn main() {}' > src/main.rs && cargo build --release && rm -rf src

COPY src ./src
RUN cargo build --release && cp target/release/polyeval-scheduler /polyeval-scheduler

FROM debian:bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 1000 --shell /usr/sbin/nologin polyeval

USER polyeval
WORKDIR /app
COPY --from=builder /polyeval-scheduler /usr/local/bin/polyeval-scheduler

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8001/healthz || exit 1

CMD ["/usr/local/bin/polyeval-scheduler"]
