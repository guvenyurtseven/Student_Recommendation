from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from student_planner.domain.planning import (
    CompletedCourseAttempt,
    DifficultyPreference,
    PlanningGoal,
    PlanningReport,
    PlanningWarning,
    PlanningWarningSeverity,
    StudentPlanningInput,
)
from student_planner.services.planning_io import (
    load_student_planning_input,
    planning_report_to_dict,
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
            }
        )

        self.assertEqual(planning_input.program_abbr, "CENG")
        self.assertEqual(planning_input.completed_course_codes, ("MATH 119", "CENG 140"))
        self.assertEqual(planning_input.goal.difficulty_preference, DifficultyPreference.HARD)
        self.assertEqual(planning_input.goal.target_ects, 32)

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
