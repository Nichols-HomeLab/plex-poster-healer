FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY tests /app/tests
RUN pip install --no-cache-dir .

RUN mkdir -p /app/config /app/data/backups /app/data/assets /app/data/cache /app/data/reports

CMD ["plex-poster-healer", "scan", "--config", "/app/config/config.yaml"]

