from __future__ import annotations

from pathlib import Path

from plex_poster_healer.config import Settings
from plex_poster_healer.models import ArtworkCandidate
from plex_poster_healer.plex_client import PlexClient
from plex_poster_healer.providers.base import ArtworkProvider


class PlexMetadataProvider(ArtworkProvider):
    source_name = "plex_metadata"

    def __init__(self, settings: Settings, plex: PlexClient) -> None:
        self.settings = settings
        self.plex = plex
        self.cache_dir = settings.cache_dir / "plex_metadata"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_candidates(self, item) -> list[ArtworkCandidate]:
        posters = getattr(item, "posters", None)
        if not callable(posters):
            return []

        candidates: list[ArtworkCandidate] = []
        for index, poster in enumerate(posters()):
            if getattr(poster, "selected", False):
                continue
            key = getattr(poster, "key", None)
            if not key:
                continue
            url = self.plex.server.url(key, includeToken=True)
            poster_bytes, _ = self.plex.download_url(url)
            suffix = Path(key).suffix or ".jpg"
            target = self.cache_dir / f"{item.ratingKey}_{index}{suffix}"
            target.write_bytes(poster_bytes)
            candidates.append(
                ArtworkCandidate(
                    source=self.source_name,
                    path=target,
                    score=(4, len(poster_bytes)),
                    metadata={"provider": getattr(poster, "provider", None), "key": key},
                )
            )
            if len(candidates) >= 5:
                break
        return candidates

