FROM python:3.13-slim AS base

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY alembic/ alembic.ini ./
COPY . .

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 9090
EXPOSE 9091

# Default: run REST API. Override CMD for MCP server.
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9090"]
