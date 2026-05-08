"""Ed25519 attestation signing — spec §9.

Signs the canonical JSON blob (RFC 8785 key-ordering) with an Ed25519 private key
loaded from POLYEVAL_ED25519_PRIVKEY_PATH.

Key is loaded once at module import and cached.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)

log = structlog.get_logger()

_privkey: Ed25519PrivateKey | None = None
_pubkey_id: str = "polyeval-dev"
_host_fingerprint: str = ""


def _get_host_fingerprint() -> str:
    """Stable fingerprint: sha256(cpu_model) truncated to 16 hex chars."""
    try:
        cpu = platform.processor() or platform.machine()
    except Exception:
        cpu = "unknown"
    return hashlib.sha256(cpu.encode()).hexdigest()[:16]


def load_key(privkey_path: Path | None = None, pubkey_id: str = "polyeval-dev") -> None:
    """Load private key from path (call once at aggregator startup)."""
    global _privkey, _pubkey_id, _host_fingerprint

    _pubkey_id = pubkey_id
    _host_fingerprint = _get_host_fingerprint()

    if privkey_path is None:
        env_path = os.environ.get("POLYEVAL_ED25519_PRIVKEY_PATH")
        privkey_path = Path(env_path) if env_path else Path("/run/secrets/eval-signer.key")

    if not privkey_path.exists():
        log.warning("attestation.key_not_found", path=str(privkey_path))
        return

    pem = privkey_path.read_bytes()
    _privkey = load_pem_private_key(pem, password=None)  # type: ignore[assignment]
    log.info("attestation.key_loaded", pubkey_id=_pubkey_id)


def _canonical_json(obj: Any) -> bytes:
    """RFC 8785-compatible: sort keys recursively, no extra whitespace."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def sign_attestation(attestation_dict: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    """Sign the attestation dict. Returns (signed_dict, raw_sig_bytes).

    The `signature` field is base64(ed25519(canonical_json_without_signature)).
    If key not loaded (dev), signature is empty and sig_bytes is b"".
    """
    # Ensure no existing signature corrupts the payload.
    payload = {k: v for k, v in attestation_dict.items() if k != "signature"}
    payload["signature_algorithm"] = "Ed25519"
    payload["pubkey_id"] = _pubkey_id
    payload["host_fingerprint"] = _host_fingerprint

    canonical = _canonical_json(payload)

    if _privkey is None:
        log.warning("attestation.key_not_loaded_signing_empty")
        signed = {**payload, "signature": ""}
        return (signed, b"dev-no-key")

    raw_sig = _privkey.sign(canonical)
    sig_b64 = base64.b64encode(raw_sig).decode("ascii")
    signed = {**payload, "signature": sig_b64}
    return (signed, raw_sig)


def generate_dev_keypair(out_dir: Path) -> None:  # pragma: no cover
    """Generate a throwaway dev keypair for local testing."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    priv = Ed25519PrivateKey.generate()
    priv_pem = priv.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    pub_pem = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval-signer.key").write_bytes(priv_pem)
    (out_dir / "polyeval-dev.pub").write_bytes(pub_pem)
    print(f"Keypair written to {out_dir}")
