from __future__ import annotations

from dataclasses import dataclass, field

from student_planner.domain.models import CurriculumRequirementRecord, CurriculumSnapshot, RequirementType
from student_planner.domain.planning import (
    CompletedCourseAttempt,
    PlanningWarning,
    PlanningWarningSeverity,
    RequirementProgress,
    RequirementProgressStatus,
    StudentPlanningInput,
)
from student_planner.services.prerequisite_evaluator import CourseAliases, canonicalize_course_code


REVIEW_ONLY_REQUIREMENT_TYPES = {
    RequirementType.TECHNICAL_ELECTIVE_POOL,
    RequirementType.RESTRICTED_ELECTIVE_POOL,
    RequirementType.NONTECHNICAL_ELECTIVE_POOL,
    RequirementType.FREE_ELECTIVE_POOL,
    RequirementType.SUMMER_PRACTICE,
    RequirementType.OTHER,
}


@dataclass(frozen=True)
class CurriculumProgressResult:
    program_abbr: str
    curriculum_version_label: str
    requirements: tuple[RequirementProgress, ...]
    warnings: tuple[PlanningWarning, ...] = field(default_factory=tuple)

    @property
    def satisfied_requirements(self) -> tuple[RequirementProgress, ...]:
        return tuple(
            requirement
            for requirement in self.requirements
            if requirement.status == RequirementProgressStatus.SATISFIED
        )

    @property
    def unsatisfied_requirements(self) -> tuple[RequirementProgress, ...]:
        return tuple(
            requirement
            for requirement in self.requirements
            if requirement.status
            in {
                RequirementProgressStatus.UNSATISFIED,
                RequirementProgressStatus.PARTIALLY_SATISFIED,
                RequirementProgressStatus.NEEDS_REVIEW,
            }
        )

    @property
    def remaining_concrete_course_codes(self) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for requirement in self.unsatisfied_requirements:
            for course_code in requirement.remaining_course_codes:
                if course_code not in seen:
                    seen.add(course_code)
                    ordered.append(course_code)
        return tuple(ordered)


class CurriculumProgressService:
    """Evaluate a student's progress against a curriculum snapshot.

    This service intentionally does not evaluate prerequisites or offerings. It
    only answers which curriculum requirements appear satisfied by the student's
    completed course attempts.
    """

    def __init__(self, aliases: CourseAliases | None = None) -> None:
        self.aliases = aliases or {}

    def evaluate(
        self,
        planning_input: StudentPlanningInput,
        curriculum: CurriculumSnapshot,
    ) -> CurriculumProgressResult:
        if planning_input.program_abbr != curriculum.program.abbr.upper():
            raise ValueError(
                "planning_input program does not match curriculum program: "
                f"{planning_input.program_abbr} != {curriculum.program.abbr}"
            )

        completed = latest_completed_credit_courses(planning_input.completed_courses, self.aliases)
        requirement_progress: list[RequirementProgress] = []
        warnings: list[PlanningWarning] = []
        for requirement in curriculum.requirements:
            progress, warning = self.evaluate_requirement(requirement, completed)
            requirement_progress.append(progress)
            if warning is not None:
                warnings.append(warning)

        return CurriculumProgressResult(
            program_abbr=curriculum.program.abbr,
            curriculum_version_label=curriculum.version_label,
            requirements=tuple(requirement_progress),
            warnings=tuple(warnings),
        )

    def evaluate_requirement(
        self,
        requirement: CurriculumRequirementRecord,
        completed_course_codes: set[str],
    ) -> tuple[RequirementProgress, PlanningWarning | None]:
        option_codes = canonical_course_codes(requirement.option_course_codes, self.aliases)
        if not option_codes:
            return self.review_only_progress(requirement), PlanningWarning(
                code="requirement_needs_manual_matching",
                message=(
                    "This curriculum requirement has no concrete course options in the "
                    "current processed data, so it cannot be automatically marked satisfied."
                ),
                severity=PlanningWarningSeverity.WARNING,
                requirement_label=requirement.label,
            )

        completed_options = tuple(course_code for course_code in option_codes if course_code in completed_course_codes)
        required_count = required_option_count(requirement, len(option_codes))
        if len(completed_options) >= required_count:
            status = RequirementProgressStatus.SATISFIED
            remaining_options: tuple[str, ...] = ()
        elif completed_options:
            status = RequirementProgressStatus.PARTIALLY_SATISFIED
            remaining_options = tuple(course_code for course_code in option_codes if course_code not in completed_course_codes)
        else:
            status = RequirementProgressStatus.UNSATISFIED
            remaining_options = option_codes

        return RequirementProgress(
            requirement_id=requirement.id,
            requirement_label=requirement.label,
            requirement_type=requirement.requirement_type,
            status=status,
            completed_course_codes=completed_options,
            remaining_course_codes=remaining_options,
            option_course_codes=option_codes,
            recommended_year=requirement.recommended_year,
            recommended_term=requirement.recommended_term,
            course_count_min=requirement.course_count_min,
            ects_min=requirement.ects_min,
            credits_min=requirement.credits_min,
            notes=progress_note(requirement, required_count, len(option_codes)),
        ), None

    def review_only_progress(self, requirement: CurriculumRequirementRecord) -> RequirementProgress:
        note = (
            "Automatic matching is not available yet for this requirement type. "
            "It should be reviewed as part of elective/special requirement handling."
        )
        if requirement.requirement_type not in REVIEW_ONLY_REQUIREMENT_TYPES:
            note = "No concrete course options were found for this requirement."

        return RequirementProgress(
            requirement_id=requirement.id,
            requirement_label=requirement.label,
            requirement_type=requirement.requirement_type,
            status=RequirementProgressStatus.NEEDS_REVIEW,
            recommended_year=requirement.recommended_year,
            recommended_term=requirement.recommended_term,
            course_count_min=requirement.course_count_min,
            ects_min=requirement.ects_min,
            credits_min=requirement.credits_min,
            notes=note,
        )


def latest_completed_credit_courses(
    attempts: tuple[CompletedCourseAttempt, ...],
    aliases: CourseAliases | None = None,
) -> set[str]:
    latest_by_course: dict[str, tuple[tuple[int, int, str], CompletedCourseAttempt]] = {}
    for input_index, attempt in enumerate(attempts):
        course_code = canonicalize_course_code(attempt.course_code, aliases)
        sort_key = attempt_sort_key(attempt, input_index)
        if course_code not in latest_by_course or sort_key >= latest_by_course[course_code][0]:
            latest_by_course[course_code] = (sort_key, attempt)

    return {
        course_code
        for course_code, (_sort_key, attempt) in latest_by_course.items()
        if attempt.earns_credit
    }


def attempt_sort_key(attempt: CompletedCourseAttempt, input_index: int) -> tuple[int, int, str]:
    if attempt.attempt_order is not None:
        return (2, attempt.attempt_order, "")
    if attempt.completed_semester_no:
        return (1, int_or_negative_one(attempt.completed_semester_no), attempt.completed_semester_no)
    return (0, input_index, "")


def int_or_negative_one(value: str) -> int:
    return int(value) if value.isdigit() else -1


def canonical_course_codes(course_codes: tuple[str, ...], aliases: CourseAliases | None = None) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for course_code in course_codes:
        canonical = canonicalize_course_code(course_code, aliases)
        if canonical not in seen:
            seen.add(canonical)
            ordered.append(canonical)
    return tuple(ordered)


def required_option_count(requirement: CurriculumRequirementRecord, option_count: int) -> int:
    if requirement.course_count_min is not None:
        return max(1, min(requirement.course_count_min, option_count))
    if requirement.requirement_type == RequirementType.REQUIRED_COURSE:
        return max(1, option_count)
    return 1


def progress_note(requirement: CurriculumRequirementRecord, required_count: int, option_count: int) -> str:
    if requirement.requirement_type == RequirementType.REQUIRED_COURSE:
        return f"Requires {required_count} of {option_count} listed required course option(s)."
    return f"Requires {required_count} of {option_count} listed option(s)."
