from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class ScanThresholds(BaseModel):
    min_width: int = 300
    min_height: int = 450
    poster_aspect_ratio: float = 2 / 3
    aspect_ratio_tolerance: float = 0.18
    min_entropy: float = 2.5
    max_single_color_ratio: float = 0.72
    timeout_seconds: int = 15


class Settings(BaseModel):
    plex_url: str
    plex_token: str
    tmdb_api_key: str | None = None
    tvdb_api_key: str | None = None
    tvdb_pin: str | None = None
    imdb_api_key: str | None = None
    imdb_data_set_id: str | None = None
    imdb_revision_id: str | None = None
    imdb_asset_id: str | None = None
    imdb_region: str = "us-east-1"
    backup_dir: Path = Path("backups")
    assets_dir: Path | None = None
    cache_dir: Path = Path("cache")
    reports_dir: Path = Path("reports")
    request_timeout: int = 20
    preferred_source_order: list[
        Literal["local_backup", "local_assets", "local_posters", "plex_metadata", "tmdb", "tvdb", "imdb"]
    ] = Field(
        default_factory=lambda: ["local_backup", "local_posters", "plex_metadata", "tmdb", "tvdb", "imdb"]
    )
    scan_thresholds: ScanThresholds = Field(default_factory=ScanThresholds)

    def ensure_directories(self) -> None:
        for path in [self.backup_dir, self.cache_dir, self.reports_dir]:
            path.mkdir(parents=True, exist_ok=True)
        if self.assets_dir:
            self.assets_dir.mkdir(parents=True, exist_ok=True)


def load_settings(config_path: str | Path | None = None) -> Settings:
    load_dotenv()
    file_path = Path(
        config_path
        or os.getenv("PPH_CONFIG_PATH")
        or "config.yaml"
    )
    data: dict = {}
    if file_path.exists():
        data = yaml.safe_load(file_path.read_text()) or {}

    env_overrides = {
        "plex_url": os.getenv("PPH_PLEX_URL"),
        "plex_token": os.getenv("PPH_PLEX_TOKEN"),
        "tmdb_api_key": os.getenv("PPH_TMDB_API_KEY"),
        "tvdb_api_key": os.getenv("PPH_TVDB_API_KEY"),
        "tvdb_pin": os.getenv("PPH_TVDB_PIN"),
        "imdb_api_key": os.getenv("PPH_IMDB_API_KEY"),
        "imdb_data_set_id": os.getenv("PPH_IMDB_DATA_SET_ID"),
        "imdb_revision_id": os.getenv("PPH_IMDB_REVISION_ID"),
        "imdb_asset_id": os.getenv("PPH_IMDB_ASSET_ID"),
        "imdb_region": os.getenv("PPH_IMDB_REGION"),
    }
    merged = {**data, **{k: v for k, v in env_overrides.items() if v}}
    settings = Settings.model_validate(merged)
    settings.ensure_directories()
    return settings
