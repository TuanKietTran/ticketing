.PHONY: test load chaos tf-check

test:
	uv run pytest -q
	uv run ruff check .

load:
	uv run python -m tools.loadgen.main --buyers 10000 --capacity 1000

chaos:
	uv run python -m tools.chaos.main

tf-check:
	terraform fmt -check -recursive infra/terraform
	terraform -chdir=infra/terraform/envs/staging init -backend=false
	terraform -chdir=infra/terraform/envs/staging validate
	terraform -chdir=infra/terraform/envs/prod init -backend=false
	terraform -chdir=infra/terraform/envs/prod validate
	terraform -chdir=infra/terraform/bootstrap init -backend=false
	terraform -chdir=infra/terraform/bootstrap validate
