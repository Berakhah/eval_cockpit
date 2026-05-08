"""End-to-end acceptance test — spec §13.2.

Validates: Python `add(a, b)` → correctness = 1.0.

Runs against a live stack started by docker compose (CI integration job).
Required env vars:
  POLYEVAL_API_URL  — e.g. http://localhost:8000
  POLYEVAL_TEST_TENANT — tenant id used in HMAC header
  POLYEVAL_HMAC_SECRET — signing secret (empty string = dev/no-HMAC mode)

The test POSTs a pytest test suite that imports solution.add(),
polls until status == 'scored', then asserts correctness_score == 1.0.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_module
import os
import time
import uuid

import httpx
import pytest

# ─── Config from env ──────────────────────────────────────────────────────────

API_URL = os.environ.get("POLYEVAL_API_URL", "http://localhost:8000")
TENANT = os.environ.get("POLYEVAL_TEST_TENANT", "integration-test")
HMAC_SECRET = os.environ.get("POLYEVAL_HMAC_SECRET", "")

POLL_TIMEOUT_S = 120
POLL_INTERVAL_S = 2

# ─── HMAC helper ──────────────────────────────────────────────────────────────

def _sign_request(body: bytes) -> dict[str, str]:
    from datetime import UTC, datetime
    ts = datetime.now(UTC).isoformat()
    nonce = uuid.uuid4().hex
    if HMAC_SECRET:
        mac = hmac_module.new(HMAC_SECRET.encode(), body, hashlib.sha256)
        sig = "hmac-sha256:" + mac.hexdigest()
    else:
        sig = "hmac-sha256:dev"
    return {
        "X-Polyeval-Signature": sig,
        "X-Polyeval-Timestamp": ts,
        "X-Polyeval-Nonce": nonce,
        "X-Polyeval-Tenant": TENANT,
        "Content-Type": "application/json",
    }

# ─── Test data ────────────────────────────────────────────────────────────────

_CODE = """\
def add(a, b):
    return a + b
"""

_TEST_FILE_CONTENT = """\
import pytest
from solution import add


@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3),
    (0, 0, 0),
    (-1, 1, 0),
    (10, 32, 42),
    (-5, -3, -8),
])
def test_add(a, b, expected):
    assert add(a, b) == expected
"""

_SUBMISSION_PAYLOAD = {
    "model_id": "test-model-add",
    "language": "python",
    "prompt": "Write a function add(a, b) that returns a + b.",
    "code": _CODE,
    "test_suite": {
        "framework": "pytest",
        "files": [
            {"name": "test_add.py", "content": _TEST_FILE_CONTENT},
        ],
        "entrypoint": "test_add.py",
    },
    "trials": 5,
    "timeout_seconds": 15.0,
    "memory_limit_mb": 256,
}

# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_api_health() -> None:
    """Sanity check: API is reachable."""
    resp = httpx.get(f"{API_URL}/healthz", timeout=10)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


@pytest.mark.integration
def test_add_correctness_one() -> None:  # spec §13.2
    """Submit Python add(a,b) and assert correctness_score == 1.0."""
    import json

    body_bytes = json.dumps(_SUBMISSION_PAYLOAD).encode()
    headers = _sign_request(body_bytes)

    # 1. Submit.
    resp = httpx.post(
        f"{API_URL}/v1/submissions",
        content=body_bytes,
        headers=headers,
        timeout=30,
    )
    assert resp.status_code == 202, f"submit failed: {resp.status_code} {resp.text}"
    submission_id = resp.json()["id"]

    # 2. Poll until scored.
    deadline = time.monotonic() + POLL_TIMEOUT_S
    result_body: dict = {}
    while time.monotonic() < deadline:
        poll_headers = _sign_request(b"")
        poll_resp = httpx.get(
            f"{API_URL}/v1/submissions/{submission_id}",
            headers=poll_headers,
            timeout=10,
        )
        assert poll_resp.status_code == 200, f"poll failed: {poll_resp.status_code}"
        result_body = poll_resp.json()
        status = result_body.get("status")
        if status == "scored":
            break
        if status == "failed":
            pytest.fail(f"submission failed: {result_body}")
        time.sleep(POLL_INTERVAL_S)
    else:
        pytest.fail(f"timed out after {POLL_TIMEOUT_S}s, last status: {result_body.get('status')}")

    # 3. Assert spec §13.2: correctness == 1.0.
    result = result_body.get("result")
    assert result is not None, "result is None on scored submission"
    correctness = result["correctness"]
    assert correctness == pytest.approx(1.0), (
        f"Expected correctness=1.0, got {correctness}. "
        f"trials_passed={result.get('trials_passed')}/{result.get('trials_total')}"
    )

    # 4. Sanity: CI covers 1.0.
    ci = result["correctness_ci"]
    assert ci["lo"] <= 1.0 <= ci["hi"], f"CI [{ci['lo']}, {ci['hi']}] does not cover 1.0"

    # 5. Sanity: reliability is non-flaky (all trials pass → stable).
    assert result["reliability"] >= 0.95 or not result["flaky"], (
        f"Expected non-flaky for deterministic add(), got reliability={result['reliability']}"
    )
