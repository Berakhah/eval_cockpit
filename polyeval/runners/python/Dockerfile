# syntax=docker/dockerfile:1.7
# Python runner — spec §7.4: python:3.12-slim, pytest, forbidden: ptrace/bpf/clone3.

FROM polyeval/runner-base:latest AS python-runner

USER 0
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.12 python3-pip python3.12-dev \
    && pip3 install --no-cache-dir pytest pytest-json-report \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.py /usr/local/bin/entrypoint.py
COPY seccomp-python.json /etc/polyeval/seccomp-python.json

RUN chmod +x /usr/local/bin/entrypoint.py

USER 65534
WORKDIR /work

CMD ["python3", "/usr/local/bin/entrypoint.py"]
