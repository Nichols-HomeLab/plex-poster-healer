from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from plex_poster_healer.config import Settings
from plex_poster_healer.healer import PosterHealer
from plex_poster_healer.models import ArtworkCandidate
from plex_poster_healer.providers.plex_metadata import PlexMetadataProvider


class FakePlex:
    def __init__(self, items):
        self._items = items
        self.uploaded = []

    def iter_items(self, **_kwargs):
        yield from self._items

    def download_artwork(self, item, kind="poster"):
        return item.current_bytes, "image/jpeg"

    def upload_poster(self, item, image_path):
        self.uploaded.append((item.ratingKey, Path(image_path)))


class StubProvider:
    def __init__(self, candidates: list[ArtworkCandidate] | None):
        self.candidates = candidates or []

    def get_candidates(self, item):
        return self.candidates


class RaisingProvider:
    def get_candidates(self, item):
        raise RuntimeError("provider boom")


def make_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        plex_url="http://example",
        plex_token="token",
        backup_dir=tmp_path / "backups",
        assets_dir=tmp_path / "assets",
        cache_dir=tmp_path / "cache",
        reports_dir=tmp_path / "reports",
    )
    settings.ensure_directories()
    return settings


def test_heal_prefers_local_assets_before_tmdb(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    poster = tmp_path / "candidate.png"
    image = Image.new("RGB", (300, 450))
    for x in range(300):
        for y in range(450):
            image.putpixel((x, y), ((x * 11) % 255, (y * 7) % 255, ((x + y) * 5) % 255))
    image.save(poster)
    item = SimpleNamespace(
        title="Movie",
        type="movie",
        ratingKey="123",
        thumb="/library/metadata/123/thumb",
        current_bytes=b"invalid",
    )
    fake_plex = FakePlex([("Movies", item)])
    healer = PosterHealer(settings, plex=fake_plex)
    healer.providers = {
        "local_assets": StubProvider([ArtworkCandidate(source="local_assets", path=poster, score=(5, 100))]),
        "local_posters": StubProvider([ArtworkCandidate(source="local_assets", path=poster, score=(5, 100))]),
        "plex_metadata": StubProvider([]),
        "tmdb": StubProvider([ArtworkCandidate(source="tmdb", path=poster, score=(1, 50))]),
        "tvdb": StubProvider([]),
        "imdb": StubProvider([]),
    }

    results = healer.heal(dry_run=True)

    assert results[0].replacement_source == "local_assets"
    assert results[0].status == "dry-run"


def test_heal_skips_invalid_high_priority_candidate_and_uses_next(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    good_poster = tmp_path / "good.png"
    bad_poster = tmp_path / "bad.jpg"
    image = Image.new("RGB", (300, 450))
    for x in range(300):
        for y in range(450):
            image.putpixel((x, y), ((x * 13) % 255, (y * 9) % 255, ((x + y) * 7) % 255))
    image.save(good_poster)
    bad_poster.write_text("not-an-image")
    item = SimpleNamespace(
        title="Movie",
        type="movie",
        ratingKey="123",
        thumb="/library/metadata/123/thumb",
        current_bytes=b"invalid",
    )
    fake_plex = FakePlex([("Movies", item)])
    healer = PosterHealer(settings, plex=fake_plex)
    healer.providers = {
        "local_assets": StubProvider([]),
        "local_posters": StubProvider([]),
        "plex_metadata": StubProvider([ArtworkCandidate(source="plex_metadata", path=bad_poster, score=(9, 1000))]),
        "tmdb": StubProvider([ArtworkCandidate(source="tmdb", path=good_poster, score=(1, 50))]),
        "tvdb": StubProvider([]),
        "imdb": StubProvider([]),
    }

    results = healer.heal(dry_run=True)

    assert results[0].replacement_source == "tmdb"
    assert any("plex_metadata invalid" in reason for reason in results[0].reasons)


def test_plex_metadata_provider_keeps_absolute_urls() -> None:
    fake_plex = SimpleNamespace(server=SimpleNamespace(url=lambda key, includeToken=True: f"http://plex.local{key}"))
    absolute = PlexMetadataProvider._resolve_url(fake_plex, "https://image.tmdb.org/t/p/original/test.jpg")
    relative = PlexMetadataProvider._resolve_url(fake_plex, "/library/metadata/123/thumb")

    assert absolute == "https://image.tmdb.org/t/p/original/test.jpg"
    assert relative == "http://plex.local/library/metadata/123/thumb"


def test_heal_skips_provider_exceptions(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    good_poster = tmp_path / "good.png"
    image = Image.new("RGB", (300, 450))
    for x in range(300):
        for y in range(450):
            image.putpixel((x, y), ((x * 13) % 255, (y * 9) % 255, ((x + y) * 7) % 255))
    image.save(good_poster)
    item = SimpleNamespace(
        title="Movie",
        type="movie",
        ratingKey="123",
        thumb="/library/metadata/123/thumb",
        current_bytes=b"invalid",
    )
    fake_plex = FakePlex([("Movies", item)])
    healer = PosterHealer(settings, plex=fake_plex)
    healer.providers = {
        "local_assets": StubProvider([]),
        "local_posters": StubProvider([]),
        "plex_metadata": RaisingProvider(),
        "tmdb": StubProvider([ArtworkCandidate(source="tmdb", path=good_poster, score=(1, 50))]),
        "tvdb": StubProvider([]),
        "imdb": StubProvider([]),
    }

    results = healer.heal(dry_run=True)

    assert results[0].replacement_source == "tmdb"
    assert results[0].status == "dry-run"
