from __future__ import annotations

import hashlib
import math
from collections import Counter
from io import BytesIO

from PIL import Image, ImageFile, UnidentifiedImageError

from plex_poster_healer.config import ScanThresholds
from plex_poster_healer.models import CheckResult

ImageFile.LOAD_TRUNCATED_IMAGES = False


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _largest_color_ratio(image: Image.Image) -> float:
    sample = image.convert("RGB")
    sample.thumbnail((128, 128))
    pixels = [sample.getpixel((x, y)) for y in range(sample.height) for x in range(sample.width)]
    if not pixels:
        return 1.0
    rounded = [(r // 16, g // 16, b // 16) for r, g, b in pixels]
    most_common = Counter(rounded).most_common(1)[0][1]
    return most_common / len(rounded)


def validate_image_bytes(
    data: bytes,
    thresholds: ScanThresholds,
    expected_poster: bool = True,
) -> CheckResult:
    reasons: list[str] = []
    if not data:
        return CheckResult(ok=False, reasons=["zero-byte image"])

    try:
        with Image.open(BytesIO(data)) as image:
            image.load()
            detected_type = (image.format or "").lower() or None
            if detected_type not in {"jpeg", "png", "webp", "ppm"}:
                reasons.append("invalid content type")
            width, height = image.size
            entropy = shannon_entropy(image.convert("L").tobytes())
            color_ratio = _largest_color_ratio(image)

            if width < thresholds.min_width or height < thresholds.min_height:
                reasons.append(f"dimensions too small ({width}x{height})")

            if expected_poster:
                ratio = width / height if height else 0
                lower = thresholds.poster_aspect_ratio - thresholds.aspect_ratio_tolerance
                upper = thresholds.poster_aspect_ratio + thresholds.aspect_ratio_tolerance
                if ratio < lower or ratio > upper:
                    reasons.append(f"aspect ratio outside poster bounds ({ratio:.2f})")

            if entropy < thresholds.min_entropy:
                reasons.append(f"entropy too low ({entropy:.2f})")

            if color_ratio > thresholds.max_single_color_ratio:
                reasons.append(f"large blank or near-solid region detected ({color_ratio:.2%})")

            return CheckResult(
                ok=not reasons,
                reasons=reasons,
                width=width,
                height=height,
                entropy=entropy,
                content_type=detected_type,
                sha256=sha256_bytes(data),
            )
    except (UnidentifiedImageError, OSError) as exc:
        reasons.append(f"decode failure: {exc.__class__.__name__}")
        return CheckResult(
            ok=False,
            reasons=reasons,
            sha256=sha256_bytes(data),
        )
