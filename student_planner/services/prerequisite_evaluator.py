from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from student_planner.domain.grades import Grade, normalize_grade, satisfies_min_grade


@dataclass(frozen=True)
class CompletedCourse:
    course_code: str
    grade: Grade | str
    completed_semester_no: str = ""
    attempt_order: int | None = None


@dataclass(frozen=True)
class PrerequisiteEdge:
    prerequisite_course_code: str
    course_code: str
    set_no: str
    min_grade: Grade | str = Grade.DD
    edge_type: str = ""
    position: str = ""


@dataclass(frozen=True)
class RequirementEvaluation:
    prerequisite_course_code: str
    min_grade: Grade
    earned_grade: Grade | None
    is_satisfied: bool
    reason: str


@dataclass(frozen=True)
class PrerequisiteSetEvaluation:
    set_no: str
    is_satisfied: bool
    requirements: tuple[RequirementEvaluation, ...]

    @property
    def missing_requirements(self) -> tuple[RequirementEvaluation, ...]:
        return tuple(requirement for requirement in self.requirements if not requirement.is_satisfied)


@dataclass(frozen=True)
class EligibilityResult:
    target_course_code: str
    is_eligible: bool
    set_evaluations: tuple[PrerequisiteSetEvaluation, ...]
    explanation: str

    @property
    def satisfied_set_nos(self) -> tuple[str, ...]:
        return tuple(
            set_evaluation.set_no
            for set_evaluation in self.set_evaluations
            if set_evaluation.is_satisfied
        )

    @property
    def missing_by_set(self) -> dict[str, tuple[RequirementEvaluation, ...]]:
        return {
            set_evaluation.set_no: set_evaluation.missing_requirements
            for set_evaluation in self.set_evaluations
            if set_evaluation.missing_requirements
        }


CourseAliases = Mapping[str, str]
CompletedInput = Mapping[str, Grade | str] | Iterable[CompletedCourse]


def normalize_course_code(value: str) -> str:
    """Normalize human-entered display course codes.

    Examples:

    - `ceng140` -> `CENG 140`
    - ` CENG   140 ` -> `CENG 140`
    - `355 140` -> `355 140`
    - `5710140` -> `5710140`
    """

    normalized = re.sub(r"\s+", " ", value.strip().upper())
    if not normalized:
        raise ValueError("Course code cannot be empty.")
    if normalized.isdigit():
        return normalized

    match = re.match(r"^([A-Z]+)\s*(\d+[A-Z]?)$", normalized)
    if match:
        return f"{match.group(1)} {match.group(2)}"

    match = re.match(r"^(\d+)\s+(\d+[A-Z]?)$", normalized)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return normalized


def canonicalize_course_code(value: str, aliases: CourseAliases | None = None) -> str:
    normalized = normalize_course_code(value)
    if not aliases:
        return normalized

    normalized_aliases = {
        normalize_course_code(alias): normalize_course_code(canonical)
        for alias, canonical in aliases.items()
    }
    return normalized_aliases.get(normalized, normalized)


def evaluate_eligibility(
    target_course_code: str,
    prerequisite_edges: Iterable[PrerequisiteEdge],
    completed_courses: CompletedInput,
    aliases: CourseAliases | None = None,
) -> EligibilityResult:
    target = canonicalize_course_code(target_course_code, aliases)
    completed = build_completed_course_index(completed_courses, aliases)
    relevant_edges = [
        edge
        for edge in prerequisite_edges
        if canonicalize_course_code(edge.course_code, aliases) == target
    ]

    if not relevant_edges:
        return EligibilityResult(
            target_course_code=target,
            is_eligible=True,
            set_evaluations=(),
            explanation=f"{target} has no prerequisite records.",
        )

    set_evaluations = evaluate_prerequisite_sets(relevant_edges, completed, aliases)
    is_eligible = any(set_evaluation.is_satisfied for set_evaluation in set_evaluations)
    explanation = build_explanation(target, is_eligible, set_evaluations)
    return EligibilityResult(
        target_course_code=target,
        is_eligible=is_eligible,
        set_evaluations=set_evaluations,
        explanation=explanation,
    )


def build_completed_course_index(
    completed_courses: CompletedInput,
    aliases: CourseAliases | None = None,
) -> dict[str, Grade]:
    if isinstance(completed_courses, Mapping):
        items = [
            CompletedCourse(course_code=course_code, grade=grade)
            for course_code, grade in completed_courses.items()
        ]
    else:
        items = list(completed_courses)

    completed: dict[str, tuple[tuple[int, int, str], Grade]] = {}
    for input_index, item in enumerate(items):
        course_code = canonicalize_course_code(item.course_code, aliases)
        grade = normalize_grade(item.grade)
        sort_key = completed_attempt_sort_key(item, input_index)
        if course_code not in completed or sort_key >= completed[course_code][0]:
            completed[course_code] = (sort_key, grade)
    return {course_code: grade for course_code, (_sort_key, grade) in completed.items()}


def completed_attempt_sort_key(item: CompletedCourse, input_index: int) -> tuple[int, int, str]:
    """Return a sortable key where the latest known attempt wins.

    Priority:

    1. Explicit `attempt_order`, when provided.
    2. Numeric `completed_semester_no`, when provided.
    3. Input order as a deterministic fallback.
    """

    if item.attempt_order is not None:
        return (2, item.attempt_order, "")
    if item.completed_semester_no:
        return (1, int_or_negative_one(item.completed_semester_no), item.completed_semester_no)
    return (0, input_index, "")


def int_or_negative_one(value: str) -> int:
    return int(value) if value.isdigit() else -1


def evaluate_prerequisite_sets(
    prerequisite_edges: Iterable[PrerequisiteEdge],
    completed: Mapping[str, Grade],
    aliases: CourseAliases | None = None,
) -> tuple[PrerequisiteSetEvaluation, ...]:
    grouped: dict[str, list[PrerequisiteEdge]] = defaultdict(list)
    for edge in prerequisite_edges:
        grouped[str(edge.set_no)].append(edge)

    set_evaluations: list[PrerequisiteSetEvaluation] = []
    for set_no in sorted(grouped, key=sort_set_no):
        requirement_evaluations = tuple(
            evaluate_requirement(edge, completed, aliases)
            for edge in sorted(
                grouped[set_no],
                key=lambda item: canonicalize_course_code(item.prerequisite_course_code, aliases),
            )
        )
        set_evaluations.append(
            PrerequisiteSetEvaluation(
                set_no=set_no,
                is_satisfied=all(requirement.is_satisfied for requirement in requirement_evaluations),
                requirements=requirement_evaluations,
            )
        )

    return tuple(set_evaluations)


def evaluate_requirement(
    edge: PrerequisiteEdge,
    completed: Mapping[str, Grade],
    aliases: CourseAliases | None = None,
) -> RequirementEvaluation:
    prerequisite_course_code = canonicalize_course_code(edge.prerequisite_course_code, aliases)
    min_grade = normalize_grade(edge.min_grade)
    earned_grade = completed.get(prerequisite_course_code)
    if earned_grade is None:
        return RequirementEvaluation(
            prerequisite_course_code=prerequisite_course_code,
            min_grade=min_grade,
            earned_grade=None,
            is_satisfied=False,
            reason="not_completed",
        )

    is_satisfied = satisfies_min_grade(earned_grade, min_grade)
    return RequirementEvaluation(
        prerequisite_course_code=prerequisite_course_code,
        min_grade=min_grade,
        earned_grade=earned_grade,
        is_satisfied=is_satisfied,
        reason="satisfied" if is_satisfied else "insufficient_grade",
    )


def sort_set_no(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (10**9, value)


def build_explanation(
    target: str,
    is_eligible: bool,
    set_evaluations: tuple[PrerequisiteSetEvaluation, ...],
) -> str:
    if is_eligible:
        return f"{target} is eligible via set(s): {', '.join(set_no for set_no in set_evaluation_ids(set_evaluations))}."

    missing_parts = []
    for set_evaluation in set_evaluations:
        missing = ", ".join(
            requirement.prerequisite_course_code
            for requirement in set_evaluation.missing_requirements
        )
        missing_parts.append(f"set {set_evaluation.set_no}: {missing}")
    return f"{target} is blocked; missing or insufficient prerequisites in {('; '.join(missing_parts))}."


def set_evaluation_ids(set_evaluations: tuple[PrerequisiteSetEvaluation, ...]) -> tuple[str, ...]:
    return tuple(
        set_evaluation.set_no
        for set_evaluation in set_evaluations
        if set_evaluation.is_satisfied
    )
