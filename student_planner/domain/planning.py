from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, TypeVar

from student_planner.domain.electives import ElectiveIntent
from student_planner.domain.grades import Grade, earns_credit, normalize_grade
from student_planner.domain.models import RequirementType


class DifficultyPreference(StrEnum):
    EASY = "easy"
    BALANCED = "balanced"
    HARD = "hard"


class PlanningWarningSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class RequirementProgressStatus(StrEnum):
    SATISFIED = "satisfied"
    PARTIALLY_SATISFIED = "partially_satisfied"
    UNSATISFIED = "unsatisfied"
    NEEDS_REVIEW = "needs_review"


class CoursePlanningStatus(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    RECOMMENDED = "recommended"
    NOT_IN_CURRICULUM = "not_in_curriculum"
    NEEDS_REVIEW = "needs_review"


class RecommendationScenarioKind(StrEnum):
    EASY = "easy"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


@dataclass(frozen=True)
class CompletedCourseAttempt:
    course_code: str
    grade: Grade | str
    completed_semester_no: str | None = None
    attempt_order: int | None = None
    source: str = "manual"
    ects: float | None = None
    credits: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "course_code", normalize_display_course_code(self.course_code))
        object.__setattr__(self, "grade", normalize_grade(self.grade))
        object.__setattr__(self, "completed_semester_no", clean_optional_text(self.completed_semester_no))
        object.__setattr__(self, "source", clean_text(self.source, "source"))
        validate_optional_positive_int(self.attempt_order, "attempt_order")
        validate_optional_non_negative_float(self.ects, "ects")
        validate_optional_non_negative_float(self.credits, "credits")

    @property
    def earns_credit(self) -> bool:
        return earns_credit(self.grade)


@dataclass(frozen=True)
class InProgressCourse:
    course_code: str
    semester_no: str
    source: str = "manual"

    def __post_init__(self) -> None:
        object.__setattr__(self, "course_code", normalize_display_course_code(self.course_code))
        object.__setattr__(self, "semester_no", clean_text(self.semester_no, "semester_no"))
        object.__setattr__(self, "source", clean_text(self.source, "source"))


@dataclass(frozen=True)
class PlanningGoal:
    target_semester_no: str
    difficulty_preference: DifficultyPreference | str = DifficultyPreference.BALANCED
    target_ects: float | None = None
    min_ects: float | None = None
    max_ects: float | None = None
    target_term_gpa: float | None = None
    target_cumulative_gpa: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_semester_no", clean_text(self.target_semester_no, "target_semester_no"))
        object.__setattr__(
            self,
            "difficulty_preference",
            coerce_enum(self.difficulty_preference, DifficultyPreference, "difficulty_preference"),
        )
        object.__setattr__(self, "notes", self.notes.strip())
        validate_optional_positive_float(self.target_ects, "target_ects")
        validate_optional_positive_float(self.min_ects, "min_ects")
        validate_optional_positive_float(self.max_ects, "max_ects")
        validate_optional_gpa(self.target_term_gpa, "target_term_gpa")
        validate_optional_gpa(self.target_cumulative_gpa, "target_cumulative_gpa")
        if self.min_ects is not None and self.max_ects is not None and self.min_ects > self.max_ects:
            raise ValueError("min_ects cannot be greater than max_ects.")


@dataclass(frozen=True)
class StudentPlanningInput:
    program_abbr: str
    completed_courses: tuple[CompletedCourseAttempt, ...]
    goal: PlanningGoal
    student_id: str | None = None
    curriculum_version_label: str | None = None
    in_progress_courses: tuple[InProgressCourse, ...] = field(default_factory=tuple)
    elective_intents: tuple[ElectiveIntent, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "program_abbr", clean_text(self.program_abbr, "program_abbr").upper())
        object.__setattr__(self, "completed_courses", tuple(self.completed_courses))
        object.__setattr__(self, "in_progress_courses", tuple(self.in_progress_courses))
        object.__setattr__(self, "elective_intents", tuple(self.elective_intents))
        object.__setattr__(self, "student_id", clean_optional_text(self.student_id))
        object.__setattr__(self, "curriculum_version_label", clean_optional_text(self.curriculum_version_label))
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))
        if not isinstance(self.goal, PlanningGoal):
            raise TypeError("goal must be a PlanningGoal.")
        for course in self.completed_courses:
            if not isinstance(course, CompletedCourseAttempt):
                raise TypeError("completed_courses must contain CompletedCourseAttempt items.")
        for course in self.in_progress_courses:
            if not isinstance(course, InProgressCourse):
                raise TypeError("in_progress_courses must contain InProgressCourse items.")
        for intent in self.elective_intents:
            if not isinstance(intent, ElectiveIntent):
                raise TypeError("elective_intents must contain ElectiveIntent items.")

    @property
    def completed_course_codes(self) -> tuple[str, ...]:
        return tuple(course.course_code for course in self.completed_courses)

    @property
    def in_progress_course_codes(self) -> tuple[str, ...]:
        return tuple(course.course_code for course in self.in_progress_courses)

    @property
    def requested_elective_intents(self) -> tuple[ElectiveIntent, ...]:
        return tuple(intent for intent in self.elective_intents if intent.wants_to_take)


@dataclass(frozen=True)
class PlanningWarning:
    code: str
    message: str
    severity: PlanningWarningSeverity | str = PlanningWarningSeverity.WARNING
    course_code: str | None = None
    requirement_label: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", clean_text(self.code, "code"))
        object.__setattr__(self, "message", clean_text(self.message, "message"))
        object.__setattr__(
            self,
            "severity",
            coerce_enum(self.severity, PlanningWarningSeverity, "severity"),
        )
        object.__setattr__(
            self,
            "course_code",
            normalize_display_course_code(self.course_code) if self.course_code else None,
        )
        object.__setattr__(self, "requirement_label", clean_optional_text(self.requirement_label))


@dataclass(frozen=True)
class RequirementProgress:
    requirement_label: str
    requirement_type: RequirementType | str
    status: RequirementProgressStatus | str
    requirement_id: int | None = None
    completed_course_codes: tuple[str, ...] = field(default_factory=tuple)
    remaining_course_codes: tuple[str, ...] = field(default_factory=tuple)
    option_course_codes: tuple[str, ...] = field(default_factory=tuple)
    recommended_year: int | None = None
    recommended_term: str | None = None
    course_count_min: int | None = None
    ects_min: float | None = None
    credits_min: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirement_label", clean_text(self.requirement_label, "requirement_label"))
        object.__setattr__(
            self,
            "requirement_type",
            coerce_enum(self.requirement_type, RequirementType, "requirement_type"),
        )
        object.__setattr__(
            self,
            "status",
            coerce_enum(self.status, RequirementProgressStatus, "status"),
        )
        validate_optional_positive_int(self.requirement_id, "requirement_id")
        validate_optional_positive_int(self.recommended_year, "recommended_year")
        validate_optional_positive_int(self.course_count_min, "course_count_min")
        validate_optional_non_negative_float(self.ects_min, "ects_min")
        validate_optional_non_negative_float(self.credits_min, "credits_min")
        object.__setattr__(self, "completed_course_codes", normalize_course_code_tuple(self.completed_course_codes))
        object.__setattr__(self, "remaining_course_codes", normalize_course_code_tuple(self.remaining_course_codes))
        object.__setattr__(self, "option_course_codes", normalize_course_code_tuple(self.option_course_codes))
        object.__setattr__(self, "recommended_term", clean_optional_text(self.recommended_term))
        object.__setattr__(self, "notes", self.notes.strip())


@dataclass(frozen=True)
class CourseEligibilitySummary:
    course_code: str
    is_eligible: bool
    explanation: str = ""
    missing_prerequisite_codes: tuple[str, ...] = field(default_factory=tuple)
    satisfied_set_nos: tuple[str, ...] = field(default_factory=tuple)
    blocking_set_nos: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "course_code", normalize_display_course_code(self.course_code))
        object.__setattr__(self, "explanation", self.explanation.strip())
        object.__setattr__(self, "missing_prerequisite_codes", normalize_course_code_tuple(self.missing_prerequisite_codes))
        object.__setattr__(self, "satisfied_set_nos", clean_text_tuple(self.satisfied_set_nos))
        object.__setattr__(self, "blocking_set_nos", clean_text_tuple(self.blocking_set_nos))

    @property
    def status(self) -> CoursePlanningStatus:
        return CoursePlanningStatus.ELIGIBLE if self.is_eligible else CoursePlanningStatus.BLOCKED


@dataclass(frozen=True)
class CourseRecommendation:
    course_code: str
    priority_score: float
    rationale: tuple[str, ...] = field(default_factory=tuple)
    estimated_ects: float | None = None
    estimated_credits: float | None = None
    difficulty_score: float | None = None
    unlock_count: int = 0
    is_placeholder: bool = False
    is_user_requested: bool = False
    is_new_course: bool = False
    is_repeat_priority: bool = False
    requires_course_selection_for_timetable: bool = False
    status: CoursePlanningStatus | str = CoursePlanningStatus.RECOMMENDED

    def __post_init__(self) -> None:
        object.__setattr__(self, "course_code", normalize_display_course_code(self.course_code))
        validate_non_negative_float(self.priority_score, "priority_score")
        validate_optional_non_negative_float(self.estimated_ects, "estimated_ects")
        validate_optional_non_negative_float(self.estimated_credits, "estimated_credits")
        validate_optional_non_negative_float(self.difficulty_score, "difficulty_score")
        validate_non_negative_int(self.unlock_count, "unlock_count")
        object.__setattr__(self, "is_placeholder", bool(self.is_placeholder))
        object.__setattr__(self, "is_user_requested", bool(self.is_user_requested))
        object.__setattr__(self, "is_new_course", bool(self.is_new_course))
        object.__setattr__(self, "is_repeat_priority", bool(self.is_repeat_priority))
        object.__setattr__(
            self,
            "requires_course_selection_for_timetable",
            bool(self.requires_course_selection_for_timetable),
        )
        object.__setattr__(self, "rationale", clean_text_tuple(self.rationale))
        object.__setattr__(self, "status", coerce_enum(self.status, CoursePlanningStatus, "status"))


@dataclass(frozen=True)
class RecommendationScenario:
    name: str
    kind: RecommendationScenarioKind | str
    courses: tuple[CourseRecommendation, ...]
    rationale: tuple[str, ...] = field(default_factory=tuple)
    total_ects: float | None = None
    total_credits: float | None = None
    difficulty_score: float | None = None
    warnings: tuple[PlanningWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", clean_text(self.name, "name"))
        object.__setattr__(self, "kind", coerce_enum(self.kind, RecommendationScenarioKind, "kind"))
        object.__setattr__(self, "courses", tuple(self.courses))
        object.__setattr__(self, "rationale", clean_text_tuple(self.rationale))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        validate_optional_non_negative_float(self.total_ects, "total_ects")
        validate_optional_non_negative_float(self.total_credits, "total_credits")
        validate_optional_non_negative_float(self.difficulty_score, "difficulty_score")
        for course in self.courses:
            if not isinstance(course, CourseRecommendation):
                raise TypeError("courses must contain CourseRecommendation items.")
        for warning in self.warnings:
            if not isinstance(warning, PlanningWarning):
                raise TypeError("warnings must contain PlanningWarning items.")

    @property
    def course_codes(self) -> tuple[str, ...]:
        return tuple(course.course_code for course in self.courses)

    @property
    def course_count(self) -> int:
        return len(self.courses)


@dataclass(frozen=True)
class PlanningReport:
    program_abbr: str
    goal: PlanningGoal
    generated_at_utc: str
    curriculum_progress: tuple[RequirementProgress, ...] = field(default_factory=tuple)
    eligible_courses: tuple[CourseEligibilitySummary, ...] = field(default_factory=tuple)
    blocked_courses: tuple[CourseEligibilitySummary, ...] = field(default_factory=tuple)
    scenarios: tuple[RecommendationScenario, ...] = field(default_factory=tuple)
    warnings: tuple[PlanningWarning, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "program_abbr", clean_text(self.program_abbr, "program_abbr").upper())
        if not isinstance(self.goal, PlanningGoal):
            raise TypeError("goal must be a PlanningGoal.")
        object.__setattr__(self, "generated_at_utc", clean_text(self.generated_at_utc, "generated_at_utc"))
        object.__setattr__(self, "curriculum_progress", tuple(self.curriculum_progress))
        object.__setattr__(self, "eligible_courses", tuple(self.eligible_courses))
        object.__setattr__(self, "blocked_courses", tuple(self.blocked_courses))
        object.__setattr__(self, "scenarios", tuple(self.scenarios))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))
        assert_tuple_items(self.curriculum_progress, RequirementProgress, "curriculum_progress")
        assert_tuple_items(self.eligible_courses, CourseEligibilitySummary, "eligible_courses")
        assert_tuple_items(self.blocked_courses, CourseEligibilitySummary, "blocked_courses")
        assert_tuple_items(self.scenarios, RecommendationScenario, "scenarios")
        assert_tuple_items(self.warnings, PlanningWarning, "warnings")

    @property
    def has_blockers(self) -> bool:
        return any(warning.severity == PlanningWarningSeverity.BLOCKER for warning in self.warnings)


EnumT = TypeVar("EnumT", bound=StrEnum)


def coerce_enum(value: EnumT | str, enum_type: type[EnumT], field_name: str) -> EnumT:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a {enum_type.__name__} or string.")
    try:
        return enum_type(value.strip().lower())
    except ValueError as exc:
        raise ValueError(f"Unsupported {field_name}: {value!r}") from exc


def normalize_display_course_code(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("course_code must be a string.")
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


def normalize_course_code_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(normalize_display_course_code(value) for value in values)


def clean_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty.")
    return cleaned


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("optional text fields must be strings or None.")
    cleaned = value.strip()
    return cleaned or None


def clean_text_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(clean_text(value, "tuple item") for value in values)


def freeze_mapping(mapping: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(mapping))


def assert_tuple_items(values: tuple[Any, ...], item_type: type[Any], field_name: str) -> None:
    for value in values:
        if not isinstance(value, item_type):
            raise TypeError(f"{field_name} must contain {item_type.__name__} items.")


def validate_optional_gpa(value: float | None, field_name: str) -> None:
    if value is None:
        return
    validate_non_negative_float(value, field_name)
    if value > 4.0:
        raise ValueError(f"{field_name} cannot be greater than 4.0.")


def validate_optional_positive_float(value: float | None, field_name: str) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{field_name} must be positive.")


def validate_optional_non_negative_float(value: float | None, field_name: str) -> None:
    if value is not None:
        validate_non_negative_float(value, field_name)


def validate_non_negative_float(value: float, field_name: str) -> None:
    if not isinstance(value, int | float):
        raise TypeError(f"{field_name} must be numeric.")
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")


def validate_optional_positive_int(value: int | None, field_name: str) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{field_name} must be positive.")


def validate_non_negative_int(value: int, field_name: str) -> None:
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")
