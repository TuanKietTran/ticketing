.PHONY: test load chaos

test:
	uv run pytest -q
	uv run ruff check .

load:
	uv run python -m tools.loadgen.main --buyers 10000 --capacity 1000

chaos:
	uv run python -m tools.chaos.main
