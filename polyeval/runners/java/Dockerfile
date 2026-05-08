# syntax=docker/dockerfile:1.7
# Java runner — spec §7.4: eclipse-temurin:21-jre, javac compile, JUnit 5, forbidden: perf_event_open.
# Two-phase: POLYEVAL_PHASE=compile (untimed javac), POLYEVAL_PHASE=run (timed java).

FROM eclipse-temurin:21-jre AS java-runner

ENV LD_PRELOAD=/usr/lib/libpolyeval_seed.so \
    JAVA_OPTS="-XX:-UsePerfData -XX:+DisableAttachMechanism -Xms64m -Xmx512m"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc libc6-dev libdl-dev python3 \
       default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Download JUnit 5 standalone JAR (all-in-one console launcher) for offline use.
RUN mkdir -p /opt/junit && \
    apt-get update -qq && apt-get install -y --no-install-recommends wget && \
    wget -q -O /opt/junit/junit-platform-console-standalone.jar \
      https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.10.3/junit-platform-console-standalone-1.10.3.jar \
    && apt-get remove -y wget && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY libpolyeval_seed.c /src/
RUN gcc -shared -fPIC -O2 -o /usr/lib/libpolyeval_seed.so /src/libpolyeval_seed.c -ldl \
    && rm -rf /src

RUN useradd -u 65534 -g 65534 -M -s /usr/sbin/nologin polyeval 2>/dev/null || true

COPY entrypoint.py /usr/local/bin/entrypoint.py
COPY seccomp-java.json /etc/polyeval/seccomp-java.json

RUN chmod +x /usr/local/bin/entrypoint.py

USER 65534
WORKDIR /work

CMD ["python3", "/usr/local/bin/entrypoint.py"]
