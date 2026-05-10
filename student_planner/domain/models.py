from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ReviewStatus(StrEnum):
    SCRAPED = "scraped"
    NEEDS_REVIEW = "needs_review"
    REVIEWED = "reviewed"
    CORRECTED = "corrected"
    DEPRECATED = "deprecated"


class RequirementType(StrEnum):
    REQUIRED_COURSE = "required_course"
    COURSE_CHOICE = "course_choice"
    TECHNICAL_ELECTIVE_POOL = "technical_elective_pool"
    RESTRICTED_ELECTIVE_POOL = "restricted_elective_pool"
    NONTECHNICAL_ELECTIVE_POOL = "nontechnical_elective_pool"
    FREE_ELECTIVE_POOL = "free_elective_pool"
    SUMMER_PRACTICE = "summer_practice"
    OTHER = "other"


@dataclass(frozen=True)
class Program:
    abbr: str
    catalog_program_id: str
    name_en: str
    name_tr: str
    faculty: str
    is_active_undergraduate: bool = True


@dataclass(frozen=True)
class Course:
    numeric_code: str | None
    subject_code: str
    course_number: int
    display_code: str
    title_en: str = ""
    title_tr: str = ""
    level: str = "undergraduate"


@dataclass(frozen=True)
class CurriculumRequirementOption:
    id: int
    course: Course | None = None
    option_label: str | None = None
    option_group: str | None = None
    is_required_option: bool = True

    @property
    def course_code(self) -> str | None:
        return self.course.display_code if self.course else None


@dataclass(frozen=True)
class CurriculumRequirementRecord:
    id: int
    requirement_type: RequirementType
    label: str
    recommended_year: int | None = None
    recommended_term: str | None = None
    course_count_min: int | None = None
    credits_min: float | None = None
    ects_min: float | None = None
    sort_order: int | None = None
    review_status: ReviewStatus = ReviewStatus.SCRAPED
    options: tuple[CurriculumRequirementOption, ...] = field(default_factory=tuple)

    @property
    def option_course_codes(self) -> tuple[str, ...]:
        return tuple(option.course_code for option in self.options if option.course_code)

    @property
    def has_concrete_course_options(self) -> bool:
        return bool(self.option_course_codes)


@dataclass(frozen=True)
class CurriculumSnapshot:
    program: Program
    version_id: int
    version_label: str
    is_latest: bool
    review_status: ReviewStatus
    requirements: tuple[CurriculumRequirementRecord, ...]

    @property
    def requirement_count(self) -> int:
        return len(self.requirements)

    @property
    def concrete_course_codes(self) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for requirement in self.requirements:
            for course_code in requirement.option_course_codes:
                if course_code not in seen:
                    seen.add(course_code)
                    ordered.append(course_code)
        return tuple(ordered)


@dataclass
class CurriculumRequirement:
    requirement_type: RequirementType
    label: str
    recommended_year: int | None = None
    recommended_term: str | None = None
    course_count_min: int | None = None
    credits_min: float | None = None
    ects_min: float | None = None
    option_course_codes: list[str] = field(default_factory=list)


@dataclass
class CurriculumVersion:
    program: Program
    version_label: str
    is_latest: bool
    requirements: list[CurriculumRequirement]
    review_status: ReviewStatus = ReviewStatus.SCRAPED
