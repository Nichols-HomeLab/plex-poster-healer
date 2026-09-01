FROM python:3.14-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 ocl-icd-libopencl1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY tests /app/tests
RUN pip install --no-cache-dir .

RUN mkdir -p /app/config /app/data/backups /app/data/assets /app/data/cache /app/data/reports

CMD ["plex-poster-healer", "scan", "--config", "/app/config/config.yaml"]
