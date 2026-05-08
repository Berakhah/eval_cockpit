"""polyeval verify — Ed25519 attestation verifier (spec §9).

Usage:
    polyeval verify <attestation.json> [--pubkey <path.pub>]

Exit codes:
    0  — valid attestation
    1  — invalid signature or malformed JSON
    2  — pubkey not found / unrecognised pubkey_id
    3  — usage error
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path


def _load_pubkey_bytes(pubkey_path: Path):
    """Load Ed25519 public key from PEM file."""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    pem = pubkey_path.read_bytes()
    return load_pem_public_key(pem)


def _canonical_json(obj: dict) -> bytes:
    """Reproduce the aggregator's RFC-8785-compatible serialisation."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def verify_attestation(attestation: dict, pubkey_path: Path | None = None) -> None:
    """Verify the Ed25519 signature in *attestation*.

    Raises ValueError with a human-readable message on failure.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    sig_b64 = attestation.get("signature", "")
    if not sig_b64:
        raise ValueError("attestation has no 'signature' field (was it signed with a dev key?)")

    try:
        raw_sig = base64.b64decode(sig_b64)
    except Exception as e:
        raise ValueError(f"cannot decode signature: {e}") from e

    # Reconstruct the canonical payload that was signed.
    payload = {k: v for k, v in attestation.items() if k != "signature"}

    canonical = _canonical_json(payload)

    # Resolve pubkey.
    if pubkey_path is None:
        env = os.environ.get("POLYEVAL_VERIFY_PUBKEY_PATH")
        if env:
            pubkey_path = Path(env)
        else:
            # Default: look for a .pub file named after pubkey_id in ~/.config/polyeval/
            pubkey_id = attestation.get("pubkey_id", "polyeval-dev")
            default = Path.home() / ".config" / "polyeval" / f"{pubkey_id}.pub"
            if default.exists():
                pubkey_path = default

    if pubkey_path is None or not pubkey_path.exists():
        raise FileNotFoundError(
            f"No public key found for pubkey_id='{attestation.get('pubkey_id')}'. "
            f"Set POLYEVAL_VERIFY_PUBKEY_PATH or place the key at "
            f"~/.config/polyeval/<pubkey_id>.pub"
        )

    pubkey = _load_pubkey_bytes(pubkey_path)
    if not isinstance(pubkey, Ed25519PublicKey):
        raise ValueError(f"Key at {pubkey_path} is not an Ed25519 public key")

    try:
        pubkey.verify(raw_sig, canonical)
    except InvalidSignature:
        raise ValueError("signature verification FAILED — attestation is invalid or tampered")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="polyeval verify",
        description="Verify an Ed25519-signed PolyEval attestation (spec §9).",
    )
    parser.add_argument("attestation_file", type=Path, help="Path to attestation JSON file")
    parser.add_argument(
        "--pubkey",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to Ed25519 public key PEM (overrides POLYEVAL_VERIFY_PUBKEY_PATH and default lookup)",
    )
    args = parser.parse_args()

    if not args.attestation_file.exists():
        print(f"error: file not found: {args.attestation_file}", file=sys.stderr)
        sys.exit(3)

    try:
        attestation = json.loads(args.attestation_file.read_text())
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        verify_attestation(attestation, args.pubkey)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    except ValueError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary on success.
    sub_id = attestation.get("submission_id", "unknown")
    scores = attestation.get("scores", {})
    correctness = scores.get("correctness", "n/a")
    print(
        f"OK  submission_id={sub_id} "
        f"correctness={correctness:.4f} "
        f"pubkey_id={attestation.get('pubkey_id', 'n/a')} "
        f"scored_at={attestation.get('scored_at', 'n/a')}"
    )
    sys.exit(0)
