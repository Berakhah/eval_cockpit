#!/usr/bin/env python3
"""Seed demo data into a running PolyEval stack.

Usage:
    python scripts/seed_demo.py [--api-url http://localhost:8000] [--tenant demo]

Submits one Python + one JavaScript sample submission, polls until scored,
then prints a results summary. Designed for `make demo`.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime

try:
    import httpx
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "-q"])
    import httpx

_PYTHON_CODE = '''\
def add(a: int, b: int) -> int:
    return a + b
'''

_PYTHON_TEST = '''\
import pytest
from solution import add

def test_basic():
    assert add(1, 2) == 3
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
'''

_JS_CODE = '''\
function add(a, b) { return a + b; }
module.exports = { add };
'''

_JS_TEST = '''\
const { add } = require('./solution');
test('add basic', () => {
    expect(add(1, 2)).toBe(3);
    expect(add(-1, 1)).toBe(0);
});
'''

_SUBMISSIONS = [
    {
        "model_id": "demo-model-python",
        "language": "python",
        "prompt": "Write an add function for two integers.",
        "code": _PYTHON_CODE,
        "test_suite": {
            "files": [{"name": "test_solution.py", "content": _PYTHON_TEST}],
            "entrypoint": "test_solution.py",
        },
        "trials": 5,
    },
    {
        "model_id": "demo-model-js",
        "language": "javascript",
        "prompt": "Write an add function for two numbers.",
        "code": _JS_CODE,
        "test_suite": {
            "files": [{"name": "test.js", "content": _JS_TEST}],
            "entrypoint": "test.js",
        },
        "trials": 5,
    },
]


def _sign(body_bytes: bytes, tenant: str, secret: str) -> dict[str, str]:
    nonce = str(uuid.uuid4())
    timestamp = datetime.now(UTC).isoformat()
    mac = hmac.new(secret.encode(), body_bytes, hashlib.sha256)
    return {
        "X-Polyeval-Signature": f"hmac-sha256:{mac.hexdigest()}",
        "X-Polyeval-Timestamp": timestamp,
        "X-Polyeval-Nonce": nonce,
        "X-Polyeval-Tenant": tenant,
        "Content-Type": "application/json",
    }


def submit(client: httpx.Client, api_url: str, tenant: str, secret: str, sub: dict) -> str:
    body = json.dumps({
        "model_id": sub["model_id"],
        "language": sub["language"],
        "prompt": sub["prompt"],
        "code": sub["code"],
        "test_suite": sub["test_suite"],
        "trials": sub["trials"],
        "timeout_seconds": 30,
        "memory_limit_mb": 256,
        "determinism_seed": 0xCAFEF00D,
    })
    body_bytes = body.encode()
    headers = _sign(body_bytes, tenant, secret)
    r = client.post(f"{api_url}/v1/submissions", content=body_bytes, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()["id"]


def poll_until_scored(client: httpx.Client, api_url: str, tenant: str, secret: str, sub_id: str, max_wait_s: int = 120) -> dict:
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        body = b""
        headers = _sign(body, tenant, secret)
        # GET has no body — sign empty bytes
        headers["X-Polyeval-Nonce"] = str(uuid.uuid4())  # fresh nonce per poll
        headers["X-Polyeval-Timestamp"] = datetime.now(UTC).isoformat()
        mac = hmac.new(secret.encode(), body, hashlib.sha256)
        headers["X-Polyeval-Signature"] = f"hmac-sha256:{mac.hexdigest()}"

        r = client.get(f"{api_url}/v1/submissions/{sub_id}", headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data["status"] in ("scored", "failed"):
                return data
        time.sleep(3)
    raise TimeoutError(f"submission {sub_id} not scored after {max_wait_s}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data into PolyEval")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--tenant", default="demo-tenant")
    parser.add_argument("--secret", default="dev-secret-please-rotate-32bytes-min")
    args = parser.parse_args()

    print(f"Seeding demo data → {args.api_url} (tenant={args.tenant})")
    ids = []

    with httpx.Client() as client:
        for sub in _SUBMISSIONS:
            print(f"  Submitting {sub['language']}...", end="", flush=True)
            sub_id = submit(client, args.api_url, args.tenant, args.secret, sub)
            ids.append((sub["language"], sub_id))
            print(f" {sub_id}")

        print("\nWaiting for scoring...")
        for lang, sub_id in ids:
            print(f"  Polling {lang} [{sub_id[:8]}]...", end="", flush=True)
            result = poll_until_scored(client, args.api_url, args.tenant, args.secret, sub_id)
            status = result["status"]
            if status == "scored":
                r = result.get("result") or {}
                correctness = r.get("correctness", "n/a")
                reliability = r.get("reliability", "n/a")
                print(f" {status} correctness={correctness:.3f} reliability={reliability:.3f}")
            else:
                print(f" {status}")

    print("\nDemo seed complete.")


if __name__ == "__main__":
    main()
