from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from student_planner.domain.models import CurriculumSnapshot
from student_planner.domain.planning import (
    PlanningReport,
    PlanningWarning,
    PlanningWarningSeverity,
    StudentPlanningInput,
)
from student_planner.services.candidate_courses import CandidateCourseGenerator
from student_planner.services.curriculum_progress import CurriculumProgressService
from student_planner.services.difficulty import CourseScoringService
from student_planner.services.offering_availability import OfferingAvailabilityService, OfferingFilterResult
from student_planner.services.prerequisite_evaluator import CourseAliases, PrerequisiteEdge
from student_planner.services.recommendation import RecommendationService
from student_planner.services.unlock_analysis import UnlockAnalysisService


class PlanningRepository(Protocol):
    def fetch_alias_map(self) -> dict[str, str]: ...

    def fetch_latest_curriculum(self, program_abbr: str) -> CurriculumSnapshot: ...

    def fetch_prerequisite_edges_for_courses(
        self,
        target_course_codes: list[str] | tuple[str, ...],
        aliases: CourseAliases | None = None,
    ) -> dict[str, list[PrerequisiteEdge]]: ...

    def fetch_all_prerequisite_edges(self) -> list[PrerequisiteEdge]: ...

    def count_offerings(self, semester_no: str | None = None) -> int: ...

    def fetch_offered_course_codes(
        self,
        semester_no: str,
        aliases: CourseAliases | None = None,
    ) -> tuple[str, ...]: ...

    def fetch_offering_subject_codes(self, semester_no: str) -> tuple[str, ...]: ...


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


@dataclass(frozen=True)
class SemesterPlanningPipeline:
    repository: PlanningRepository
    clock: Callable[[], dt.datetime] = utc_now

    def build_report(self, planning_input: StudentPlanningInput) -> PlanningReport:
        aliases = self.repository.fetch_alias_map()
        curriculum = self.repository.fetch_latest_curriculum(planning_input.program_abbr)
        progress = CurriculumProgressService(aliases).evaluate(planning_input, curriculum)
        candidate_edges = self.repository.fetch_prerequisite_edges_for_courses(
            progress.remaining_concrete_course_codes,
            aliases,
        )
        raw_candidate_result = CandidateCourseGenerator(aliases).generate(
            planning_input=planning_input,
            progress=progress,
            prerequisite_edges_by_course=candidate_edges,
        )
        offering_result = filter_candidates_by_offerings(
            repository=self.repository,
            aliases=aliases,
            raw_candidate_result=raw_candidate_result,
            target_semester_no=planning_input.goal.target_semester_no,
        )
        candidate_result = offering_result.candidate_result
        unlock_result = UnlockAnalysisService(aliases).analyze(
            candidate_course_codes=candidate_result.eligible_course_codes,
            prerequisite_edges=self.repository.fetch_all_prerequisite_edges(),
            curriculum_course_codes=curriculum.concrete_course_codes,
        )
        scoring_result = CourseScoringService().score_eligible_candidates(
            candidate_result=candidate_result,
            unlock_result=unlock_result,
            goal=planning_input.goal,
            program_abbr=curriculum.program.abbr,
        )
        recommendation_result = RecommendationService().build_scenarios(scoring_result)

        warnings = (
            *candidate_result.warnings,
            *offering_result.warnings,
            *recommendation_result.warnings,
            *data_availability_warnings(self.repository, planning_input.goal.target_semester_no),
        )
        return PlanningReport(
            program_abbr=curriculum.program.abbr,
            goal=planning_input.goal,
            generated_at_utc=self.clock().isoformat(timespec="seconds"),
            curriculum_progress=progress.requirements,
            eligible_courses=tuple(candidate.eligibility for candidate in candidate_result.eligible_courses),
            blocked_courses=tuple(candidate.eligibility for candidate in candidate_result.blocked_courses),
            scenarios=recommendation_result.scenarios,
            warnings=warnings,
            metadata=report_metadata(
                curriculum=curriculum,
                candidate_count=len(candidate_result.all_courses),
                eligible_count=len(candidate_result.eligible_courses),
                blocked_count=len(candidate_result.blocked_courses),
                preferred_scenario_kind=recommendation_result.preferred_kind.value,
                offerings_count=safe_count_offerings(self.repository),
                target_semester_offerings_count=safe_count_offerings(
                    self.repository,
                    planning_input.goal.target_semester_no,
                ),
                offered_candidate_count=len(offering_result.offered_course_codes),
                not_offered_candidate_count=len(offering_result.not_offered_course_codes),
                unknown_offering_candidate_count=len(offering_result.unknown_course_codes),
            ),
        )


def filter_candidates_by_offerings(
    repository: PlanningRepository,
    aliases: CourseAliases,
    raw_candidate_result: Any,
    target_semester_no: str,
) -> OfferingFilterResult:
    return OfferingAvailabilityService(aliases).filter_for_target_semester(
        candidate_result=raw_candidate_result,
        target_semester_no=target_semester_no,
        offered_course_codes=safe_fetch_offered_course_codes(repository, target_semester_no, aliases),
        covered_subject_codes=safe_fetch_offering_subject_codes(repository, target_semester_no),
    )


def data_availability_warnings(
    repository: PlanningRepository,
    target_semester_no: str,
) -> tuple[PlanningWarning, ...]:
    offerings_count = safe_count_offerings(repository)
    if offerings_count == 0:
        return (
            PlanningWarning(
                code="offerings_unavailable",
                message=(
                    "Course offering data is not loaded yet; recommendations do not "
                    "confirm whether courses are available in the target semester."
                ),
                severity=PlanningWarningSeverity.WARNING,
            ),
        )

    target_offerings_count = safe_count_offerings(repository, target_semester_no)
    if target_offerings_count == 0:
        return (
            PlanningWarning(
                code="target_semester_offerings_unavailable",
                message=(
                    f"Course offering data exists, but no offerings are loaded for "
                    f"target semester {target_semester_no}."
                ),
                severity=PlanningWarningSeverity.WARNING,
            ),
        )

    return ()


def safe_count_offerings(repository: PlanningRepository, semester_no: str | None = None) -> int:
    try:
        return repository.count_offerings(semester_no)
    except TypeError:
        if semester_no is None:
            return repository.count_offerings()
        return 0
    except AttributeError:
        return 0


def safe_fetch_offered_course_codes(
    repository: PlanningRepository,
    semester_no: str,
    aliases: CourseAliases,
) -> tuple[str, ...]:
    try:
        return repository.fetch_offered_course_codes(semester_no, aliases)
    except AttributeError:
        return ()


def safe_fetch_offering_subject_codes(
    repository: PlanningRepository,
    semester_no: str,
) -> tuple[str, ...]:
    try:
        return repository.fetch_offering_subject_codes(semester_no)
    except AttributeError:
        return ()


def report_metadata(
    curriculum: CurriculumSnapshot,
    candidate_count: int,
    eligible_count: int,
    blocked_count: int,
    preferred_scenario_kind: str,
    offerings_count: int,
    target_semester_offerings_count: int,
    offered_candidate_count: int,
    not_offered_candidate_count: int,
    unknown_offering_candidate_count: int,
) -> dict[str, Any]:
    return {
        "curriculum_version_label": curriculum.version_label,
        "curriculum_review_status": curriculum.review_status.value,
        "curriculum_requirement_count": curriculum.requirement_count,
        "candidate_count": candidate_count,
        "eligible_candidate_count": eligible_count,
        "blocked_candidate_count": blocked_count,
        "preferred_scenario_kind": preferred_scenario_kind,
        "offerings_count": offerings_count,
        "target_semester_offerings_count": target_semester_offerings_count,
        "offered_candidate_count": offered_candidate_count,
        "not_offered_candidate_count": not_offered_candidate_count,
        "unknown_offering_candidate_count": unknown_offering_candidate_count,
    }
