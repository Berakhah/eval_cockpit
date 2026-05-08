"""Unit tests for content-addressed cache key — spec §5.2."""

from __future__ import annotations

import hashlib

import pytest

from polyeval_api.cache.redis import build_cache_key, _sha256_hex


class TestBuildCacheKey:
    def test_format(self) -> None:
        key = build_cache_key("t1", "m1", "python", "prompt", '{"framework":"pytest"}', "sha256:abc")
        parts = key.split(":")
        # poly:cache:v1:{tenant}:{model}:{lang}:{hash}
        assert parts[0] == "poly"
        assert parts[1] == "cache"
        assert parts[2] == "v1"
        assert parts[3] == "t1"
        assert parts[4] == "m1"
        assert parts[5] == "python"
        assert len(parts[6]) == 64  # sha256 hex

    def test_deterministic(self) -> None:
        kwargs = dict(
            tenant_id="a", model_id="b", language="python",
            prompt="p", test_suite_serialized="s", runner_image_digest="d",
        )
        assert build_cache_key(**kwargs) == build_cache_key(**kwargs)

    def test_tenant_scoped(self) -> None:
        base = dict(model_id="m", language="python", prompt="p", test_suite_serialized="s", runner_image_digest="d")
        k1 = build_cache_key(tenant_id="alice", **base)
        k2 = build_cache_key(tenant_id="bob", **base)
        assert k1 != k2

    def test_model_scoped(self) -> None:
        base = dict(tenant_id="t", language="python", prompt="p", test_suite_serialized="s", runner_image_digest="d")
        k1 = build_cache_key(model_id="m1", **base)
        k2 = build_cache_key(model_id="m2", **base)
        assert k1 != k2

    def test_prompt_sensitive(self) -> None:
        base = dict(tenant_id="t", model_id="m", language="python", test_suite_serialized="s", runner_image_digest="d")
        k1 = build_cache_key(prompt="prompt-a", **base)
        k2 = build_cache_key(prompt="prompt-b", **base)
        assert k1 != k2

    def test_test_suite_sensitive(self) -> None:
        base = dict(tenant_id="t", model_id="m", language="python", prompt="p", runner_image_digest="d")
        k1 = build_cache_key(test_suite_serialized='{"files":[]}', **base)
        k2 = build_cache_key(test_suite_serialized='{"files":[{"name":"x"}]}', **base)
        assert k1 != k2

    def test_digest_sensitive(self) -> None:
        base = dict(tenant_id="t", model_id="m", language="python", prompt="p", test_suite_serialized="s")
        k1 = build_cache_key(runner_image_digest="sha256:aaa", **base)
        k2 = build_cache_key(runner_image_digest="sha256:bbb", **base)
        assert k1 != k2


class TestSha256Hex:
    def test_consistent_with_stdlib(self) -> None:
        result = _sha256_hex("hello", "world")
        expected = hashlib.sha256(b"helloworld").hexdigest()
        assert result == expected

    def test_bytes_input(self) -> None:
        result = _sha256_hex(b"binary")
        expected = hashlib.sha256(b"binary").hexdigest()
        assert result == expected
