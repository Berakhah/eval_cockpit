#!/usr/bin/env python3
"""Python runner entrypoint — spec §7.4.

Reads /work/manifest.json, materializes code + test files,
runs pytest with json-report, emits trial JSON to stdout.

Note: wall_ns reported here is informational only.
The scheduler measures wall time externally (spec §7.3 point 1).
"""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    manifest_path = Path("/work/manifest.json")
    if not manifest_path.exists():
        emit_error("manifest.json not found")
        return

    with manifest_path.open() as f:
        manifest: dict = json.load(f)

    code: str = manifest["code"]
    test_files: list[dict] = manifest["test_suite"]["files"]
    entrypoint: str = manifest["test_suite"]["entrypoint"]
    trial_index: int = manifest.get("trial_index", 0)

    work_dir = Path("/work")

    # Materialise user solution as solution.py (imported by tests).
    (work_dir / "solution.py").write_text(code, encoding="utf-8")

    # Materialise all test files.
    for tf in test_files:
        target = work_dir / tf["name"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(tf["content"], encoding="utf-8")

    result_json = work_dir / "result.json"

    t_start = time.perf_counter_ns()
    try:
        proc = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "--json-report",
                f"--json-report-file={result_json}",
                "-p", "no:cacheprovider",
                "--tb=short",
                str(work_dir / entrypoint),
            ],
            capture_output=True,
            text=True,
            cwd=str(work_dir),
            timeout=int(os.environ.get("POLYEVAL_TIMEOUT_S", "30")),
        )
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        emit_trial(trial_index, 0, 0, 124, False, False, "timeout")
        return
    except Exception as exc:
        emit_error(str(exc))
        return

    t_end = time.perf_counter_ns()
    wall_ns_internal = t_end - t_start

    mem_kb = 0
    try:
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        mem_kb = int(usage.ru_maxrss)  # already in KB on Linux
    except Exception:
        pass

    framework_passed = False
    stderr_snippet = (proc.stderr or "")[:512]

    if result_json.exists():
        try:
            with result_json.open() as rf:
                report = json.load(rf)
            summary = report.get("summary", {})
            passed = summary.get("passed", 0)
            failed = summary.get("failed", 0)
            errors = summary.get("error", 0)
            framework_passed = (exit_code == 0 and failed == 0 and errors == 0)
        except Exception:
            framework_passed = exit_code == 0
    else:
        framework_passed = exit_code == 0

    emit_trial(trial_index, wall_ns_internal, mem_kb, exit_code, framework_passed, False, stderr_snippet or None)


def emit_trial(
    index: int,
    wall_ns: int,
    mem_kb: int,
    exit_code: int,
    framework_passed: bool,
    sandbox_violation: bool,
    stderr_snippet: str | None,
) -> None:
    print(json.dumps({
        "index": index,
        "wall_ns": wall_ns,
        "mem_kb": mem_kb,
        "exit_code": exit_code,
        "framework_passed": framework_passed,
        "sandbox_violation": sandbox_violation,
        "stderr_snippet": stderr_snippet,
    }), flush=True)


def emit_error(msg: str) -> None:
    emit_trial(0, 0, 0, 1, False, False, msg)


if __name__ == "__main__":
    main()
