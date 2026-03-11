from __future__ import annotations

from pathlib import Path
from typing import Iterable

import requests
from plexapi.server import PlexServer

from plex_poster_healer.config import Settings


class PlexClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.server = PlexServer(settings.plex_url, settings.plex_token, timeout=settings.request_timeout)
        self.session = requests.Session()
        self.session.headers.update({"X-Plex-Token": settings.plex_token})

    def iter_items(
        self,
        library: str | None = None,
        item_type: str | None = None,
        title: str | None = None,
        recently_added_only: bool = False,
    ) -> Iterable:
        sections = [self.server.library.section(library)] if library else self.server.library.sections()
        for section in sections:
            items = section.recentlyAdded() if recently_added_only else section.all()
            for item in items:
                if item_type and item.type != item_type:
                    continue
                if title and title.lower() not in item.title.lower():
                    continue
                yield section.title, item

    def download_artwork(self, item, kind: str = "poster") -> tuple[bytes | None, str | None]:
        art_path = getattr(item, "thumb", None) if kind == "poster" else getattr(item, "art", None)
        if not art_path:
            return None, None
        url = self.server.url(art_path, includeToken=True)
        response = self.session.get(url, timeout=self.settings.scan_thresholds.timeout_seconds)
        response.raise_for_status()
        return response.content, response.headers.get("Content-Type")

    def upload_poster(self, item, image_path: Path) -> None:
        item.uploadPoster(filepath=str(image_path))

    def item_guid(self, item, provider: str) -> str | None:
        guids = getattr(item, "guids", None) or []
        for guid in guids:
            value = getattr(guid, "id", "")
            if value.startswith(f"{provider}://"):
                return value.split(f"{provider}://", 1)[1]
        return None

    def download_url(self, url: str, timeout: int | None = None) -> tuple[bytes, str | None]:
        response = self.session.get(url, timeout=timeout or self.settings.scan_thresholds.timeout_seconds)
        response.raise_for_status()
        return response.content, response.headers.get("Content-Type")
