from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from student_planner.domain.grades import Grade, normalize_grade
from student_planner.domain.models import CurriculumSnapshot, RequirementType
from student_planner.domain.planning import (
    CompletedCourseAttempt,
    CourseEligibilitySummary,
    CourseRecommendation,
    PlanningWarning,
    PlanningWarningSeverity,
    RecommendationScenario,
    StudentPlanningInput,
)
from student_planner.services.candidate_courses import CandidateCourse, CandidateCourseResult
from student_planner.services.curriculum_progress import attempt_sort_key
from student_planner.services.difficulty import normalize_term_label
from student_planner.services.prerequisite_evaluator import CourseAliases, canonicalize_course_code
from student_planner.services.recommendation import RecommendationResult


METU_UNDERGRAD_RULES_URL = (
    "https://oidb.metu.edu.tr/en/"
    "middle-east-technical-university-rules-and-regulations-governing-undergraduate-studies"
)
MIN_COURSE_LOAD = 3
REPEAT_PRIORITY_GRADES = {Grade.FF, Grade.FD, Grade.NA, Grade.U, Grade.W}


@dataclass(frozen=True)
class AcademicStandingSnapshot:
    standing: str
    cgpa: float | None = None
    gpa: float | None = None
    semester_no: str | None = None

    @property
    def is_probation(self) -> bool:
        normalized = self.standing.upper()
        return "PROBATION" in normalized or normalized == "PROB" or "SINAMALI" in normalized


@dataclass(frozen=True)
class RegistrationPolicyState:
    academic_standing: AcademicStandingSnapshot | None
    normal_course_load: int | None
    max_course_count: int | None
    min_course_count: int
    warnings: tuple[PlanningWarning, ...] = ()

    @property
    def is_probation(self) -> bool:
        return self.academic_standing.is_probation if self.academic_standing else False

    @property
    def metadata(self) -> dict[str, Any]:
        standing = self.academic_standing
        return {
            "registration_policy_source_url": METU_UNDERGRAD_RULES_URL,
            "registration_policy_academic_standing": standing.standing if standing else None,
            "registration_policy_cgpa": standing.cgpa if standing else None,
            "registration_policy_gpa": standing.gpa if standing else None,
            "registration_policy_standing_semester_no": standing.semester_no if standing else None,
            "registration_policy_is_probation": self.is_probation,
            "registration_policy_normal_course_load": self.normal_course_load,
            "registration_policy_max_course_count": self.max_course_count,
            "registration_policy_min_course_count": self.min_course_count,
        }


@dataclass(frozen=True)
class RegistrationPolicyResult:
    candidate_result: CandidateCourseResult
    state: RegistrationPolicyState


class AcademicRegistrationPolicyService:
    """Apply METU undergraduate registration rules to deterministic planning.

    The service implements rules that can be evaluated from transcript-derived
    state, curriculum metadata, prerequisites, and offering-filtered candidates.
    Advisor approvals and department-specific criteria are emitted as warnings
    when they cannot be proven automatically.
    """

    def __init__(self, aliases: CourseAliases | None = None) -> None:
        self.aliases = aliases or {}

    def apply_to_candidates(
        self,
        planning_input: StudentPlanningInput,
        candidate_result: CandidateCourseResult,
        curriculum: CurriculumSnapshot,
    ) -> RegistrationPolicyResult:
        state = self.build_state(planning_input, curriculum)
        latest_attempts = latest_attempts_by_course(planning_input.completed_courses, self.aliases)
        previously_taken = previously_taken_course_codes(planning_input.completed_courses, self.aliases)

        eligible: list[CandidateCourse] = []
        blocked: list[CandidateCourse] = list(candidate_result.blocked_courses)
        policy_warnings: list[PlanningWarning] = list(state.warnings)
        probation_blocked_count = 0

        for candidate in candidate_result.eligible_courses:
            annotated = annotate_candidate(candidate, latest_attempts, previously_taken, self.aliases)
            block_reason = self.block_reason_for_candidate(annotated, latest_attempts, state)
            if block_reason is None:
                eligible.append(annotated)
                continue
            probation_blocked_count += 1
            blocked.append(block_candidate(annotated, block_reason))

        repeat_priority_count = sum(1 for candidate in eligible if candidate.is_repeat_priority)
        if repeat_priority_count:
            policy_warnings.append(
                PlanningWarning(
                    code="repeat_priority_courses_detected",
                    message=(
                        f"{repeat_priority_count} eligible course(s) are repeat-priority items "
                        "under METU semester registration ordering."
                    ),
                    severity=PlanningWarningSeverity.INFO,
                )
            )
        if probation_blocked_count:
            policy_warnings.append(
                PlanningWarning(
                    code="probation_new_course_block",
                    message=(
                        f"{probation_blocked_count} eligible candidate(s) were blocked because "
                        "probation students may not register for courses they have not previously "
                        "taken, or courses from which they earned W."
                    ),
                    severity=PlanningWarningSeverity.BLOCKER,
                )
            )

        return RegistrationPolicyResult(
            candidate_result=CandidateCourseResult(
                eligible_courses=tuple(eligible),
                blocked_courses=tuple(blocked),
                warnings=(*candidate_result.warnings, *tuple(policy_warnings)),
            ),
            state=state,
        )

    def apply_to_recommendations(
        self,
        recommendation_result: RecommendationResult,
        state: RegistrationPolicyState,
    ) -> RecommendationResult:
        scenarios: list[RecommendationScenario] = []
        warnings: list[PlanningWarning] = list(recommendation_result.warnings)
        for scenario in recommendation_result.scenarios:
            adjusted = enforce_scenario_course_load(scenario, state)
            scenarios.append(adjusted)
            warnings.extend(adjusted.warnings)

        return RecommendationResult(
            scenarios=tuple(scenarios),
            warnings=dedupe_warnings(tuple(warnings)),
            preferred_kind=recommendation_result.preferred_kind,
        )

    def build_state(
        self,
        planning_input: StudentPlanningInput,
        curriculum: CurriculumSnapshot,
    ) -> RegistrationPolicyState:
        standing = academic_standing_from_metadata(planning_input.metadata)
        normal_course_load = normal_course_load_from_curriculum(curriculum)
        max_course_count = max_course_count_for(standing, normal_course_load)
        warnings: list[PlanningWarning] = []

        if standing is None:
            warnings.append(
                PlanningWarning(
                    code="academic_standing_unavailable",
                    message=(
                        "Academic standing/CGPA could not be read from the planning input. "
                        "Probation-specific restrictions cannot be proven automatically."
                    ),
                    severity=PlanningWarningSeverity.WARNING,
                )
            )
        if normal_course_load is None:
            warnings.append(
                PlanningWarning(
                    code="normal_course_load_unavailable",
                    message=(
                        "Normal course load could not be computed from the loaded curriculum. "
                        "Course-count overload limits cannot be enforced automatically."
                    ),
                    severity=PlanningWarningSeverity.WARNING,
                )
            )
        warnings.append(
            PlanningWarning(
                code="advisor_approval_required",
                message=(
                    "METU semester registration and add/drop changes require academic advisor approval; "
                    "the planner can recommend only pre-approval course sets."
                ),
                severity=PlanningWarningSeverity.INFO,
            )
        )
        warnings.append(
            PlanningWarning(
                code="department_specific_criteria_need_review",
                message=(
                    "METU departments may define additional course criteria beyond the structured "
                    "prerequisite/offering data loaded here; final registration should be checked in SAIS "
                    "and with the advisor."
                ),
                severity=PlanningWarningSeverity.WARNING,
            )
        )

        return RegistrationPolicyState(
            academic_standing=standing,
            normal_course_load=normal_course_load,
            max_course_count=max_course_count,
            min_course_count=MIN_COURSE_LOAD,
            warnings=tuple(warnings),
        )

    def block_reason_for_candidate(
        self,
        candidate: CandidateCourse,
        latest_attempts: Mapping[str, CompletedCourseAttempt],
        state: RegistrationPolicyState,
    ) -> str | None:
        if not state.is_probation:
            return None

        latest_attempt = latest_attempts.get(canonicalize_course_code(candidate.course_code, self.aliases))
        latest_grade = latest_attempt.grade if latest_attempt else None
        if latest_grade == Grade.W:
            return (
                "Blocked by METU probation rule: probation students may not register for a course "
                "from which they earned W."
            )
        if candidate.is_new_course:
            return (
                "Blocked by METU probation rule: probation students may not register for courses "
                "they have not previously taken."
            )
        return None


def academic_standing_from_metadata(metadata: Mapping[str, Any]) -> AcademicStandingSnapshot | None:
    transcript_parse = metadata.get("transcript_parse")
    source: Mapping[str, Any]
    if isinstance(transcript_parse, Mapping):
        source = transcript_parse
    else:
        source = metadata

    standing_value = source.get("latest_standing") or source.get("standing")
    if not standing_value:
        return None
    return AcademicStandingSnapshot(
        standing=str(standing_value).strip().upper(),
        cgpa=optional_float(source.get("latest_cgpa") or source.get("cgpa")),
        gpa=optional_float(source.get("latest_gpa") or source.get("gpa")),
        semester_no=optional_string(source.get("latest_standing_semester_no") or source.get("standing_semester_no")),
    )


def normal_course_load_from_curriculum(curriculum: CurriculumSnapshot) -> int | None:
    counts_by_term: dict[tuple[int, str], int] = {}
    for requirement in curriculum.requirements:
        if requirement.requirement_type in {RequirementType.SUMMER_PRACTICE, RequirementType.OTHER}:
            continue
        if requirement.recommended_year is None or requirement.recommended_term is None:
            continue
        if requirement.credits_min == 0:
            continue
        term = normalize_term_label(requirement.recommended_term)
        if term is None:
            continue
        count = requirement.course_count_min or 1
        counts_by_term[(requirement.recommended_year, term)] = (
            counts_by_term.get((requirement.recommended_year, term), 0) + count
        )
    return max(counts_by_term.values()) if counts_by_term else None


def max_course_count_for(
    standing: AcademicStandingSnapshot | None,
    normal_course_load: int | None,
) -> int | None:
    if normal_course_load is None:
        return None
    cgpa = standing.cgpa if standing else None
    if cgpa is None:
        return normal_course_load
    if cgpa >= 2.50:
        return normal_course_load + 2
    if cgpa >= 2.00:
        return normal_course_load + 1
    return normal_course_load


def annotate_candidate(
    candidate: CandidateCourse,
    latest_attempts: Mapping[str, CompletedCourseAttempt],
    previously_taken: set[str],
    aliases: CourseAliases,
) -> CandidateCourse:
    canonical = canonicalize_course_code(candidate.course_code, aliases)
    latest_attempt = latest_attempts.get(canonical)
    latest_grade = latest_attempt.grade if latest_attempt else None
    is_new_course = canonical not in previously_taken
    is_repeat_priority = latest_grade in REPEAT_PRIORITY_GRADES
    return replace(
        candidate,
        is_new_course=is_new_course,
        is_repeat_priority=is_repeat_priority,
    )


def block_candidate(candidate: CandidateCourse, reason: str) -> CandidateCourse:
    return replace(
        candidate,
        eligibility=CourseEligibilitySummary(
            course_code=candidate.course_code,
            is_eligible=False,
            explanation=reason,
            missing_prerequisite_codes=candidate.eligibility.missing_prerequisite_codes,
            satisfied_set_nos=candidate.eligibility.satisfied_set_nos,
            blocking_set_nos=candidate.eligibility.blocking_set_nos,
        ),
        rationale=(*candidate.rationale, reason),
    )


def latest_attempts_by_course(
    attempts: tuple[CompletedCourseAttempt, ...],
    aliases: CourseAliases | None = None,
) -> dict[str, CompletedCourseAttempt]:
    latest: dict[str, tuple[tuple[int, int, str], CompletedCourseAttempt]] = {}
    for input_index, attempt in enumerate(attempts):
        course_code = canonicalize_course_code(attempt.course_code, aliases)
        sort_key = attempt_sort_key(attempt, input_index)
        if course_code not in latest or sort_key >= latest[course_code][0]:
            latest[course_code] = (sort_key, attempt)
    return {course_code: attempt for course_code, (_sort_key, attempt) in latest.items()}


def previously_taken_course_codes(
    attempts: tuple[CompletedCourseAttempt, ...],
    aliases: CourseAliases | None = None,
) -> set[str]:
    return {
        canonicalize_course_code(attempt.course_code, aliases)
        for attempt in attempts
        if normalize_grade(attempt.grade) != Grade.W
    }


def enforce_scenario_course_load(
    scenario: RecommendationScenario,
    state: RegistrationPolicyState,
) -> RecommendationScenario:
    courses = scenario.courses
    warnings = list(scenario.warnings)
    rationale = list(scenario.rationale)

    if state.max_course_count is not None:
        courses, excluded = trim_to_credit_course_count(courses, state.max_course_count)
        if excluded:
            warnings.append(
                PlanningWarning(
                    code="scenario_trimmed_to_course_load_cap",
                    message=(
                        f"{scenario.name} was trimmed by {len(excluded)} course(s) to respect "
                        f"the METU course-load cap of {state.max_course_count} credit course(s)."
                    ),
                    severity=PlanningWarningSeverity.WARNING,
                )
            )
            if any(course.is_repeat_priority for course in excluded):
                warnings.append(
                    PlanningWarning(
                        code="repeat_priority_course_excluded_by_course_load_cap",
                        message=(
                            "At least one repeat-priority course could not fit within the computed "
                            "course-load cap; advisor review is required."
                        ),
                        severity=PlanningWarningSeverity.WARNING,
                    )
                )
            rationale.append(f"Applied METU course-load cap: {state.max_course_count} credit course(s).")

    credit_count = credit_course_count(courses)
    if not state.is_probation and credit_count < state.min_course_count:
        warnings.append(
            PlanningWarning(
                code="scenario_below_minimum_course_load",
                message=(
                    f"{scenario.name} contains {credit_count} credit course(s), below METU's "
                    f"{state.min_course_count}-credit-course minimum unless advisor and department "
                    "approval or graduation exception applies."
                ),
                severity=PlanningWarningSeverity.WARNING,
            )
        )

    return RecommendationScenario(
        name=scenario.name,
        kind=scenario.kind,
        courses=courses,
        rationale=tuple(rationale),
        total_ects=total_ects(courses),
        total_credits=total_credits(courses),
        difficulty_score=weighted_average_difficulty(courses),
        warnings=tuple(warnings),
    )


def trim_to_credit_course_count(
    courses: tuple[CourseRecommendation, ...],
    max_course_count: int,
) -> tuple[tuple[CourseRecommendation, ...], tuple[CourseRecommendation, ...]]:
    kept: list[CourseRecommendation] = []
    excluded: list[CourseRecommendation] = []
    credit_count = 0
    for course in courses:
        if not counts_as_credit_course(course):
            kept.append(course)
            continue
        if credit_count >= max_course_count:
            excluded.append(course)
            continue
        kept.append(course)
        credit_count += 1
    return tuple(kept), tuple(excluded)


def counts_as_credit_course(course: CourseRecommendation) -> bool:
    return course.estimated_credits is None or course.estimated_credits > 0


def credit_course_count(courses: tuple[CourseRecommendation, ...]) -> int:
    return sum(1 for course in courses if counts_as_credit_course(course))


def total_ects(courses: tuple[CourseRecommendation, ...]) -> float:
    return sum(course.estimated_ects or 0.0 for course in courses)


def total_credits(courses: tuple[CourseRecommendation, ...]) -> float | None:
    if not courses or any(course.estimated_credits is None for course in courses):
        return None
    return sum(course.estimated_credits or 0.0 for course in courses)


def weighted_average_difficulty(courses: tuple[CourseRecommendation, ...]) -> float | None:
    ects_total = total_ects(courses)
    if ects_total <= 0:
        return None
    return round(
        sum((course.difficulty_score or 0.0) * (course.estimated_ects or 0.0) for course in courses) / ects_total,
        4,
    )


def dedupe_warnings(warnings: tuple[PlanningWarning, ...]) -> tuple[PlanningWarning, ...]:
    seen: set[tuple[str, str, str, str | None]] = set()
    deduped: list[PlanningWarning] = []
    for warning in warnings:
        key = (warning.code, str(warning.severity), warning.message, warning.course_code)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(warning)
    return tuple(deduped)


def optional_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
