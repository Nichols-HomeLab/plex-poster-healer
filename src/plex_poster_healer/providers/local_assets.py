from __future__ import annotations

import re
from pathlib import Path

from plex_poster_healer.config import Settings
from plex_poster_healer.models import ArtworkCandidate
from plex_poster_healer.providers.base import ArtworkProvider


def _safe_name(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "", value).strip()


class LocalAssetProvider(ArtworkProvider):
    source_name = "local_posters"

    def __init__(self, settings: Settings) -> None:
        self.assets_dir = settings.assets_dir

    def get_candidates(self, item) -> list[ArtworkCandidate]:
        if not self.assets_dir:
            return []

        title = _safe_name(item.title)
        year = getattr(item, "year", None)
        if item.type == "movie":
            base = self.assets_dir / f"{title} ({year})" if year else self.assets_dir / title
            candidates = [base / "poster.jpg", base / "poster.png"]
        elif item.type == "show":
            base = self.assets_dir / title
            candidates = [base / "poster.jpg", base / "poster.png"]
        elif item.type == "season":
            show_title = _safe_name(getattr(item.show(), "title", "Unknown Show"))
            index = getattr(item, "index", 0)
            base = self.assets_dir / show_title
            candidates = [base / f"Season{index:02d}.jpg", base / f"Season{index:02d}.png"]
        else:
            return []

        for candidate in candidates:
            if candidate.exists():
                return [ArtworkCandidate(source=self.source_name, path=candidate, score=(5, 0))]
        return []
