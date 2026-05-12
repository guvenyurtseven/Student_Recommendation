from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from student_planner.domain.planning import (
    CompletedCourseAttempt,
    CourseEligibilitySummary,
    PlanningWarning,
    PlanningWarningSeverity,
    RequirementProgress,
    StudentPlanningInput,
)
from student_planner.services.curriculum_progress import CurriculumProgressResult
from student_planner.services.prerequisite_evaluator import (
    CompletedCourse,
    CourseAliases,
    PrerequisiteEdge,
    canonicalize_course_code,
    evaluate_eligibility,
)


@dataclass(frozen=True)
class CandidateCourse:
    course_code: str
    eligibility: CourseEligibilitySummary
    requirement_labels: tuple[str, ...] = field(default_factory=tuple)
    recommended_year: int | None = None
    recommended_term: str | None = None
    estimated_ects: float | None = None
    estimated_credits: float | None = None
    difficulty_rank: int | None = None
    is_placeholder: bool = False
    is_user_requested: bool = False
    is_new_course: bool = False
    is_repeat_priority: bool = False
    elective_category: str | None = None
    is_easy_priority_elective: bool = False
    requires_explicit_course_selection: bool = False
    rationale: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_eligible(self) -> bool:
        return self.eligibility.is_eligible


@dataclass(frozen=True)
class CandidateCourseResult:
    eligible_courses: tuple[CandidateCourse, ...]
    blocked_courses: tuple[CandidateCourse, ...]
    warnings: tuple[PlanningWarning, ...] = field(default_factory=tuple)

    @property
    def all_courses(self) -> tuple[CandidateCourse, ...]:
        return self.eligible_courses + self.blocked_courses

    @property
    def eligible_course_codes(self) -> tuple[str, ...]:
        return tuple(candidate.course_code for candidate in self.eligible_courses)

    @property
    def blocked_course_codes(self) -> tuple[str, ...]:
        return tuple(candidate.course_code for candidate in self.blocked_courses)


class CandidateCourseGenerator:
    """Generate eligible/blocked concrete course candidates for a student.

    This service connects curriculum progress to prerequisite evaluation. It
    does not rank courses, optimize workload, or filter by offerings yet.
    """

    def __init__(self, aliases: CourseAliases | None = None) -> None:
        self.aliases = aliases or {}

    def generate(
        self,
        planning_input: StudentPlanningInput,
        progress: CurriculumProgressResult,
        prerequisite_edges_by_course: Mapping[str, Iterable[PrerequisiteEdge]],
    ) -> CandidateCourseResult:
        completed_courses = to_prerequisite_completed_courses(planning_input.completed_courses)
        edges_by_course = canonicalize_edge_mapping(prerequisite_edges_by_course, self.aliases)
        requirement_index = RequirementCandidateIndex(progress.requirements, self.aliases)
        eligible: list[CandidateCourse] = []
        blocked: list[CandidateCourse] = []

        for course_code in progress.remaining_concrete_course_codes:
            target = canonicalize_course_code(course_code, self.aliases)
            eligibility_result = evaluate_eligibility(
                target_course_code=target,
                prerequisite_edges=edges_by_course.get(target, ()),
                completed_courses=completed_courses,
                aliases=self.aliases,
            )
            summary = CourseEligibilitySummary(
                course_code=target,
                is_eligible=eligibility_result.is_eligible,
                explanation=eligibility_result.explanation,
                missing_prerequisite_codes=missing_prerequisite_codes(eligibility_result.missing_by_set),
                satisfied_set_nos=eligibility_result.satisfied_set_nos,
                blocking_set_nos=tuple(eligibility_result.missing_by_set.keys()),
            )
            metadata = requirement_index.metadata_for(target)
            candidate = CandidateCourse(
                course_code=target,
                eligibility=summary,
                requirement_labels=metadata.requirement_labels,
                recommended_year=metadata.recommended_year,
                recommended_term=metadata.recommended_term,
                estimated_ects=metadata.estimated_ects,
                estimated_credits=metadata.estimated_credits,
            )
            if candidate.is_eligible:
                eligible.append(candidate)
            else:
                blocked.append(candidate)

        warnings = list(progress.warnings)
        if not eligible and not blocked:
            warnings.append(
                PlanningWarning(
                    code="no_remaining_concrete_courses",
                    message="No remaining concrete curriculum courses were available for candidate evaluation.",
                    severity=PlanningWarningSeverity.INFO,
                )
            )

        return CandidateCourseResult(
            eligible_courses=tuple(eligible),
            blocked_courses=tuple(blocked),
            warnings=tuple(warnings),
        )


@dataclass(frozen=True)
class RequirementCandidateMetadata:
    requirement_labels: tuple[str, ...] = ()
    recommended_year: int | None = None
    recommended_term: str | None = None
    estimated_ects: float | None = None
    estimated_credits: float | None = None


class RequirementCandidateIndex:
    def __init__(self, requirements: tuple[RequirementProgress, ...], aliases: CourseAliases | None = None) -> None:
        self.aliases = aliases or {}
        self._metadata_by_course = self.build_index(requirements)

    def metadata_for(self, course_code: str) -> RequirementCandidateMetadata:
        return self._metadata_by_course.get(
            canonicalize_course_code(course_code, self.aliases),
            RequirementCandidateMetadata(),
        )

    def build_index(self, requirements: tuple[RequirementProgress, ...]) -> dict[str, RequirementCandidateMetadata]:
        grouped: dict[str, list[RequirementProgress]] = {}
        for requirement in requirements:
            for course_code in requirement.remaining_course_codes:
                target = canonicalize_course_code(course_code, self.aliases)
                grouped.setdefault(target, []).append(requirement)

        return {
            course_code: merge_requirement_metadata(requirements)
            for course_code, requirements in grouped.items()
        }


def merge_requirement_metadata(requirements: list[RequirementProgress]) -> RequirementCandidateMetadata:
    return RequirementCandidateMetadata(
        requirement_labels=tuple(requirement.requirement_label for requirement in requirements),
        recommended_year=first_present(requirement.recommended_year for requirement in requirements),
        recommended_term=first_present(requirement.recommended_term for requirement in requirements),
        estimated_ects=first_present(requirement.ects_min for requirement in requirements),
        estimated_credits=first_present(requirement.credits_min for requirement in requirements),
    )


def first_present(values: Iterable[object | None]) -> object | None:
    for value in values:
        if value is not None:
            return value
    return None


def to_prerequisite_completed_courses(
    attempts: tuple[CompletedCourseAttempt, ...],
) -> tuple[CompletedCourse, ...]:
    return tuple(
        CompletedCourse(
            course_code=attempt.course_code,
            grade=attempt.grade,
            completed_semester_no=attempt.completed_semester_no or "",
            attempt_order=attempt.attempt_order,
        )
        for attempt in attempts
    )


def canonicalize_edge_mapping(
    prerequisite_edges_by_course: Mapping[str, Iterable[PrerequisiteEdge]],
    aliases: CourseAliases | None = None,
) -> dict[str, tuple[PrerequisiteEdge, ...]]:
    canonical: dict[str, list[PrerequisiteEdge]] = {}
    for course_code, edges in prerequisite_edges_by_course.items():
        target = canonicalize_course_code(course_code, aliases)
        canonical.setdefault(target, []).extend(edges)
    return {course_code: tuple(edges) for course_code, edges in canonical.items()}


def missing_prerequisite_codes(missing_by_set: Mapping[str, tuple[object, ...]]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for requirements in missing_by_set.values():
        for requirement in requirements:
            course_code = getattr(requirement, "prerequisite_course_code")
            if course_code not in seen:
                seen.add(course_code)
                ordered.append(course_code)
    return tuple(ordered)
