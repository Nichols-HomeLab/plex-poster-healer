# plex-poster-healer

`plex-poster-healer` scans Plex libraries for broken poster artwork, backs up the current poster, and repairs bad artwork with local posters, Plex metadata posters, TMDb, TVDB, or IMDb replacements. This repository is set up as an MVP focused on the core scan/heal workflow in Docker or a local Python environment.

## MVP scope

This version supports:

- Plex connection with `plexapi`
- Poster download and validation
- Backups before replacement
- Replacement from local posters, Plex metadata posters, TMDb, TVDB, or IMDb
- CLI commands for `scan`, `heal`, `backup`, and `restore`
- JSON and HTML reports
- Docker and `docker-compose` setup
- Best-effort OpenCV/OpenCL image path for iGPU-backed poster checks
- GitHub Actions workflow to publish `ghcr.io/<owner>/<repo>:latest`

Deferred for later iterations:

- Plex alternate poster selection from existing metadata
- fanart.tv support
- OCR/title matching
- richer visual glitch heuristics for banding, block artifacts, and partial corruption
- web UI, notifications, Prometheus, and SQLite history

## Project layout

```text
src/plex_poster_healer/
  cli.py
  config.py
  healer.py
  image_checks.py
  models.py
  plex_client.py
  reporting.py
  providers/
    base.py
    local_assets.py
    tmdb.py
tests/
  fixtures/
```

## Configuration

Copy `.env.example` to `.env` if you want environment-based configuration. The main runtime config lives in YAML.

Example:

```yaml
plex_url: http://plex:32400
plex_token: your-plex-token
tmdb_api_key: your-tmdb-api-key
tvdb_api_key: your-tvdb-api-key
tvdb_pin: optional-tvdb-pin
imdb_api_key: your-imdb-api-key
imdb_data_set_id: your-imdb-dataset-id
imdb_revision_id: your-imdb-revision-id
imdb_asset_id: your-imdb-asset-id
imdb_region: us-east-1
image_backend: opencv
prefer_opencl: true
backup_dir: /app/data/backups
assets_dir: /app/data/assets
cache_dir: /app/data/cache
reports_dir: /app/data/reports
preferred_source_order:
  - local_backup
  - local_posters
  - plex_metadata
  - tmdb
  - tvdb
  - imdb
scan_thresholds:
  min_width: 300
  min_height: 450
  poster_aspect_ratio: 0.6667
  aspect_ratio_tolerance: 0.18
  min_entropy: 2.5
  max_single_color_ratio: 0.72
```

## Local asset layout

```text
assets/
  Movie Name (2024)/
    poster.jpg
  Show Name/
    poster.jpg
    Season01.jpg
```

## Usage

Install locally:

```bash
pip install -e .[dev]
```

Run a scan:

```bash
plex-poster-healer --config config.example.yaml scan
```

Run heal mode without changing Plex:

```bash
plex-poster-healer --config config.example.yaml --dry-run heal
```

Run actual healing for one library:

```bash
plex-poster-healer --config config.example.yaml --library Movies heal
```

Back up posters:

```bash
plex-poster-healer --config config.example.yaml backup
```

Restore from backups:

```bash
plex-poster-healer --config config.example.yaml restore
```

Useful filters:

- `--library Movies`
- `--item-type movie`
- `--title "Alien"`
- `--recently-added-only`
- `--dry-run`

## Docker

Build and run:

```bash
docker compose build
docker compose run --rm plex-poster-healer
```

For nightly scans, run the container from cron or a scheduler with the `scan` command. Persisted volumes keep backups, cache, reports, and local assets outside the container.

## Reports

Each run writes:

- a JSON report to the configured `reports_dir`
- an HTML report to the configured `reports_dir`

The report includes the item scanned, failure reasons, backup location, replacement source, and replacement path.

## Provider notes

- `plex_metadata` uses Plex's own available poster list via `item.posters()`.
- `local_posters` uses the local asset layout above.
- `tvdb` uses a TVDB API key and optional subscriber PIN.
- `imdb` uses IMDb's official API on AWS Data Exchange, which requires an IMDb API key plus `data-set-id`, `revision-id`, and `asset-id`, along with valid AWS credentials in the runtime environment.

## GitHub Container Image

The workflow at [.github/workflows/publish-docker.yml](/home/ubuntu/plex-poster-healer/.github/workflows/publish-docker.yml) builds the repository Dockerfile on pushes to `main` and publishes:

- `ghcr.io/<owner>/<repo>:latest`
- `ghcr.io/<owner>/<repo>:sha-<commit>`

## iGPU Notes

`docker-compose.yml` now mounts `/dev/dri` to match your Plex stack and defaults the healer to `image_backend: opencv`. When OpenCV can see an OpenCL-capable Intel runtime, the image checks use that path; otherwise they fall back to CPU safely. For Docker hosts, the practical requirement is that the node exposes a usable `/dev/dri` render device and the container has the matching runtime libraries.

## Tests

Run:

```bash
pytest
```

The test suite covers:

- image validity and corruption checks
- low entropy rejection
- provider fallback priority behavior
