from __future__ import annotations

import datetime as dt
import unittest

from student_planner.domain.models import (
    Course,
    CurriculumRequirementOption,
    CurriculumRequirementRecord,
    CurriculumSnapshot,
    Program,
    RequirementType,
    ReviewStatus,
)
from student_planner.domain.planning import (
    CompletedCourseAttempt,
    PlanningGoal,
    StudentPlanningInput,
)
from student_planner.services.planning_pipeline import SemesterPlanningPipeline
from student_planner.services.prerequisite_evaluator import PrerequisiteEdge


class SemesterPlanningPipelineTests(unittest.TestCase):
    def test_build_report_runs_full_deterministic_pipeline(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(
                CompletedCourseAttempt("MATH 119", "DD", attempt_order=1),
                CompletedCourseAttempt("CENG 140", "CC", attempt_order=2),
            ),
            goal=PlanningGoal("20252", difficulty_preference="balanced"),
        )
        report = SemesterPlanningPipeline(
            FakePlanningRepository(),
            clock=lambda: dt.datetime(2026, 5, 10, tzinfo=dt.timezone.utc),
        ).build_report(planning_input)

        self.assertEqual(report.program_abbr, "CENG")
        self.assertEqual(report.generated_at_utc, "2026-05-10T00:00:00+00:00")
        self.assertEqual(report.metadata["curriculum_version_label"], "latest")
        self.assertEqual(report.metadata["eligible_candidate_count"], 2)
        self.assertEqual(report.metadata["blocked_candidate_count"], 0)
        self.assertEqual(report.metadata["offerings_count"], 0)
        self.assertEqual({course.course_code for course in report.eligible_courses}, {"MATH 120", "CENG 213"})
        self.assertEqual(len(report.scenarios), 3)
        self.assertIn("offerings_unavailable", {warning.code for warning in report.warnings})

    def test_build_report_filters_known_not_offered_courses(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(
                CompletedCourseAttempt("MATH 119", "DD", attempt_order=1),
                CompletedCourseAttempt("CENG 140", "CC", attempt_order=2),
            ),
            goal=PlanningGoal("20252", difficulty_preference="balanced"),
        )
        report = SemesterPlanningPipeline(
            FakePlanningRepositoryWithOfferings(),
            clock=lambda: dt.datetime(2026, 5, 10, tzinfo=dt.timezone.utc),
        ).build_report(planning_input)

        self.assertEqual({course.course_code for course in report.eligible_courses}, {"MATH 120", "CENG 213"})
        self.assertEqual(report.metadata["offerings_count"], 2)
        self.assertEqual(report.metadata["target_semester_offerings_count"], 2)
        self.assertEqual(report.metadata["offered_candidate_count"], 1)
        self.assertEqual(report.metadata["not_offered_candidate_count"], 1)
        self.assertEqual(report.metadata["unknown_offering_candidate_count"], 1)
        warning_codes = {warning.code for warning in report.warnings}
        self.assertIn("target_semester_not_offered", warning_codes)
        self.assertIn("offering_coverage_unknown", warning_codes)
        self.assertNotIn("offerings_unavailable", warning_codes)


class FakePlanningRepository:
    def fetch_alias_map(self) -> dict[str, str]:
        return {
            "MATH 119": "MATH 119",
            "MATH 120": "MATH 120",
            "CENG 140": "CENG 140",
            "CENG 213": "CENG 213",
        }

    def fetch_latest_curriculum(self, program_abbr: str) -> CurriculumSnapshot:
        if program_abbr != "CENG":
            raise LookupError(program_abbr)
        return CurriculumSnapshot(
            program=Program(
                abbr="CENG",
                catalog_program_id="571",
                name_en="Computer Engineering",
                name_tr="Bilgisayar Muhendisligi",
                faculty="Engineering",
            ),
            version_id=1,
            version_label="latest",
            is_latest=True,
            review_status=ReviewStatus.SCRAPED,
            requirements=(
                required_course(1, "MATH 119", "2360119", "MATH", 119, 6),
                required_course(2, "MATH 120", "2360120", "MATH", 120, 6),
                required_course(3, "CENG 140", "5710140", "CENG", 140, 6),
                required_course(4, "CENG 213", "5710213", "CENG", 213, 6),
            ),
        )

    def fetch_prerequisite_edges_for_courses(
        self,
        target_course_codes: list[str] | tuple[str, ...],
        aliases: dict[str, str] | None = None,
    ) -> dict[str, list[PrerequisiteEdge]]:
        return {
            "MATH 120": [PrerequisiteEdge("MATH 119", "MATH 120", set_no="1")],
            "CENG 213": [PrerequisiteEdge("CENG 140", "CENG 213", set_no="1")],
        }

    def fetch_all_prerequisite_edges(self) -> list[PrerequisiteEdge]:
        return [
            PrerequisiteEdge("MATH 119", "MATH 120", set_no="1"),
            PrerequisiteEdge("MATH 120", "MATH 219", set_no="1"),
            PrerequisiteEdge("CENG 140", "CENG 213", set_no="1"),
        ]

    def count_offerings(self) -> int:
        return 0


class FakePlanningRepositoryWithOfferings(FakePlanningRepository):
    def fetch_latest_curriculum(self, program_abbr: str) -> CurriculumSnapshot:
        base = super().fetch_latest_curriculum(program_abbr)
        return CurriculumSnapshot(
            program=base.program,
            version_id=base.version_id,
            version_label=base.version_label,
            is_latest=base.is_latest,
            review_status=base.review_status,
            requirements=(
                *base.requirements,
                required_course(5, "CENG 223", "5710223", "CENG", 223, 5),
            ),
        )

    def fetch_prerequisite_edges_for_courses(
        self,
        target_course_codes: list[str] | tuple[str, ...],
        aliases: dict[str, str] | None = None,
    ) -> dict[str, list[PrerequisiteEdge]]:
        edges_by_course = super().fetch_prerequisite_edges_for_courses(target_course_codes, aliases)
        edges_by_course["CENG 223"] = []
        return edges_by_course

    def count_offerings(self, semester_no: str | None = None) -> int:
        return 2

    def fetch_offered_course_codes(
        self,
        semester_no: str,
        aliases: dict[str, str] | None = None,
    ) -> tuple[str, ...]:
        return ("CENG 213", "CENG 499")

    def fetch_offering_subject_codes(self, semester_no: str) -> tuple[str, ...]:
        return ("CENG",)


def required_course(
    requirement_id: int,
    display_code: str,
    numeric_code: str,
    subject_code: str,
    course_number: int,
    ects: float,
) -> CurriculumRequirementRecord:
    return CurriculumRequirementRecord(
        id=requirement_id,
        requirement_type=RequirementType.REQUIRED_COURSE,
        label=display_code,
        recommended_year=1,
        recommended_term="Spring",
        course_count_min=1,
        ects_min=ects,
        credits_min=ects / 1.5,
        sort_order=requirement_id,
        options=(
            CurriculumRequirementOption(
                id=requirement_id,
                course=Course(
                    numeric_code=numeric_code,
                    subject_code=subject_code,
                    course_number=course_number,
                    display_code=display_code,
                    title_en=display_code,
                ),
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()
