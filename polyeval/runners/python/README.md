# runners/python

Python 3.12 runner.

Slice 1 deliverable. Inherits `runners/base` and adds:

- CPython 3.12 (system pip disabled; allow-list of stdlib + pytest + hypothesis)
- pytest entrypoint that emits a JSON report to `/work/result.json`
- runner image digest pinned in `runners/python/digest.txt` (consumed by the cache key — spec §9)

Empty until Slice 1.
