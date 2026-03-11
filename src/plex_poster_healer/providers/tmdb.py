from __future__ import annotations

from pathlib import Path

import requests

from plex_poster_healer.config import Settings
from plex_poster_healer.models import ArtworkCandidate
from plex_poster_healer.providers.base import ArtworkProvider


class TMDbProvider(ArtworkProvider):
    source_name = "tmdb"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.tmdb_api_key
        self.cache_dir = settings.cache_dir / "tmdb"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.params = {"api_key": self.api_key}

    def get_candidates(self, item) -> list[ArtworkCandidate]:
        if not self.api_key:
            return []
        tmdb_id = None
        for guid in getattr(item, "guids", None) or []:
            guid_id = getattr(guid, "id", "")
            if guid_id.startswith("tmdb://"):
                tmdb_id = guid_id.split("tmdb://", 1)[1]
                break
        if not tmdb_id:
            return []

        media_type = "movie" if item.type == "movie" else "tv"
        response = self.session.get(
            f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/images",
            timeout=15,
        )
        response.raise_for_status()
        posters = response.json().get("posters", [])
        if not posters:
            return []

        candidates: list[ArtworkCandidate] = []
        for index, poster in enumerate(
            sorted(posters, key=lambda value: (value.get("width", 0), value.get("vote_average", 0)), reverse=True)
        ):
            file_path = poster.get("file_path")
            if not file_path:
                continue
            image_url = f"https://image.tmdb.org/t/p/original{file_path}"
            image_response = requests.get(image_url, timeout=20)
            image_response.raise_for_status()
            target = self.cache_dir / f"{media_type}_{tmdb_id}_{index}{Path(file_path).suffix or '.jpg'}"
            target.write_bytes(image_response.content)
            candidates.append(
                ArtworkCandidate(
                    source=self.source_name,
                    path=target,
                    width=poster.get("width"),
                    height=poster.get("height"),
                    score=(2, poster.get("width", 0)),
                    metadata={"tmdb_id": tmdb_id, "vote_average": poster.get("vote_average")},
                )
            )
            if len(candidates) >= 3:
                break
        return candidates

