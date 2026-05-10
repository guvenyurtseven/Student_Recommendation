from __future__ import annotations

import unittest

from student_planner.domain.grades import Grade
from student_planner.domain.models import RequirementType
from student_planner.domain.planning import (
    CompletedCourseAttempt,
    CourseEligibilitySummary,
    CoursePlanningStatus,
    CourseRecommendation,
    DifficultyPreference,
    InProgressCourse,
    PlanningGoal,
    PlanningReport,
    PlanningWarning,
    PlanningWarningSeverity,
    RecommendationScenario,
    RecommendationScenarioKind,
    RequirementProgress,
    RequirementProgressStatus,
    StudentPlanningInput,
    normalize_display_course_code,
)


class PlanningModelTests(unittest.TestCase):
    def test_normalize_display_course_code(self) -> None:
        self.assertEqual(normalize_display_course_code("ceng140"), "CENG 140")
        self.assertEqual(normalize_display_course_code(" CENG   140 "), "CENG 140")
        self.assertEqual(normalize_display_course_code("355 140"), "355 140")
        self.assertEqual(normalize_display_course_code("5710140"), "5710140")

    def test_student_planning_input_normalizes_course_attempts_and_program(self) -> None:
        goal = PlanningGoal(
            target_semester_no="20252",
            difficulty_preference="hard",
            target_ects=30,
            target_term_gpa=3.2,
        )
        completed = CompletedCourseAttempt(
            course_code="ceng140",
            grade="cc",
            completed_semester_no="20242",
            attempt_order=1,
            ects=6,
        )
        in_progress = InProgressCourse("math219", "20252")
        planning_input = StudentPlanningInput(
            program_abbr=" ceng ",
            completed_courses=[completed],
            in_progress_courses=[in_progress],
            goal=goal,
            metadata={"source": "unit-test"},
        )

        self.assertEqual(planning_input.program_abbr, "CENG")
        self.assertEqual(planning_input.goal.difficulty_preference, DifficultyPreference.HARD)
        self.assertEqual(planning_input.completed_courses[0].course_code, "CENG 140")
        self.assertEqual(planning_input.completed_courses[0].grade, Grade.CC)
        self.assertTrue(planning_input.completed_courses[0].earns_credit)
        self.assertEqual(planning_input.completed_course_codes, ("CENG 140",))
        self.assertEqual(planning_input.in_progress_course_codes, ("MATH 219",))
        with self.assertRaises(TypeError):
            planning_input.metadata["new"] = "value"

    def test_planning_goal_validates_gpa_and_ects_bounds(self) -> None:
        with self.assertRaises(ValueError):
            PlanningGoal(target_semester_no="20252", target_cumulative_gpa=4.1)
        with self.assertRaises(ValueError):
            PlanningGoal(target_semester_no="20252", min_ects=35, max_ects=20)
        with self.assertRaises(ValueError):
            PlanningGoal(target_semester_no="20252", target_ects=0)

    def test_requirement_progress_coerces_enums_and_course_codes(self) -> None:
        progress = RequirementProgress(
            requirement_id=1,
            requirement_label="CENG 140",
            requirement_type="required_course",
            status="satisfied",
            completed_course_codes=["ceng140"],
            option_course_codes=["CENG 140"],
            recommended_year=1,
            recommended_term="Fall",
            ects_min=6,
        )

        self.assertEqual(progress.requirement_type, RequirementType.REQUIRED_COURSE)
        self.assertEqual(progress.status, RequirementProgressStatus.SATISFIED)
        self.assertEqual(progress.completed_course_codes, ("CENG 140",))

    def test_course_eligibility_summary_exposes_planning_status(self) -> None:
        blocked = CourseEligibilitySummary(
            course_code="math219",
            is_eligible=False,
            missing_prerequisite_codes=["math120"],
            blocking_set_nos=["1"],
        )
        eligible = CourseEligibilitySummary("ceng213", is_eligible=True)

        self.assertEqual(blocked.status, CoursePlanningStatus.BLOCKED)
        self.assertEqual(blocked.missing_prerequisite_codes, ("MATH 120",))
        self.assertEqual(eligible.status, CoursePlanningStatus.ELIGIBLE)

    def test_recommendation_scenario_and_report_contract(self) -> None:
        goal = PlanningGoal("20252")
        recommendation = CourseRecommendation(
            course_code="math219",
            priority_score=8.5,
            estimated_ects=6,
            difficulty_score=0.6,
            unlock_count=2,
            rationale=["Unlocks later math-dependent courses"],
        )
        warning = PlanningWarning(
            code="offerings_missing",
            message="Offering data is not loaded yet.",
            severity="blocker",
        )
        scenario = RecommendationScenario(
            name="Balanced",
            kind="balanced",
            courses=[recommendation],
            total_ects=6,
            difficulty_score=0.6,
            warnings=[warning],
        )
        report = PlanningReport(
            program_abbr="ceng",
            goal=goal,
            generated_at_utc="2026-05-10T00:00:00+00:00",
            scenarios=[scenario],
            warnings=[warning],
        )

        self.assertEqual(scenario.kind, RecommendationScenarioKind.BALANCED)
        self.assertEqual(scenario.course_codes, ("MATH 219",))
        self.assertEqual(scenario.course_count, 1)
        self.assertEqual(report.program_abbr, "CENG")
        self.assertTrue(report.has_blockers)
        self.assertEqual(report.warnings[0].severity, PlanningWarningSeverity.BLOCKER)


if __name__ == "__main__":
    unittest.main()
