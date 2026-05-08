#!/usr/bin/env python3
"""C++ runner entrypoint — spec §7.4.

Two phases controlled by POLYEVAL_PHASE env var:
  compile  — write sources, g++ compile to /work/a.out. No stdout JSON.
  run      — execute /work/a.out, emit trial JSON to stdout.

The scheduler calls compile once (untimed), then run N times (timed externally).
wall_ns reported here is informational only; scheduler measures externally (spec §7.3).

Test contract: the test file provides main(); exit 0 = all assertions pass.
"""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

_WORK = Path("/work")
_SRC = _WORK / "src"
_BINARY = _WORK / "a.out"


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
    _SRC.mkdir(parents=True, exist_ok=True)

    code: str = manifest.get("code", "")
    (_SRC / "solution.cpp").write_text(code, encoding="utf-8")

    test_suite: dict = manifest.get("test_suite", {})
    files: list[dict] = test_suite.get("files", [])
    cpp_sources = [str(_SRC / "solution.cpp")]

    for tf in files:
        target = _SRC / Path(tf["name"]).name
        target.write_text(tf["content"], encoding="utf-8")
        if target.suffix in (".cpp", ".cc", ".cxx"):
            cpp_sources.append(str(target))

    if not cpp_sources:
        print("COMPILE_FAILED: no C++ sources found", file=sys.stderr)
        sys.exit(1)

    compile_timeout = int(os.environ.get("POLYEVAL_COMPILE_TIMEOUT_S", "120"))
    try:
        result = subprocess.run(
            [
                "g++",
                "-O2",
                "-std=c++17",
                "-o", str(_BINARY),
                *cpp_sources,
            ],
            capture_output=True,
            text=True,
            timeout=compile_timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"COMPILE_TIMEOUT after {compile_timeout}s", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"COMPILE_FAILED:\n{result.stderr[:2048]}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


# ─── Run phase ────────────────────────────────────────────────────────────────

def _do_run(manifest: dict) -> None:
    if not _BINARY.exists():
        _emit_error("/work/a.out not found — compile phase may have failed")
        return

    trial_index: int = manifest.get("trial_index", 0)
    timeout_s = int(os.environ.get("POLYEVAL_TIMEOUT_S", "30"))

    t_start = time.perf_counter_ns()
    try:
        proc = subprocess.run(
            [str(_BINARY)],
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

    # Test binary: exit 0 = all assertions passed.
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
