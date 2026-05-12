from __future__ import annotations

import base64
import unittest
from unittest.mock import patch

from student_planner.web.api import decode_pdf_payload, goal_from_payload, recommendation_from_transcript_payload


class WebApiTests(unittest.TestCase):
    def test_goal_from_payload_accepts_nested_goal(self) -> None:
        goal = goal_from_payload(
            {
                "program_abbr": "CENG",
                "goal": {
                    "target_semester_no": "20252",
                    "difficulty_preference": "hard",
                    "target_ects": 36,
                },
            }
        )

        self.assertEqual(goal.target_semester_no, "20252")
        self.assertEqual(goal.difficulty_preference, "hard")
        self.assertEqual(goal.target_ects, 36)

    def test_goal_from_payload_defaults_to_operation_semester(self) -> None:
        with patch("student_planner.web.api.load_operation_semester") as load_operation_semester:
            load_operation_semester.return_value.active_semester_no = "20252"

            goal = goal_from_payload({"difficulty_preference": "easy"})

        self.assertEqual(goal.target_semester_no, "20252")
        self.assertEqual(goal.difficulty_preference, "easy")

    def test_decode_pdf_payload_accepts_plain_or_data_url_base64(self) -> None:
        pdf_bytes = b"%PDF-1.4\nminimal"
        encoded = base64.b64encode(pdf_bytes).decode("ascii")

        self.assertEqual(decode_pdf_payload(encoded), pdf_bytes)
        self.assertEqual(decode_pdf_payload(f"data:application/pdf;base64,{encoded}"), pdf_bytes)

    def test_decode_pdf_payload_rejects_non_pdf_data(self) -> None:
        encoded = base64.b64encode(b"not a pdf").decode("ascii")

        with self.assertRaises(ValueError):
            decode_pdf_payload(encoded)

    def test_transcript_payload_without_program_uses_detected_program(self) -> None:
        transcript_text = """
        FACULTY Engineering
        DEPARTMENT/
        PROGRAM
        Computer Engineering
        2024-2025 Fall
        MATH119 CALCULUS WITH ANALYTIC GEOMETRY 5,00 DC 7,50
        """

        def fake_response(planning_input, _db_path):
            return {"ok": True, "program_abbr": planning_input.program_abbr}

        with (
            patch("student_planner.web.api.extract_text_from_pdf_bytes", return_value=transcript_text),
            patch("student_planner.web.api.recommendation_response", side_effect=fake_response),
        ):
            response = recommendation_from_transcript_payload(
                {
                    "file_base64": base64.b64encode(b"%PDF-1.4\nstub").decode("ascii"),
                    "goal": {"target_semester_no": "20252"},
                },
                "data/db/student_planner.sqlite",
            )

        self.assertEqual(response["program_abbr"], "CENG")


if __name__ == "__main__":
    unittest.main()
