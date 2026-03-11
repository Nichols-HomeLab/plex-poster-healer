from pathlib import Path

from PIL import Image

from plex_poster_healer.config import ScanThresholds
from plex_poster_healer.image_checks import validate_image_bytes


def test_valid_image_fixture_is_accepted(tmp_path) -> None:
    image = Image.new("RGB", (300, 450))
    for x in range(300):
        for y in range(450):
            image.putpixel((x, y), ((x * 7) % 255, (y * 5) % 255, ((x + y) * 3) % 255))
    path = tmp_path / "good.png"
    image.save(path)
    data = path.read_bytes()
    thresholds = ScanThresholds(min_width=1, min_height=1, min_entropy=1.0, max_single_color_ratio=0.95)
    result = validate_image_bytes(data, thresholds)
    assert result.ok is True
    assert result.reasons == []


def test_invalid_image_fixture_is_rejected() -> None:
    data = (Path(__file__).parent / "fixtures" / "bad_poster.jpg").read_bytes()
    result = validate_image_bytes(data, ScanThresholds())
    assert result.ok is False
    assert any("invalid content type" in reason or "decode failure" in reason for reason in result.reasons)


def test_low_entropy_image_is_rejected() -> None:
    image = Image.new("RGB", (300, 450), color=(20, 20, 20))
    tmp = Path(__file__).parent / "fixtures" / "generated-low-entropy.png"
    image.save(tmp)
    try:
        result = validate_image_bytes(tmp.read_bytes(), ScanThresholds(min_entropy=3.0, max_single_color_ratio=0.5))
        assert result.ok is False
        assert any("entropy too low" in reason for reason in result.reasons)
    finally:
        tmp.unlink(missing_ok=True)
