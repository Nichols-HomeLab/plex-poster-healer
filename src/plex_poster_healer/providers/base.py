from __future__ import annotations

from abc import ABC, abstractmethod

from plex_poster_healer.models import ArtworkCandidate


class ArtworkProvider(ABC):
    source_name: str

    @abstractmethod
    def get_candidates(self, item) -> list[ArtworkCandidate]:
        raise NotImplementedError
