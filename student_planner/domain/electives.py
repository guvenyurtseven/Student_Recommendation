from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from student_planner.domain.models import RequirementType


class ElectiveCategory(StrEnum):
    TECHNICAL = "technical_elective"
    RESTRICTED = "restricted_elective"
    NONTECHNICAL = "nontechnical_elective"
    FREE = "free_elective"


DEFAULT_ECTS_BY_ELECTIVE_CATEGORY = MappingProxyType(
    {
        ElectiveCategory.TECHNICAL: 6.5,
        ElectiveCategory.RESTRICTED: 6.0,
        ElectiveCategory.NONTECHNICAL: 5.5,
        ElectiveCategory.FREE: 5.0,
    }
)

DIFFICULTY_RANK_BY_ELECTIVE_CATEGORY = MappingProxyType(
    {
        ElectiveCategory.TECHNICAL: 4,
        ElectiveCategory.RESTRICTED: 3,
        ElectiveCategory.NONTECHNICAL: 2,
        ElectiveCategory.FREE: 1,
    }
)

REQUIREMENT_TYPE_BY_ELECTIVE_CATEGORY = MappingProxyType(
    {
        ElectiveCategory.TECHNICAL: RequirementType.TECHNICAL_ELECTIVE_POOL,
        ElectiveCategory.RESTRICTED: RequirementType.RESTRICTED_ELECTIVE_POOL,
        ElectiveCategory.NONTECHNICAL: RequirementType.NONTECHNICAL_ELECTIVE_POOL,
        ElectiveCategory.FREE: RequirementType.FREE_ELECTIVE_POOL,
    }
)

ELECTIVE_CATEGORY_BY_REQUIREMENT_TYPE = MappingProxyType(
    {
        requirement_type: category
        for category, requirement_type in REQUIREMENT_TYPE_BY_ELECTIVE_CATEGORY.items()
    }
)

PLACEHOLDER_CODE_BY_ELECTIVE_CATEGORY = MappingProxyType(
    {
        ElectiveCategory.TECHNICAL: "TECHNICAL_ELECTIVE",
        ElectiveCategory.RESTRICTED: "RESTRICTED_ELECTIVE",
        ElectiveCategory.NONTECHNICAL: "NONTECHNICAL_ELECTIVE",
        ElectiveCategory.FREE: "FREE_ELECTIVE",
    }
)


@dataclass(frozen=True)
class ElectiveIntent:
    category: ElectiveCategory | str
    wants_to_take: bool = True
    course_code: str | None = None
    requested_count: int = 1
    notes: str = ""

    def __post_init__(self) -> None:
        category = coerce_elective_category(self.category)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "wants_to_take", bool(self.wants_to_take))
        object.__setattr__(self, "course_code", normalize_optional_course_code(self.course_code))
        validate_positive_int(self.requested_count, "requested_count")
        object.__setattr__(self, "notes", self.notes.strip())

    @property
    def has_explicit_course(self) -> bool:
        return self.course_code is not None

    @property
    def default_ects(self) -> float:
        return DEFAULT_ECTS_BY_ELECTIVE_CATEGORY[self.category]

    @property
    def difficulty_rank(self) -> int:
        return DIFFICULTY_RANK_BY_ELECTIVE_CATEGORY[self.category]

    @property
    def requirement_type(self) -> RequirementType:
        return REQUIREMENT_TYPE_BY_ELECTIVE_CATEGORY[self.category]

    @property
    def placeholder_code(self) -> str:
        return PLACEHOLDER_CODE_BY_ELECTIVE_CATEGORY[self.category]

    @property
    def requires_course_selection_for_timetable(self) -> bool:
        return self.wants_to_take and not self.has_explicit_course


def coerce_elective_category(value: ElectiveCategory | str) -> ElectiveCategory:
    if isinstance(value, ElectiveCategory):
        return value
    if not isinstance(value, str):
        raise TypeError("elective category must be an ElectiveCategory or string.")
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "technical": ElectiveCategory.TECHNICAL,
        "technical_elective": ElectiveCategory.TECHNICAL,
        "technical_elective_pool": ElectiveCategory.TECHNICAL,
        "te": ElectiveCategory.TECHNICAL,
        "restricted": ElectiveCategory.RESTRICTED,
        "restricted_elective": ElectiveCategory.RESTRICTED,
        "restricted_elective_pool": ElectiveCategory.RESTRICTED,
        "re": ElectiveCategory.RESTRICTED,
        "non_technical": ElectiveCategory.NONTECHNICAL,
        "nontechnical": ElectiveCategory.NONTECHNICAL,
        "nontechnical_elective": ElectiveCategory.NONTECHNICAL,
        "non_technical_elective": ElectiveCategory.NONTECHNICAL,
        "nontechnical_elective_pool": ElectiveCategory.NONTECHNICAL,
        "nte": ElectiveCategory.NONTECHNICAL,
        "free": ElectiveCategory.FREE,
        "free_elective": ElectiveCategory.FREE,
        "free_elective_pool": ElectiveCategory.FREE,
        "fe": ElectiveCategory.FREE,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported elective category: {value!r}") from exc


def elective_category_for_requirement_type(requirement_type: RequirementType | str) -> ElectiveCategory | None:
    try:
        normalized = RequirementType(requirement_type)
    except ValueError:
        return None
    return ELECTIVE_CATEGORY_BY_REQUIREMENT_TYPE.get(normalized)


def normalize_optional_course_code(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("course_code must be a string or None.")
    cleaned = value.strip()
    if not cleaned:
        return None
    return normalize_display_course_code(cleaned)


def normalize_display_course_code(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().upper())
    if not normalized:
        raise ValueError("course_code cannot be empty.")
    if normalized.isdigit():
        return normalized

    match = re.match(r"^([A-Z]+)\s*(\d+[A-Z]?)$", normalized)
    if match:
        return f"{match.group(1)} {match.group(2)}"

    match = re.match(r"^(\d+)\s+(\d+[A-Z]?)$", normalized)
    if match:
        return f"{match.group(1)} {match.group(2)}"

    return normalized


def validate_positive_int(value: int, field_name: str) -> None:
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive.")
