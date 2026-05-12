from __future__ import annotations

import unittest

from student_planner.domain.planning import (
    CourseEligibilitySummary,
    CourseRecommendation,
    PlanningGoal,
    PlanningReport,
    PlanningWarning,
    PlanningWarningSeverity,
    RecommendationScenario,
)
from student_planner.services.student_view import planning_report_to_student_view


class StudentViewTests(unittest.TestCase):
    def test_student_view_hides_internal_load_metrics_from_courses(self) -> None:
        report = report_fixture()

        view = planning_report_to_student_view(report)

        course = view["routes"][0]["courses"][0]
        self.assertEqual(course["code"], "BA 100")
        self.assertIn("Kredisiz", course["summary"])
        self.assertIn("zero_credit", course["flags"])
        self.assertNotIn("estimated_ects", course)
        self.assertNotIn("difficulty_score", course)

    def test_student_view_contains_routes_notices_blocked_courses_and_elective_status(self) -> None:
        view = planning_report_to_student_view(report_fixture())

        self.assertEqual(view["program_abbr"], "CENG")
        self.assertEqual(view["target_semester_no"], "20252")
        self.assertEqual(view["routes"][0]["credit_course_count"], 1)
        self.assertEqual(view["routes"][0]["zero_credit_course_count"], 1)
        self.assertEqual(view["routes"][0]["courses"][0]["color"], "#f6d65b")
        self.assertNotIn("timetable", view["routes"][0])
        self.assertEqual(view["notices"][0]["code"], "department_specific_criteria_need_review")
        self.assertEqual(view["blocked_courses"][0]["code"], "CENG 400")
        self.assertEqual(view["blocked_courses"][0]["missing_prerequisites"], ["CENG 300"])
        self.assertEqual(view["elective_status"][0]["label"], "Free Elective")
        self.assertEqual(view["elective_status"][0]["remaining"], 1)

    def test_summer_practice_summary_uses_product_copy(self) -> None:
        report = report_fixture(
            courses=(
                CourseRecommendation(
                    course_code="CENG 300",
                    priority_score=10,
                    estimated_credits=0,
                    estimated_ects=5,
                ),
            )
        )

        view = planning_report_to_student_view(report)

        self.assertEqual(
            view["routes"][0]["courses"][0]["summary"],
            "Eğer stajını resmi olarak yaptıysan bu dersi almalısın.",
        )


def report_fixture(courses: tuple[CourseRecommendation, ...] | None = None) -> PlanningReport:
    return PlanningReport(
        program_abbr="CENG",
        goal=PlanningGoal("20252"),
        generated_at_utc="2026-05-12T00:00:00+00:00",
        scenarios=(
            RecommendationScenario(
                name="Ana Rota",
                kind="balanced",
                courses=courses or (
                    CourseRecommendation(
                        course_code="BA 100",
                        priority_score=10,
                        estimated_credits=0,
                        estimated_ects=1,
                    ),
                    CourseRecommendation(
                        course_code="CENG 334",
                        priority_score=80,
                        estimated_credits=3,
                        estimated_ects=6,
                    ),
                ),
            ),
        ),
        blocked_courses=(
            CourseEligibilitySummary(
                course_code="CENG 400",
                is_eligible=False,
                missing_prerequisite_codes=("CENG 300",),
                explanation="CENG 400 is blocked; missing CENG 300.",
            ),
        ),
        warnings=(
            PlanningWarning(
                code="advisor_approval_required",
                message="Advisor approval required.",
                severity=PlanningWarningSeverity.INFO,
            ),
            PlanningWarning(
                code="department_specific_criteria_need_review",
                message="Department criteria need review.",
                severity=PlanningWarningSeverity.WARNING,
            ),
        ),
        metadata={
            "elective_remaining_slots_by_category": {"free_elective": 1},
            "elective_completed_counts_by_category": {"free_elective": 0},
            "elective_requested_counts_by_category": {"free_elective": 1},
            "elective_matched_counts_by_category": {"free_elective": 1},
        },
    )


if __name__ == "__main__":
    unittest.main()
