.PHONY: test load chaos tf-check

test:
	uv run pytest -q
	uv run ruff check .

load:
	ulimit -n 65536; uv run python -m tools.loadgen.main --buyers 10000 --capacity 1000 --concurrency 100 --ramp-seconds 5

load-split:
	ulimit -n 65536; seq 1 4 | xargs -P4 -I{} uv run python -m tools.loadgen.main --buyers 2500 --capacity 250 --concurrency 50 --ramp-seconds 2

chaos:
	uv run uvicorn ticketing.app:app --host 127.0.0.1 --port 18040 --workers 1 >/tmp/ticketing-chaos.log 2>&1 & \
	pid=$$!; \
	trap 'kill $$pid 2>/dev/null || true' EXIT; \
	for i in $$(seq 1 30); do curl -sf http://127.0.0.1:18040/healthz >/dev/null && break; sleep 1; done; \
	uv run python -m tools.chaos.main --base-url http://127.0.0.1:18040

tf-check:
	terraform fmt -check -recursive infra/terraform
	terraform -chdir=infra/terraform/envs/staging init -backend=false
	terraform -chdir=infra/terraform/envs/staging validate
	terraform -chdir=infra/terraform/envs/prod init -backend=false
	terraform -chdir=infra/terraform/envs/prod validate
	terraform -chdir=infra/terraform/bootstrap init -backend=false
	terraform -chdir=infra/terraform/bootstrap validate
