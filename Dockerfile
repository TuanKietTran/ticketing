FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY src ./src
COPY alembic.ini ./
CMD ["uv", "run", "uvicorn", "ticketing.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
