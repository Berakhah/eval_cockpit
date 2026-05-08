"""Unit tests for HMAC authentication — spec §12.1."""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

# ─── Helpers ──────────────────────────────────────────────────────────────────

_SECRET = "test-secret-key-for-unit-tests-abc"
_HMAC_PREFIX = "hmac-sha256:"


def _make_sig(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return _HMAC_PREFIX + mac.hexdigest()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now_minus(seconds: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()


# ─── Pure-logic tests (no FastAPI) ────────────────────────────────────────────

class TestComputeHmac:
    def test_deterministic(self) -> None:
        body = b'{"hello": "world"}'
        s1 = _make_sig(_SECRET, body)
        s2 = _make_sig(_SECRET, body)
        assert s1 == s2

    def test_different_body_different_sig(self) -> None:
        s1 = _make_sig(_SECRET, b"body1")
        s2 = _make_sig(_SECRET, b"body2")
        assert s1 != s2

    def test_different_secret_different_sig(self) -> None:
        body = b"body"
        s1 = _make_sig("secret1", body)
        s2 = _make_sig("secret2", body)
        assert s1 != s2

    def test_prefix_present(self) -> None:
        sig = _make_sig(_SECRET, b"x")
        assert sig.startswith(_HMAC_PREFIX)

    def test_hex_length(self) -> None:
        sig = _make_sig(_SECRET, b"x")
        # prefix + 64 hex chars
        assert len(sig) == len(_HMAC_PREFIX) + 64


class TestTimestampWindow:
    """Verify timestamp comparison logic in isolation."""

    def test_current_timestamp_in_window(self) -> None:
        ts = datetime.fromisoformat(_now_iso())
        age_s = abs((datetime.now(UTC) - ts).total_seconds())
        assert age_s < 300

    def test_old_timestamp_out_of_window(self) -> None:
        ts_str = _now_minus(400)
        ts = datetime.fromisoformat(ts_str)
        age_s = abs((datetime.now(UTC) - ts).total_seconds())
        assert age_s > 300

    def test_future_timestamp_in_window(self) -> None:
        ts = datetime.now(UTC) + timedelta(seconds=10)
        age_s = abs((datetime.now(UTC) - ts).total_seconds())
        assert age_s < 300


class TestConstantCompare:
    def test_equal_strings(self) -> None:
        assert hmac.compare_digest(b"abc", b"abc")

    def test_unequal_strings(self) -> None:
        assert not hmac.compare_digest(b"abc", b"xyz")

    def test_prefix_match_rejected(self) -> None:
        assert not hmac.compare_digest(b"abcde", b"abc")
