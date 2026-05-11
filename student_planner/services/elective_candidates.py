from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from student_planner.domain.electives import ElectiveIntent
from student_planner.domain.planning import (
    CourseEligibilitySummary,
    PlanningWarning,
    PlanningWarningSeverity,
    StudentPlanningInput,
)
from student_planner.services.candidate_courses import (
    CandidateCourse,
    CandidateCourseResult,
    to_prerequisite_completed_courses,
)
from student_planner.services.prerequisite_evaluator import (
    CompletedCourse,
    CourseAliases,
    PrerequisiteEdge,
    canonicalize_course_code,
    evaluate_eligibility,
)


@dataclass(frozen=True)
class ElectiveCandidateResult:
    explicit_result: CandidateCourseResult
    placeholder_result: CandidateCourseResult
    warnings: tuple[PlanningWarning, ...] = field(default_factory=tuple)

    @property
    def explicit_course_codes(self) -> tuple[str, ...]:
        return self.explicit_result.eligible_course_codes + self.explicit_result.blocked_course_codes

    @property
    def placeholder_course_codes(self) -> tuple[str, ...]:
        return self.placeholder_result.eligible_course_codes

    @property
    def explicit_count(self) -> int:
        return len(self.explicit_course_codes)

    @property
    def placeholder_count(self) -> int:
        return len(self.placeholder_course_codes)


class ElectiveCandidateService:
    """Turn user elective intents into recommendation candidates.

    Explicit elective courses are treated like normal course candidates: if
    prerequisite records exist, they are evaluated, and offering filtering can
    later remove a known not-offered course. Category-only intents become
    placeholder candidates; those stay out of offering filtering because they do
    not name a concrete course yet.
    """

    def __init__(self, aliases: CourseAliases | None = None) -> None:
        self.aliases = aliases or {}

    def build(
        self,
        planning_input: StudentPlanningInput,
        prerequisite_edges_by_course: Mapping[str, list[PrerequisiteEdge] | tuple[PrerequisiteEdge, ...]],
        course_ects_estimates: Mapping[str, float] | None = None,
    ) -> ElectiveCandidateResult:
        completed_courses = to_prerequisite_completed_courses(planning_input.completed_courses)
        course_ects_estimates = course_ects_estimates or {}
        explicit_eligible: list[CandidateCourse] = []
        explicit_blocked: list[CandidateCourse] = []
        placeholders: list[CandidateCourse] = []
        warnings: list[PlanningWarning] = []

        for intent in planning_input.requested_elective_intents:
            for index in range(1, intent.requested_count + 1):
                if intent.has_explicit_course:
                    candidate = self.explicit_candidate(
                        intent=intent,
                        index=index,
                        completed_courses=completed_courses,
                        prerequisite_edges_by_course=prerequisite_edges_by_course,
                        course_ects_estimates=course_ects_estimates,
                    )
                    if candidate.is_eligible:
                        explicit_eligible.append(candidate)
                    else:
                        explicit_blocked.append(candidate)
                else:
                    placeholders.append(self.placeholder_candidate(intent, index))

        if placeholders:
            warnings.append(
                PlanningWarning(
                    code="elective_course_selection_required",
                    message=(
                        f"{len(placeholders)} elective placeholder(s) can be used for semester load planning, "
                        "but a concrete course must be selected before a weekly timetable can be built."
                    ),
                    severity=PlanningWarningSeverity.INFO,
                )
            )

        return ElectiveCandidateResult(
            explicit_result=CandidateCourseResult(
                eligible_courses=tuple(explicit_eligible),
                blocked_courses=tuple(explicit_blocked),
                warnings=tuple(warnings),
            ),
            placeholder_result=CandidateCourseResult(
                eligible_courses=tuple(placeholders),
                blocked_courses=(),
                warnings=(),
            ),
            warnings=tuple(warnings),
        )

    def explicit_candidate(
        self,
        intent: ElectiveIntent,
        index: int,
        completed_courses: tuple[CompletedCourse, ...],
        prerequisite_edges_by_course: Mapping[str, list[PrerequisiteEdge] | tuple[PrerequisiteEdge, ...]],
        course_ects_estimates: Mapping[str, float],
    ) -> CandidateCourse:
        assert intent.course_code is not None
        target = canonicalize_course_code(intent.course_code, self.aliases)
        edges = prerequisite_edges_by_course.get(target, ())
        eligibility_result = evaluate_eligibility(
            target_course_code=target,
            prerequisite_edges=edges,
            completed_courses=completed_courses,
            aliases=self.aliases,
        )
        estimated_ects = course_ects_estimates.get(target, intent.default_ects)
        summary = CourseEligibilitySummary(
            course_code=target,
            is_eligible=eligibility_result.is_eligible,
            explanation=eligibility_result.explanation,
            missing_prerequisite_codes=missing_prerequisite_codes(eligibility_result.missing_by_set),
            satisfied_set_nos=eligibility_result.satisfied_set_nos,
            blocking_set_nos=tuple(eligibility_result.missing_by_set.keys()),
        )
        return CandidateCourse(
            course_code=target,
            eligibility=summary,
            requirement_labels=(intent.category.value,),
            estimated_ects=estimated_ects,
            difficulty_rank=intent.difficulty_rank,
            is_user_requested=True,
            rationale=explicit_rationale(intent, index, target, target in course_ects_estimates),
        )

    def placeholder_candidate(self, intent: ElectiveIntent, index: int) -> CandidateCourse:
        course_code = numbered_placeholder_code(intent.placeholder_code, index, intent.requested_count)
        summary = CourseEligibilitySummary(
            course_code=course_code,
            is_eligible=True,
            explanation=(
                f"Requested {intent.category.value} placeholder. A concrete course has not been selected yet."
            ),
        )
        return CandidateCourse(
            course_code=course_code,
            eligibility=summary,
            requirement_labels=(intent.category.value,),
            estimated_ects=intent.default_ects,
            difficulty_rank=intent.difficulty_rank,
            is_placeholder=True,
            is_user_requested=True,
            requires_course_selection_for_timetable=True,
            rationale=(
                f"requested {intent.category.value}",
                f"uses category ECTS assumption {intent.default_ects:g}",
                "placeholder elective; concrete course is not selected yet",
            ),
        )


def numbered_placeholder_code(base_code: str, index: int, total_count: int) -> str:
    if total_count <= 1:
        return base_code
    return f"{base_code} {index}"


def explicit_rationale(
    intent: ElectiveIntent,
    index: int,
    target: str,
    used_db_ects: bool,
) -> tuple[str, ...]:
    count_text = "" if intent.requested_count == 1 else f" #{index}"
    ects_text = "uses DB ECTS estimate" if used_db_ects else f"uses category ECTS assumption {intent.default_ects:g}"
    return (
        f"requested {intent.category.value}{count_text}: {target}",
        ects_text,
    )


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
