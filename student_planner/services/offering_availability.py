from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum

from student_planner.domain.planning import CourseEligibilitySummary, PlanningWarning, PlanningWarningSeverity
from student_planner.services.candidate_courses import CandidateCourse, CandidateCourseResult
from student_planner.services.prerequisite_evaluator import CourseAliases, canonicalize_course_code


class OfferingAvailabilityStatus(StrEnum):
    OFFERED = "offered"
    NOT_OFFERED = "not_offered"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CourseOfferingAvailability:
    course_code: str
    status: OfferingAvailabilityStatus


@dataclass(frozen=True)
class OfferingFilterResult:
    candidate_result: CandidateCourseResult
    availability: tuple[CourseOfferingAvailability, ...]
    warnings: tuple[PlanningWarning, ...] = ()

    @property
    def offered_course_codes(self) -> tuple[str, ...]:
        return tuple(item.course_code for item in self.availability if item.status == OfferingAvailabilityStatus.OFFERED)

    @property
    def not_offered_course_codes(self) -> tuple[str, ...]:
        return tuple(
            item.course_code for item in self.availability if item.status == OfferingAvailabilityStatus.NOT_OFFERED
        )

    @property
    def unknown_course_codes(self) -> tuple[str, ...]:
        return tuple(item.course_code for item in self.availability if item.status == OfferingAvailabilityStatus.UNKNOWN)


class OfferingAvailabilityService:
    """Conservatively filter recommendation candidates by target-semester offerings.

    A course is removed only when its subject has offering coverage for the target
    semester and the course itself is absent. If the subject has no loaded
    coverage, the course remains eligible with an availability warning elsewhere.
    """

    def __init__(self, aliases: CourseAliases | None = None) -> None:
        self.aliases = aliases or {}

    def filter_for_target_semester(
        self,
        candidate_result: CandidateCourseResult,
        target_semester_no: str,
        offered_course_codes: Iterable[str],
        covered_subject_codes: Iterable[str],
    ) -> OfferingFilterResult:
        offered = {
            canonicalize_course_code(course_code, self.aliases)
            for course_code in offered_course_codes
        }
        covered_subjects = {subject.upper().strip() for subject in covered_subject_codes if subject.strip()}
        if not covered_subjects:
            return OfferingFilterResult(candidate_result=candidate_result, availability=())

        availability = tuple(
            CourseOfferingAvailability(
                course_code=candidate.course_code,
                status=availability_status(candidate, offered, covered_subjects),
            )
            for candidate in candidate_result.eligible_courses
        )
        available_candidates = tuple(
            candidate
            for candidate, item in zip(candidate_result.eligible_courses, availability, strict=True)
            if item.status != OfferingAvailabilityStatus.NOT_OFFERED
        )
        not_offered_candidates = tuple(
            block_not_offered_candidate(candidate, target_semester_no)
            for candidate, item in zip(candidate_result.eligible_courses, availability, strict=True)
            if item.status == OfferingAvailabilityStatus.NOT_OFFERED
        )
        filtered_result = CandidateCourseResult(
            eligible_courses=available_candidates,
            blocked_courses=(*candidate_result.blocked_courses, *not_offered_candidates),
            warnings=candidate_result.warnings,
        )
        return OfferingFilterResult(
            candidate_result=filtered_result,
            availability=availability,
            warnings=availability_warnings(target_semester_no, availability),
        )


def availability_status(
    candidate: CandidateCourse,
    offered_course_codes: set[str],
    covered_subject_codes: set[str],
) -> OfferingAvailabilityStatus:
    if candidate.course_code in offered_course_codes:
        return OfferingAvailabilityStatus.OFFERED
    if subject_code(candidate.course_code) in covered_subject_codes:
        return OfferingAvailabilityStatus.NOT_OFFERED
    return OfferingAvailabilityStatus.UNKNOWN


def block_not_offered_candidate(candidate: CandidateCourse, target_semester_no: str) -> CandidateCourse:
    return replace(
        candidate,
        eligibility=CourseEligibilitySummary(
            course_code=candidate.course_code,
            is_eligible=False,
            explanation=(
                f"{candidate.course_code} is not listed in loaded offerings for target semester "
                f"{target_semester_no}."
            ),
            missing_prerequisite_codes=candidate.eligibility.missing_prerequisite_codes,
            satisfied_set_nos=candidate.eligibility.satisfied_set_nos,
            blocking_set_nos=candidate.eligibility.blocking_set_nos,
        ),
    )


def subject_code(course_code: str) -> str:
    return course_code.split(" ", 1)[0].upper()


def availability_warnings(
    target_semester_no: str,
    availability: tuple[CourseOfferingAvailability, ...],
) -> tuple[PlanningWarning, ...]:
    not_offered = [item.course_code for item in availability if item.status == OfferingAvailabilityStatus.NOT_OFFERED]
    unknown = [item.course_code for item in availability if item.status == OfferingAvailabilityStatus.UNKNOWN]
    warnings: list[PlanningWarning] = []

    if not_offered:
        warnings.append(
            PlanningWarning(
                code="target_semester_not_offered",
                message=(
                    f"{len(not_offered)} eligible course(s) were excluded because they are not "
                    f"listed in loaded offerings for {target_semester_no}."
                ),
                severity=PlanningWarningSeverity.INFO,
            )
        )
    if unknown:
        warnings.append(
            PlanningWarning(
                code="offering_coverage_unknown",
                message=(
                    f"{len(unknown)} eligible course(s) stayed in the recommendation pool because "
                    f"their subject offering coverage is not loaded for {target_semester_no}."
                ),
                severity=PlanningWarningSeverity.WARNING,
            )
        )

    return tuple(warnings)
