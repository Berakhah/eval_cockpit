.PHONY: dev up down logs test openapi seed-baselines clean ps demo load-test chaos verify gen-keypair

COMPOSE := docker compose -f infra/docker-compose.yml
COMPOSE_TEST := docker compose -f infra/docker-compose.test.yml

# Boot the full local dev stack and tail api logs.
dev:
	$(COMPOSE) up -d
	$(COMPOSE) logs -f api scheduler

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down --remove-orphans

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

# Regenerate openapi.json from the FastAPI app.
# Cockpit codegen consumes this file via openapi-typescript.
openapi:
	cd api && python -m polyeval_api.openapi > openapi.json
	@echo "wrote api/openapi.json"

# Run the api unit tests inside the api container.
test:
	$(COMPOSE) run --rm api pytest -q

# Pre-compute Rust baselines for all fixture test suites (Slice 2+).
seed-baselines:
	@echo "seed-baselines: implemented in Slice 2"

# ─── Demo ─────────────────────────────────────────────────────────────────────
# Boot the stack and seed demo submissions; polls until scored and prints summary.
demo: up
	@echo "Waiting for stack to be healthy..."
	@sleep 10
	@$(COMPOSE) run --rm api alembic upgrade head 2>/dev/null || true
	@python scripts/seed_demo.py
	@echo ""
	@echo "Grafana:    http://localhost:3000"
	@echo "API docs:   http://localhost:8000/docs"
	@echo "Prometheus: http://localhost:9090"

# ─── Load test ────────────────────────────────────────────────────────────────
# Sustained submission load for 60s with 5 concurrent users.
# Requires: pip install locust
load-test:
	locust -f scripts/load_test.py \
	  --host http://localhost:8000 \
	  -u 5 -r 1 \
	  --run-time 60s \
	  --headless \
	  --exit-code-on-error 1

# ─── Chaos ────────────────────────────────────────────────────────────────────
# Default chaos scenario: kill and restart the scheduler.
chaos:
	python scripts/chaos.py kill-scheduler

# ─── Attestation verification ─────────────────────────────────────────────────
# polyeval verify <attestation.json> [--pubkey <path.pub>]
verify:
	@python -m polyeval_api.cli.verify $(filter-out $@,$(MAKECMDGOALS))

# ─── Dev utilities ────────────────────────────────────────────────────────────
# Generate a throwaway Ed25519 keypair for local attestation signing.
gen-keypair:
	python -c "from polyeval_aggregator.attestation.sign import generate_dev_keypair; \
	           from pathlib import Path; \
	           generate_dev_keypair(Path('infra/secrets'))"
	@echo "Keys written to infra/secrets/ (gitignored)"

# Tear down all volumes — DESTRUCTIVE.
clean:
	$(COMPOSE) down --volumes --remove-orphans
