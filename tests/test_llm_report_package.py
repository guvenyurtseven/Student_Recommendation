from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from student_planner.domain.planning import (
    CourseRecommendation,
    PlanningGoal,
    PlanningReport,
    PlanningWarning,
    PlanningWarningSeverity,
    RecommendationScenario,
)
from student_planner.services.llm_report_package import (
    build_llm_report_package,
    build_llm_user_message,
    load_preprompt,
)
from student_planner.services.planning_io import planning_report_to_text


class LLMReportPackageTests(unittest.TestCase):
    def test_build_llm_report_package_wraps_deterministic_report(self) -> None:
        report = sample_report()

        package = build_llm_report_package(report)

        self.assertEqual(package.task, "student_planner_semester_narrative")
        self.assertEqual(package.prompt_version, "student-planner-report-v1")
        self.assertIn("deterministic planning report", package.system_prompt)
        self.assertIn("# CENG Next-Semester Planning Report", package.deterministic_report_markdown)
        self.assertIn("FREE_ELECTIVE", package.deterministic_report_markdown)
        self.assertEqual(package.metadata["program_abbr"], "CENG")
        self.assertEqual(package.metadata["target_semester_no"], "20252")
        self.assertEqual(package.metadata["placeholder_elective_count"], 1)
        self.assertEqual(package.model_policy["primary_model_tier"], "mini")
        self.assertTrue(package.response_contract["must_not_change_deterministic_decisions"])

    def test_build_llm_user_message_adds_clear_report_boundary(self) -> None:
        package = build_llm_report_package(sample_report())

        message = build_llm_user_message(package)

        self.assertIn("<deterministic_report>", message)
        self.assertIn("</deterministic_report>", message)
        self.assertIn("Balanced Progress", message)

    def test_planning_report_to_text_can_render_llm_package_json(self) -> None:
        payload = json.loads(planning_report_to_text(sample_report(), output_format="llm-package"))

        self.assertEqual(payload["task"], "student_planner_semester_narrative")
        self.assertEqual(payload["response_contract"]["format"], "markdown")
        self.assertIn("deterministic_report_markdown", payload)
        self.assertIn("system_prompt", payload)
        self.assertEqual(payload["metadata"]["warning_count"], 1)

    def test_load_preprompt_rejects_empty_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_path = Path(temp_dir) / "empty.md"
            prompt_path.write_text("", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_preprompt(prompt_path)


def sample_report() -> PlanningReport:
    return PlanningReport(
        program_abbr="CENG",
        goal=PlanningGoal("20252", difficulty_preference="balanced"),
        generated_at_utc="2026-05-11T00:00:00+00:00",
        scenarios=(
            RecommendationScenario(
                name="Balanced Progress",
                kind="balanced",
                total_ects=11.5,
                courses=(
                    CourseRecommendation(
                        course_code="CENG 213",
                        priority_score=80,
                        estimated_ects=6.5,
                    ),
                    CourseRecommendation(
                        course_code="FREE_ELECTIVE",
                        priority_score=20,
                        estimated_ects=5,
                        is_placeholder=True,
                        is_user_requested=True,
                        requires_explicit_course_selection=True,
                    ),
                ),
            ),
        ),
        warnings=(
            PlanningWarning(
                code="elective_course_selection_required",
                message="A concrete elective course must be selected.",
                severity=PlanningWarningSeverity.INFO,
            ),
        ),
        metadata={"preferred_scenario_kind": "balanced"},
    )


if __name__ == "__main__":
    unittest.main()
