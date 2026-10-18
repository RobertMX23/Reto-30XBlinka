FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY agents ./agents
COPY data ./data
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
RUN useradd --create-home --uid 10001 blinka && mkdir -p /app/var && chown -R blinka:blinka /app
USER blinka
ENV PYTHONPATH=/app/src:/app
EXPOSE 8080
CMD ["uv", "run", "--no-dev", "python", "-m", "blinka.http_api"]
