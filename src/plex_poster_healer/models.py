from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ArtworkCandidate:
    source: str
    path: Path
    content_type: str | None = None
    width: int | None = None
    height: int | None = None
    score: tuple[int, int] = (0, 0)
    metadata: dict[str, Any] = field(default_factory=dict)
    cleanup: bool = False


@dataclass(slots=True)
class CheckResult:
    ok: bool
    reasons: list[str]
    width: int | None = None
    height: int | None = None
    entropy: float | None = None
    content_type: str | None = None
    sha256: str | None = None


@dataclass(slots=True)
class ScanRecord:
    rating_key: str
    title: str
    library: str
    item_type: str
    poster_url: str | None
    status: str
    reasons: list[str]
    backup_path: str | None = None
    replacement_path: str | None = None
    replacement_source: str | None = None
    accepted_hash: str | None = None
