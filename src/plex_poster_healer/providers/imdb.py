from __future__ import annotations

import json
from pathlib import Path

import boto3

from plex_poster_healer.config import Settings
from plex_poster_healer.models import ArtworkCandidate
from plex_poster_healer.providers.base import ArtworkProvider


class IMDbProvider(ArtworkProvider):
    source_name = "imdb"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.imdb_api_key
        self.data_set_id = settings.imdb_data_set_id
        self.revision_id = settings.imdb_revision_id
        self.asset_id = settings.imdb_asset_id
        self.region = settings.imdb_region
        self.cache_dir = settings.cache_dir / "imdb"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = boto3.client("dataexchange", region_name=self.region)

    def get_candidates(self, item) -> list[ArtworkCandidate]:
        if not all([self.api_key, self.data_set_id, self.revision_id, self.asset_id]):
            return []

        imdb_id = None
        for guid in getattr(item, "guids", None) or []:
            guid_id = getattr(guid, "id", "")
            if guid_id.startswith("imdb://"):
                imdb_id = guid_id.split("imdb://", 1)[1]
                break
        if not imdb_id:
            return []

        query = """
        query PosterQuery($id: ID!) {
          title(id: $id) {
            id
            titleText { text }
            primaryImage {
              url
              width
              height
            }
          }
        }
        """
        body = json.dumps({"query": query, "variables": {"id": imdb_id}})
        response = self.client.send_api_asset(
            DataSetId=self.data_set_id,
            RevisionId=self.revision_id,
            AssetId=self.asset_id,
            Method="POST",
            Path="/v1",
            Body=body,
            RequestHeaders={"x-api-key": self.api_key, "Content-Type": "application/json"},
        )
        payload = json.loads(response["Body"].read())
        primary = ((payload.get("data") or {}).get("title") or {}).get("primaryImage") or {}
        url = primary.get("url")
        if not url:
            return []

        import requests

        image_response = requests.get(url, timeout=20)
        image_response.raise_for_status()
        target = self.cache_dir / f"{imdb_id}{Path(url).suffix or '.jpg'}"
        target.write_bytes(image_response.content)
        return [
            ArtworkCandidate(
                source=self.source_name,
                path=target,
                width=primary.get("width"),
                height=primary.get("height"),
                score=(1, primary.get("width", 0) or 0),
                metadata={"imdb_id": imdb_id, "image_url": url},
            )
        ]
