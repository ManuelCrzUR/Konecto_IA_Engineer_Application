FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# No apt packages: only opencv-python-headless is installed (the [tool.uv]
# override in pyproject.toml drops rapidocr's GUI opencv), so no X11/GL libs.

WORKDIR /app

# Dependencies first (cached unless pyproject/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code and data
COPY app ./app
COPY eval ./eval
COPY ingest.py cli.py ./
COPY data/raw/series_76_electric_data.pdf ./data/raw/series_76_electric_data.pdf
COPY data/processed/actuators.json ./data/processed/actuators.json
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 1000 app && mkdir -p /app/data/processed && chown -R app:app /app/data
USER app

EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
