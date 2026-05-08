# scripts

Operator + CI scripts.

| script           | slice | purpose |
|------------------|-------|---------|
| `seed_demo.py`   | 7     | Seeds tenant + demo submissions for the public demo |
| `load_test.py`   | 7     | Locust load test driving sustained submission load |
| `chaos.py`       | 7     | Toxiproxy harness — kills runners mid-trial, latency-injects redis |
| `seed_baselines` | 2     | Pre-computes Rust baselines for fixture suites (called from `make seed-baselines`) |

Scripts are entrypointed individually — each owns its own dependencies inside its module.
