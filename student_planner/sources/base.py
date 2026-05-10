from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from student_planner.domain.models import CurriculumVersion, Program


@dataclass(frozen=True)
class SourceSnapshot:
    source_name: str
    source_url: str
    retrieved_at_utc: str
    content_path: str
    content_sha256: str


class CurriculumSource(Protocol):
    source_name: str

    def fetch(self, program: Program) -> SourceSnapshot:
        """Fetch source data and persist a raw snapshot."""

    def parse(self, snapshot: SourceSnapshot, program: Program) -> CurriculumVersion:
        """Parse a raw snapshot into a normalized curriculum draft."""

