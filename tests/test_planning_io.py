from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from student_planner.domain.planning import (
    CompletedCourseAttempt,
    CourseRecommendation,
    DifficultyPreference,
    PlanningGoal,
    PlanningReport,
    PlanningWarning,
    PlanningWarningSeverity,
    RecommendationScenario,
    StudentPlanningInput,
)
from student_planner.domain.electives import ElectiveCategory
from student_planner.services.planning_io import (
    load_student_planning_input,
    planning_report_to_dict,
    planning_report_to_text,
    student_planning_input_from_dict,
)


class PlanningIOTests(unittest.TestCase):
    def test_student_planning_input_from_dict_accepts_objects_and_compact_completed_courses(self) -> None:
        planning_input = student_planning_input_from_dict(
            {
                "program": "ceng",
                "completed_courses": [
                    "MATH 119:DD",
                    {
                        "course_code": "CENG 140",
                        "grade": "CC",
                        "completed_semester_no": "20241",
                        "attempt_order": 2,
                    },
                ],
                "goal": {
                    "target_semester": "20252",
                    "difficulty_preference": "hard",
                    "target_ects": 32,
                },
                "elective_intents": [
                    {"category": "technical_elective", "course_code": "ceng495"},
                    {"category": "free_elective"},
                ],
            }
        )

        self.assertEqual(planning_input.program_abbr, "CENG")
        self.assertEqual(planning_input.completed_course_codes, ("MATH 119", "CENG 140"))
        self.assertEqual(planning_input.goal.difficulty_preference, DifficultyPreference.HARD)
        self.assertEqual(planning_input.goal.target_ects, 32)
        self.assertEqual(len(planning_input.elective_intents), 2)
        self.assertEqual(planning_input.elective_intents[0].category, ElectiveCategory.TECHNICAL)
        self.assertEqual(planning_input.elective_intents[0].course_code, "CENG 495")
        self.assertTrue(planning_input.elective_intents[1].requires_explicit_course_selection)

    def test_student_planning_input_from_dict_accepts_checkbox_style_elective_preferences(self) -> None:
        planning_input = student_planning_input_from_dict(
            {
                "program": "CENG",
                "completed_courses": [],
                "goal": {"target_semester": "20252"},
                "elective_preferences": {
                    "technical_elective": {"wants_to_take": True, "course": "ceng495"},
                    "restricted_elective": False,
                    "nontechnical_elective": {"selected": "yes"},
                    "free_elective": {"wants_to_take": "no"},
                },
            }
        )

        self.assertEqual(
            tuple(intent.category for intent in planning_input.elective_intents),
            (ElectiveCategory.TECHNICAL, ElectiveCategory.NONTECHNICAL),
        )
        self.assertEqual(planning_input.elective_intents[0].course_code, "CENG 495")
        self.assertIsNone(planning_input.elective_intents[1].course_code)

    def test_load_student_planning_input_reads_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "input.json"
            path.write_text(
                json.dumps(
                    {
                        "program_abbr": "CENG",
                        "completed_courses": [],
                        "goal": {"target_semester_no": "20252"},
                    }
                ),
                encoding="utf-8",
            )

            planning_input = load_student_planning_input(path)

        self.assertEqual(planning_input.program_abbr, "CENG")
        self.assertEqual(planning_input.goal.difficulty_preference, DifficultyPreference.BALANCED)

    def test_planning_report_to_dict_serializes_enums_and_tuples(self) -> None:
        report = PlanningReport(
            program_abbr="CENG",
            goal=PlanningGoal("20252"),
            generated_at_utc="2026-05-10T00:00:00+00:00",
            warnings=(
                PlanningWarning(
                    code="offerings_unavailable",
                    message="Offerings are not loaded.",
                    severity=PlanningWarningSeverity.WARNING,
                ),
            ),
            metadata={"preferred_scenario_kind": "balanced"},
        )

        payload = planning_report_to_dict(report)

        self.assertEqual(payload["program_abbr"], "CENG")
        self.assertEqual(payload["goal"]["difficulty_preference"], "balanced")
        self.assertEqual(payload["warnings"][0]["severity"], "warning")
        self.assertEqual(payload["metadata"]["preferred_scenario_kind"], "balanced")

    def test_planning_report_to_text_can_render_markdown(self) -> None:
        report = PlanningReport(
            program_abbr="CENG",
            goal=PlanningGoal("20252", difficulty_preference="balanced"),
            generated_at_utc="2026-05-10T00:00:00+00:00",
            scenarios=(
                RecommendationScenario(
                    name="Balanced Progress",
                    kind="balanced",
                    total_ects=11.5,
                    difficulty_score=0.42,
                    courses=(
                        CourseRecommendation(
                            course_code="CENG 213",
                            priority_score=80,
                            estimated_ects=6.5,
                            difficulty_score=0.6,
                        ),
                        CourseRecommendation(
                            course_code="FREE_ELECTIVE",
                            priority_score=20,
                            estimated_ects=5,
                            difficulty_score=0.2,
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
            metadata={
                "preferred_scenario_kind": "balanced",
                "target_semester_offerings_count": 654,
                "offered_candidate_count": 2,
                "not_offered_candidate_count": 1,
                "unknown_offering_candidate_count": 0,
                "elective_remaining_slots_by_category": {"free_elective": 1},
                "elective_requested_counts_by_category": {"free_elective": 1},
                "elective_matched_counts_by_category": {"free_elective": 1},
                "elective_unplanned_counts_by_category": {"free_elective": 0},
                "elective_extra_counts_by_category": {"free_elective": 0},
            },
        )

        markdown = planning_report_to_text(report, output_format="markdown")

        self.assertIn("# CENG Next-Semester Planning Report", markdown)
        self.assertIn("## Elective Fit", markdown)
        self.assertIn("FREE_ELECTIVE", markdown)
        self.assertIn("needs concrete course", markdown)
        self.assertIn("elective_course_selection_required", markdown)

    def test_invalid_payloads_raise_clear_errors(self) -> None:
        with self.assertRaises(ValueError):
            student_planning_input_from_dict({"completed_courses": [], "goal": {}})
        with self.assertRaises(ValueError):
            student_planning_input_from_dict({"program": "CENG", "completed_courses": [], "goal": {}})
        with self.assertRaises(ValueError):
            student_planning_input_from_dict(
                {"program": "CENG", "completed_courses": ["MATH 119"], "goal": {"target_semester": "20252"}}
            )


if __name__ == "__main__":
    unittest.main()
