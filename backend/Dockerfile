FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock /app/
COPY backend /app/backend
COPY README.md /app/README.md

RUN uv sync --frozen --no-dev --no-editable

COPY prototype /app/prototype

EXPOSE 8000
CMD ["uv", "run", "--frozen", "--no-dev", "--no-editable", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
