#!/usr/bin/env python3
"""Rust runner entrypoint — spec §7.4.

Two phases controlled by POLYEVAL_PHASE env var:
  compile  — create Cargo project, run `cargo test --no-run --release --offline`,
              write binary path to /work/binary_path.txt. No stdout JSON.
  run      — execute pre-compiled test binary, emit trial JSON to stdout.

The scheduler calls compile once (untimed), then run N times (timed externally).
wall_ns reported here is informational only; scheduler measures externally (spec §7.3).
"""

from __future__ import annotations

import glob
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path


_WORK = Path("/work")
_PROJECT = _work = _WORK / "project"
_BINARY_PATH_FILE = _WORK / "binary_path.txt"


def main() -> None:
    phase = os.environ.get("POLYEVAL_PHASE", "compile")
    manifest_path = _WORK / "manifest.json"

    if not manifest_path.exists():
        _emit_error("manifest.json not found")
        return

    with manifest_path.open() as f:
        manifest: dict = json.load(f)

    if phase == "compile":
        _do_compile(manifest)
    elif phase == "run":
        _do_run(manifest)
    else:
        _emit_error(f"unknown POLYEVAL_PHASE: {phase!r}")


# ─── Compile phase ────────────────────────────────────────────────────────────

def _do_compile(manifest: dict) -> None:
    project_dir = _WORK / "project"
    src_dir = project_dir / "src"
    tests_dir = project_dir / "tests"

    project_dir.mkdir(parents=True, exist_ok=True)
    src_dir.mkdir(exist_ok=True)
    tests_dir.mkdir(exist_ok=True)

    # Cargo.toml — lib + no external deps so --offline works.
    (project_dir / "Cargo.toml").write_text(
        '[package]\nname = "submission"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )

    # User's solution as src/lib.rs.
    (src_dir / "lib.rs").write_text(manifest["code"], encoding="utf-8")

    # Test files — use "integration" as the fixed name for the test binary.
    test_suite: dict = manifest.get("test_suite", {})
    files: list[dict] = test_suite.get("files", [])
    if files:
        # Merge all test files into a single tests/integration.rs.
        combined = "\n".join(tf["content"] for tf in files)
        (tests_dir / "integration.rs").write_text(combined, encoding="utf-8")
    else:
        # Fallback: empty integration test so cargo test has something to compile.
        (tests_dir / "integration.rs").write_text(
            "#[test]\nfn placeholder() {}\n", encoding="utf-8"
        )

    compile_timeout = int(os.environ.get("POLYEVAL_COMPILE_TIMEOUT_S", "120"))
    try:
        result = subprocess.run(
            [
                "cargo", "test",
                "--no-run",
                "--release",
                "--offline",
                "--test", "integration",
            ],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=compile_timeout,
            env={
                **os.environ,
                "CARGO_TARGET_DIR": str(project_dir / "target"),
                "RUSTFLAGS": "-C opt-level=3",
            },
        )
    except subprocess.TimeoutExpired:
        print(f"COMPILE_TIMEOUT after {compile_timeout}s", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"COMPILE_FAILED:\n{result.stderr[:2048]}", file=sys.stderr)
        sys.exit(1)

    # Find the integration test binary (name = integration-<hash>).
    pattern = str(project_dir / "target" / "release" / "deps" / "integration-*")
    candidates = [
        p for p in glob.glob(pattern)
        if not p.endswith(".d") and os.path.isfile(p) and os.access(p, os.X_OK)
    ]
    if not candidates:
        print(f"BINARY_NOT_FOUND: pattern={pattern}", file=sys.stderr)
        print(f"cargo stderr:\n{result.stderr[:2048]}", file=sys.stderr)
        sys.exit(1)

    binary = candidates[0]
    _BINARY_PATH_FILE.write_text(binary, encoding="utf-8")
    # No JSON output in compile phase.
    sys.exit(0)


# ─── Run phase ────────────────────────────────────────────────────────────────

def _do_run(manifest: dict) -> None:
    if not _BINARY_PATH_FILE.exists():
        _emit_error("binary_path.txt not found — compile phase may have failed")
        return

    binary = _BINARY_PATH_FILE.read_text(encoding="utf-8").strip()
    if not os.path.isfile(binary):
        _emit_error(f"compiled binary missing: {binary}")
        return

    trial_index: int = manifest.get("trial_index", 0)
    timeout_s = int(os.environ.get("POLYEVAL_TIMEOUT_S", "30"))

    t_start = time.perf_counter_ns()
    try:
        proc = subprocess.run(
            [binary, "--nocapture"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        _emit_trial(trial_index, 0, 0, 124, False, False, "timeout")
        return
    except Exception as exc:
        _emit_error(str(exc))
        return

    t_end = time.perf_counter_ns()
    wall_ns_internal = t_end - t_start

    mem_kb = 0
    try:
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        mem_kb = int(usage.ru_maxrss)
    except Exception:
        pass

    # cargo test binary: exit 0 = all tests passed, non-zero = failures.
    framework_passed = exit_code == 0
    stderr_snippet = (proc.stderr or "")[:512]

    _emit_trial(
        trial_index,
        wall_ns_internal,
        mem_kb,
        exit_code,
        framework_passed,
        False,
        stderr_snippet or None,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _emit_trial(
    index: int,
    wall_ns: int,
    mem_kb: int,
    exit_code: int,
    framework_passed: bool,
    sandbox_violation: bool,
    stderr_snippet: str | None,
) -> None:
    print(
        json.dumps({
            "index": index,
            "wall_ns": wall_ns,
            "mem_kb": mem_kb,
            "exit_code": exit_code,
            "framework_passed": framework_passed,
            "sandbox_violation": sandbox_violation,
            "stderr_snippet": stderr_snippet,
        }),
        flush=True,
    )


def _emit_error(msg: str) -> None:
    _emit_trial(0, 0, 0, 1, False, False, msg)


if __name__ == "__main__":
    main()
