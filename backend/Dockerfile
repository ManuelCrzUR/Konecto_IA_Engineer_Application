FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# poppler-utils provides `pdfimages`, which crops.py uses to pull the embedded page
# images out of the PDF (needed only when the data is re-extracted, D-49).
# opencv-python-headless only (the [tool.uv] override in pyproject.toml drops
# rapidocr's GUI opencv), so no X11/GL libs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

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
