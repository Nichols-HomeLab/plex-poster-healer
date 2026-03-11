from __future__ import annotations

import hashlib
import math
from collections import Counter
from io import BytesIO

from PIL import Image, ImageFile, UnidentifiedImageError

from plex_poster_healer.config import ScanThresholds
from plex_poster_healer.models import CheckResult

ImageFile.LOAD_TRUNCATED_IMAGES = False

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - optional at import time
    cv2 = None
    np = None


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


def _largest_color_ratio_array(image) -> float:
    if image.size == 0:
        return 1.0
    height, width = image.shape[:2]
    scale = min(128 / max(width, 1), 128 / max(height, 1), 1.0)
    resized = cv2.resize(image, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    pixels = rgb.reshape(-1, 3)
    rounded = [(int(r) // 16, int(g) // 16, int(b) // 16) for r, g, b in pixels]
    most_common = Counter(rounded).most_common(1)[0][1]
    return most_common / len(rounded)


def _sniff_content_type(data: bytes) -> str | None:
    if data.startswith(b"\xFF\xD8\xFF"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith((b"P3", b"P6")):
        return "ppm"
    return None


def describe_acceleration(backend: str, prefer_opencl: bool) -> str:
    if backend == "pillow":
        return "backend=pillow, opencl=disabled"
    if cv2 is None:
        return "backend=pillow-fallback, opencl=unavailable"
    if prefer_opencl:
        cv2.ocl.setUseOpenCL(True)
    using_opencl = bool(prefer_opencl and cv2.ocl.haveOpenCL() and cv2.ocl.useOpenCL())
    return f"backend=opencv, opencl={'enabled' if using_opencl else 'disabled'}"


def _validate_with_opencv(
    data: bytes,
    thresholds: ScanThresholds,
    expected_poster: bool,
) -> CheckResult:
    reasons: list[str] = []
    detected_type = _sniff_content_type(data)
    if detected_type not in {"jpeg", "png", "webp", "ppm"}:
        reasons.append("invalid content type")

    encoded = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        return CheckResult(ok=False, reasons=["decode failure: OpenCV"], sha256=sha256_bytes(data))

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    entropy = shannon_entropy(gray.tobytes())
    color_ratio = _largest_color_ratio_array(image)

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


def validate_image_bytes(
    data: bytes,
    thresholds: ScanThresholds,
    expected_poster: bool = True,
    backend: str = "auto",
    prefer_opencl: bool = True,
) -> CheckResult:
    reasons: list[str] = []
    if not data:
        return CheckResult(ok=False, reasons=["zero-byte image"])

    if backend in {"auto", "opencv"} and cv2 is not None and np is not None:
        if prefer_opencl:
            cv2.ocl.setUseOpenCL(True)
        return _validate_with_opencv(data, thresholds, expected_poster)

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
