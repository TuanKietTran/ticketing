# ticketing

Flash-sale ticketing backend using Python/FastAPI, PostgreSQL, and Redis. Start with [specs/000-brief.md](specs/000-brief.md).

```sh
uv sync
make test
make load       # requires a running app
make chaos      # requires a running app
```

Measured results and unverified acceptance criteria are recorded in [specs/load-results.md](specs/load-results.md) and [specs/FINAL.md](specs/FINAL.md).
