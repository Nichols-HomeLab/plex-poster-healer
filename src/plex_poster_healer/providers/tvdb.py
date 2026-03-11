from __future__ import annotations

from pathlib import Path

import requests

from plex_poster_healer.config import Settings
from plex_poster_healer.models import ArtworkCandidate
from plex_poster_healer.providers.base import ArtworkProvider


class TVDbProvider(ArtworkProvider):
    source_name = "tvdb"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.tvdb_api_key
        self.pin = settings.tvdb_pin
        self.cache_dir = settings.cache_dir / "tvdb"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self._token: str | None = None

    def _login(self) -> str | None:
        if self._token or not self.api_key:
            return self._token
        payload = {"apikey": self.api_key}
        if self.pin:
            payload["pin"] = self.pin
        response = self.session.post("https://api4.thetvdb.com/v4/login", json=payload, timeout=20)
        response.raise_for_status()
        self._token = response.json().get("data", {}).get("token")
        if self._token:
            self.session.headers["Authorization"] = f"Bearer {self._token}"
        return self._token

    def get_candidates(self, item) -> list[ArtworkCandidate]:
        token = self._login()
        if not token:
            return []
        tvdb_id = None
        for guid in getattr(item, "guids", None) or []:
            guid_id = getattr(guid, "id", "")
            if guid_id.startswith("tvdb://"):
                tvdb_id = guid_id.split("tvdb://", 1)[1]
                break
        if not tvdb_id:
            return []

        entity = "movies" if item.type == "movie" else "series"
        response = self.session.get(f"https://api4.thetvdb.com/v4/{entity}/{tvdb_id}/extended", timeout=20)
        response.raise_for_status()
        data = response.json().get("data", {})

        artworks = data.get("artworks", []) or []
        image_urls = [artwork.get("image") for artwork in artworks if artwork.get("image")]
        image_urls.extend([data.get("image"), data.get("thumbnail")])

        seen: set[str] = set()
        candidates: list[ArtworkCandidate] = []
        for index, image_url in enumerate(url for url in image_urls if url and url not in seen):
            seen.add(image_url)
            image_response = self.session.get(image_url, timeout=20)
            image_response.raise_for_status()
            target = self.cache_dir / f"{entity}_{tvdb_id}_{index}{Path(image_url).suffix or '.jpg'}"
            target.write_bytes(image_response.content)
            candidates.append(
                ArtworkCandidate(
                    source=self.source_name,
                    path=target,
                    score=(2, len(image_response.content)),
                    metadata={"tvdb_id": tvdb_id, "image_url": image_url},
                )
            )
            if len(candidates) >= 3:
                break
        return candidates

