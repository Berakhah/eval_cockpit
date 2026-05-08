"""Chaos scenarios for PolyEval resilience testing.

Requires: docker compose stack running + python3 + docker SDK.

Scenarios:
  1. kill-scheduler   — kills the scheduler container mid-processing, verifies recovery
  2. redis-latency    — injects 500ms latency on Redis port via tc netem (Linux only)
  3. redis-partition  — disconnects Redis from the scheduler for 10s, checks DLQ
  4. oom-runner       — submits code that allocates 600MB (over limit), verifies OOM kill

Usage:
    python scripts/chaos.py kill-scheduler
    python scripts/chaos.py redis-latency --latency-ms 500 --duration-s 15
    python scripts/chaos.py redis-partition --duration-s 10
    python scripts/chaos.py oom-runner
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  + {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=False)


def kill_scheduler(args: argparse.Namespace) -> None:
    """Kill the scheduler container; verify it restarts and drains the queue."""
    print("=== chaos: kill-scheduler ===")
    _run(["docker", "compose", "-f", "infra/docker-compose.yml", "kill", "scheduler"])
    print("Scheduler killed. Waiting 5s...")
    time.sleep(5)
    _run(["docker", "compose", "-f", "infra/docker-compose.yml", "up", "-d", "scheduler"])
    print("Scheduler restarted. Check logs for pending message recovery.")
    time.sleep(3)
    r = _run(
        ["docker", "compose", "-f", "infra/docker-compose.yml", "logs", "--tail=20", "scheduler"],
        check=False,
    )
    print("Done. Exit code:", r.returncode)


def redis_latency(args: argparse.Namespace) -> None:
    """Inject tc netem latency on the Redis container's eth0."""
    latency_ms = args.latency_ms
    duration_s = args.duration_s
    print(f"=== chaos: redis-latency {latency_ms}ms for {duration_s}s ===")

    container = subprocess.check_output(
        ["docker", "compose", "-f", "infra/docker-compose.yml", "ps", "-q", "redis"],
        text=True,
    ).strip()

    print(f"Redis container: {container}")
    _run(["docker", "exec", container, "tc", "qdisc", "add", "dev", "eth0", "root",
          "netem", "delay", f"{latency_ms}ms"])
    print(f"Latency injected. Running for {duration_s}s...")
    time.sleep(duration_s)
    _run(["docker", "exec", container, "tc", "qdisc", "del", "dev", "eth0", "root"])
    print("Latency removed.")


def redis_partition(args: argparse.Namespace) -> None:
    """Block Redis port 6379 on the scheduler container for duration_s seconds."""
    duration_s = args.duration_s
    print(f"=== chaos: redis-partition for {duration_s}s ===")

    container = subprocess.check_output(
        ["docker", "compose", "-f", "infra/docker-compose.yml", "ps", "-q", "scheduler"],
        text=True,
    ).strip()

    print(f"Scheduler container: {container}")
    _run(["docker", "exec", container, "iptables", "-A", "OUTPUT",
          "-p", "tcp", "--dport", "6379", "-j", "DROP"])
    print(f"Redis blocked on scheduler. Running for {duration_s}s...")
    time.sleep(duration_s)
    _run(["docker", "exec", container, "iptables", "-D", "OUTPUT",
          "-p", "tcp", "--dport", "6379", "-j", "DROP"])
    print("Redis unblocked. Check aggregator for DLQ entries.")


def oom_runner(args: argparse.Namespace) -> None:
    """Submit a Python solution that allocates 600MB — should be OOM-killed."""
    print("=== chaos: oom-runner ===")
    print("Submitting memory-bomb submission (600MB alloc > 256MB limit)...")

    oom_code = (
        "def add(a, b):\n"
        "    _ = bytearray(600 * 1024 * 1024)  # 600MB — OOM bomb\n"
        "    return a + b\n"
    )

    sys.path.insert(0, ".")
    try:
        from scripts.seed_demo import _sign, submit
        import httpx

        with httpx.Client() as client:
            sub = {
                "model_id": "chaos-oom",
                "language": "python",
                "prompt": "Write an add function",
                "code": oom_code,
                "test_suite": {
                    "files": [{"name": "test_solution.py", "content": "from solution import add\ndef test_add(): assert add(1,2)==3\n"}],
                    "entrypoint": "test_solution.py",
                },
                "trials": 1,
            }
            sub_id = submit(client, "http://localhost:8000", "chaos-tenant",
                           "dev-secret-please-rotate-32bytes-min", sub)
            print(f"Submitted {sub_id}. Check runner logs for OOM kill (exit 137).")
    except Exception as e:
        print(f"Could not submit via API: {e}")
        print("Start the stack first: make -C polyeval up")


def main() -> None:
    parser = argparse.ArgumentParser(description="PolyEval chaos scenarios")
    sub = parser.add_subparsers(dest="scenario", required=True)

    sub.add_parser("kill-scheduler", help="Kill and restart the scheduler")

    lat = sub.add_parser("redis-latency", help="Inject Redis latency via tc netem")
    lat.add_argument("--latency-ms", type=int, default=500)
    lat.add_argument("--duration-s", type=int, default=15)

    part = sub.add_parser("redis-partition", help="Block Redis on scheduler")
    part.add_argument("--duration-s", type=int, default=10)

    sub.add_parser("oom-runner", help="Submit OOM-bomb (requires running stack)")

    args = parser.parse_args()
    {
        "kill-scheduler": kill_scheduler,
        "redis-latency": redis_latency,
        "redis-partition": redis_partition,
        "oom-runner": oom_runner,
    }[args.scenario](args)


if __name__ == "__main__":
    main()
