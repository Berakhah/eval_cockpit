"""Locust load test for the PolyEval API.

Run:
    locust -f scripts/load_test.py --host http://localhost:8000 -u 5 -r 1 --run-time 60s

Or headless for CI:
    locust -f scripts/load_test.py --host http://localhost:8000 \
        -u 5 -r 1 --run-time 60s --headless --exit-code-on-error 1

Requires: pip install locust
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime

from locust import HttpUser, between, task

_TENANT = "load-test-tenant"
_SECRET = "dev-secret-please-rotate-32bytes-min"

_PYTHON_CODE = "def add(a, b):\n    return a + b\n"
_PYTHON_TEST = (
    "from solution import add\n"
    "def test_add(): assert add(1,2)==3\n"
)
_JS_CODE = "function add(a,b){return a+b;}module.exports={add};"
_JS_TEST = "const {add}=require('./solution');test('add',()=>expect(add(1,2)).toBe(3));"


def _make_headers(body_bytes: bytes, tenant: str, secret: str) -> dict[str, str]:
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


class PolyEvalUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(3)
    def submit_python(self) -> None:
        self._submit("python", _PYTHON_CODE, "test_solution.py", _PYTHON_TEST)

    @task(1)
    def submit_javascript(self) -> None:
        self._submit("javascript", _JS_CODE, "test.js", _JS_TEST)

    @task(2)
    def list_submissions(self) -> None:
        body = b""
        headers = _make_headers(body, _TENANT, _SECRET)
        self.client.get("/v1/submissions", headers=headers, name="/v1/submissions [list]")

    @task(1)
    def health_check(self) -> None:
        self.client.get("/healthz", name="/healthz")

    def _submit(self, language: str, code: str, test_name: str, test_content: str) -> None:
        payload = {
            "model_id": f"load-test-{language}",
            "language": language,
            "prompt": f"Write an add function ({language})",
            "code": code,
            "test_suite": {
                "files": [{"name": test_name, "content": test_content}],
                "entrypoint": test_name,
            },
            "trials": 3,
            "timeout_seconds": 30,
            "memory_limit_mb": 256,
            "determinism_seed": 0xCAFEF00D,
        }
        body = json.dumps(payload).encode()
        headers = _make_headers(body, _TENANT, _SECRET)
        self.client.post(
            "/v1/submissions",
            data=body,
            headers=headers,
            name=f"/v1/submissions [POST {language}]",
        )
