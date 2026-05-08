"""CLI entrypoint that emits the FastAPI OpenAPI document to stdout.

The cockpit's `bun run codegen` step consumes this output via openapi-typescript
to produce `src/infrastructure/api/generated.ts`. Spec §6 defines the API surface;
the Pydantic models in `polyeval_api.schemas` are the canonical source of truth.
"""

import json
import sys

from .main import create_app


def main() -> None:
    app = create_app()
    schema = app.openapi()
    json.dump(schema, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
