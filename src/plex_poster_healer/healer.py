from __future__ import annotations

import json
import logging
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from plex_poster_healer.config import Settings
from plex_poster_healer.image_checks import validate_image_bytes
from plex_poster_healer.models import ArtworkCandidate, ScanRecord
from plex_poster_healer.plex_client import PlexClient
from plex_poster_healer.providers import IMDbProvider, LocalAssetProvider, PlexMetadataProvider, TMDbProvider, TVDbProvider
from plex_poster_healer.reporting import ReportWriter

LOGGER = logging.getLogger(__name__)


class PosterHealer:
    def __init__(self, settings: Settings, plex: PlexClient | None = None) -> None:
        self.settings = settings
        self.plex = plex or PlexClient(settings)
        self.report_writer = ReportWriter(settings.reports_dir)
        self.hash_store_path = settings.cache_dir / "hashes.json"
        self.hash_store = self._load_hash_store()
        self.providers = {
            "local_assets": LocalAssetProvider(settings),
            "local_posters": LocalAssetProvider(settings),
            "plex_metadata": PlexMetadataProvider(settings, self.plex),
            "tmdb": TMDbProvider(settings),
            "tvdb": TVDbProvider(settings),
            "imdb": IMDbProvider(settings),
        }

    def _load_hash_store(self) -> dict:
        if self.hash_store_path.exists():
            return json.loads(self.hash_store_path.read_text())
        return {"known_bad": {}, "accepted": {}}

    def _save_hash_store(self) -> None:
        self.hash_store_path.write_text(json.dumps(self.hash_store, indent=2))

    def _extension_for_bytes(self, poster_bytes: bytes) -> str:
        try:
            from io import BytesIO

            with Image.open(BytesIO(poster_bytes)) as image:
                format_name = (image.format or "").lower()
        except (UnidentifiedImageError, OSError):
            format_name = ""
        return {
            "jpeg": ".jpg",
            "png": ".png",
            "webp": ".webp",
            "ppm": ".ppm",
        }.get(format_name, ".jpg")

    def backup_item(self, item, poster_bytes: bytes) -> Path:
        safe_title = "".join(ch for ch in item.title if ch.isalnum() or ch in " ._-").strip() or item.ratingKey
        folder = self.settings.backup_dir / item.type
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{safe_title}-{item.ratingKey}{self._extension_for_bytes(poster_bytes)}"
        path.write_bytes(poster_bytes)
        return path

    def restore_item(self, item) -> Path | None:
        folder = self.settings.backup_dir / item.type
        matches = sorted(folder.glob(f"*-{item.ratingKey}.*"))
        if not matches:
            return None
        item.uploadPoster(filepath=str(matches[-1]))
        return matches[-1]

    def scan(
        self,
        library: str | None = None,
        item_type: str | None = None,
        title: str | None = None,
        recently_added_only: bool = False,
    ) -> list[ScanRecord]:
        records: list[ScanRecord] = []
        for library_name, item in self.plex.iter_items(
            library=library,
            item_type=item_type,
            title=title,
            recently_added_only=recently_added_only,
        ):
            LOGGER.info("Scanning %s [%s]", item.title, item.type)
            try:
                poster_bytes, _content_type = self.plex.download_artwork(item, kind="poster")
            except Exception as exc:
                records.append(
                    ScanRecord(
                        rating_key=str(item.ratingKey),
                        title=item.title,
                        library=library_name,
                        item_type=item.type,
                        poster_url=getattr(item, "thumb", None),
                        status="failed",
                        reasons=[f"fetch failure: {exc.__class__.__name__}"],
                    )
                )
                continue

            if not poster_bytes:
                records.append(
                    ScanRecord(
                        rating_key=str(item.ratingKey),
                        title=item.title,
                        library=library_name,
                        item_type=item.type,
                        poster_url=getattr(item, "thumb", None),
                        status="failed",
                        reasons=["missing poster"],
                    )
                )
                continue

            check = validate_image_bytes(poster_bytes, self.settings.scan_thresholds)
            status = "ok" if check.ok else "failed"
            if check.sha256 and check.ok:
                self.hash_store["accepted"][check.sha256] = {"title": item.title, "rating_key": item.ratingKey}
            elif check.sha256:
                self.hash_store["known_bad"][check.sha256] = {"title": item.title, "rating_key": item.ratingKey}

            records.append(
                ScanRecord(
                    rating_key=str(item.ratingKey),
                    title=item.title,
                    library=library_name,
                    item_type=item.type,
                    poster_url=getattr(item, "thumb", None),
                    status=status,
                    reasons=check.reasons,
                    accepted_hash=check.sha256,
                )
            )
        self._save_hash_store()
        return records

    def _candidate_from_backup(self, item) -> ArtworkCandidate | None:
        folder = self.settings.backup_dir / item.type
        matches = sorted(folder.glob(f"*-{item.ratingKey}.*"))
        if not matches:
            return None
        return ArtworkCandidate(source="local_backup", path=matches[-1], score=(6, 0))

    def _iter_replacement_candidates(self, item) -> list[ArtworkCandidate]:
        ordered: list[ArtworkCandidate] = []
        for source in self.settings.preferred_source_order:
            if source == "local_backup":
                backup = self._candidate_from_backup(item)
                if backup:
                    ordered.append(backup)
                continue
            provider = self.providers.get(source)
            if not provider:
                continue
            ordered.extend(provider.get_candidates(item))
        ordered.sort(key=lambda candidate: candidate.score, reverse=True)
        return ordered

    def heal(
        self,
        library: str | None = None,
        item_type: str | None = None,
        title: str | None = None,
        recently_added_only: bool = False,
        dry_run: bool = False,
    ) -> list[ScanRecord]:
        scanned = self.scan(
            library=library,
            item_type=item_type,
            title=title,
            recently_added_only=recently_added_only,
        )
        rating_key_to_item = {
            str(item.ratingKey): (library_name, item)
            for library_name, item in self.plex.iter_items(
                library=library,
                item_type=item_type,
                title=title,
                recently_added_only=recently_added_only,
            )
        }

        for record in scanned:
            if record.status != "failed":
                continue
            _, item = rating_key_to_item[record.rating_key]
            poster_bytes, _ = self.plex.download_artwork(item, kind="poster")
            if poster_bytes:
                backup_path = self.backup_item(item, poster_bytes)
                record.backup_path = str(backup_path)

            replacement_found = False
            for candidate in self._iter_replacement_candidates(item):
                candidate_bytes = candidate.path.read_bytes()
                check = validate_image_bytes(candidate_bytes, self.settings.scan_thresholds)
                if not check.ok:
                    record.reasons.extend([f"{candidate.source} invalid: {reason}" for reason in check.reasons])
                    continue
                if check.sha256 and check.sha256 in self.hash_store["known_bad"]:
                    record.reasons.append(f"{candidate.source} skipped: known bad hash")
                    continue
                if dry_run:
                    record.status = "dry-run"
                else:
                    self.plex.upload_poster(item, candidate.path)
                    record.status = "healed"

                record.replacement_source = candidate.source
                record.replacement_path = str(candidate.path)
                record.accepted_hash = check.sha256
                if check.sha256:
                    self.hash_store["accepted"][check.sha256] = {
                        "title": item.title,
                        "rating_key": item.ratingKey,
                        "source": candidate.source,
                    }
                replacement_found = True
                break

            if not replacement_found:
                record.status = "unfixed"

        self._save_hash_store()
        return scanned

    def backup(
        self,
        library: str | None = None,
        item_type: str | None = None,
        title: str | None = None,
        recently_added_only: bool = False,
    ) -> list[ScanRecord]:
        records: list[ScanRecord] = []
        for library_name, item in self.plex.iter_items(
            library=library,
            item_type=item_type,
            title=title,
            recently_added_only=recently_added_only,
        ):
            poster_bytes, _ = self.plex.download_artwork(item, kind="poster")
            if not poster_bytes:
                records.append(
                    ScanRecord(
                        rating_key=str(item.ratingKey),
                        title=item.title,
                        library=library_name,
                        item_type=item.type,
                        poster_url=getattr(item, "thumb", None),
                        status="failed",
                        reasons=["missing poster"],
                    )
                )
                continue
            backup_path = self.backup_item(item, poster_bytes)
            records.append(
                ScanRecord(
                    rating_key=str(item.ratingKey),
                    title=item.title,
                    library=library_name,
                    item_type=item.type,
                    poster_url=getattr(item, "thumb", None),
                    status="backed_up",
                    reasons=[],
                    backup_path=str(backup_path),
                )
            )
        return records

    def restore(
        self,
        library: str | None = None,
        item_type: str | None = None,
        title: str | None = None,
        recently_added_only: bool = False,
        dry_run: bool = False,
    ) -> list[ScanRecord]:
        records: list[ScanRecord] = []
        for library_name, item in self.plex.iter_items(
            library=library,
            item_type=item_type,
            title=title,
            recently_added_only=recently_added_only,
        ):
            backup_path = self._candidate_from_backup(item)
            if not backup_path:
                records.append(
                    ScanRecord(
                        rating_key=str(item.ratingKey),
                        title=item.title,
                        library=library_name,
                        item_type=item.type,
                        poster_url=getattr(item, "thumb", None),
                        status="failed",
                        reasons=["no backup found"],
                    )
                )
                continue
            if dry_run:
                status = "dry-run"
            else:
                self.plex.upload_poster(item, backup_path.path)
                status = "restored"
            records.append(
                ScanRecord(
                    rating_key=str(item.ratingKey),
                    title=item.title,
                    library=library_name,
                    item_type=item.type,
                    poster_url=getattr(item, "thumb", None),
                    status=status,
                    reasons=[],
                    replacement_path=str(backup_path.path),
                    replacement_source="local_backup",
                )
            )
        return records
