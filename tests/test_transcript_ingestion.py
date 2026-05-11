from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from student_planner.domain.planning import PlanningGoal
from student_planner.services.planning_io import student_planning_input_to_dict
from student_planner.services.transcript_ingestion import (
    TranscriptTextParser,
    build_planning_input_from_transcript_text,
)


SAMPLE_TRANSCRIPT_TEXT = """
Middle East Technical University
Student Transcript
FACULTY Engineering
DEPARTMENT/
PROGRAM
Computer Engineering

2024-2025 Fall
MATH 119 Calculus with Analytic Geometry I 4.0 7.5 DD
CENG 140 C Programming 4.0 6.5 CC

2024-2025 Spring
MATH 120 Calculus with Analytic Geometry II 4.0 7.5 BA
PHYS 105 General Physics I 4.0 6.0 BB
CumGPA: 2,47 GPA: 3,20 STAN: HONOR 20,00 64,00

2025-2026 Fall
MATH 119 Calculus with Analytic Geometry I 4.0 7.5 FF
CENG 213 Data Structures 4.0 7.0 IP
"""


SPLIT_TRANSCRIPT_TEXT = """
2019-2020 Spring / COVID-19 Pandemic
IS100 INTRODUCTION TO INFORMATION TECHNOLOGIES AND
APPLICATIONS
0,00 EX 0,00
2020-2021 Fall
MATH119 CALCULUS WITH ANALYTIC GEOMETRY 5,00 * DC * 7,50 *
"""


class TranscriptIngestionTests(unittest.TestCase):
    def test_parser_extracts_completed_and_in_progress_courses_without_raw_text(self) -> None:
        result = TranscriptTextParser().parse(SAMPLE_TRANSCRIPT_TEXT)

        self.assertEqual(
            tuple(course.course_code for course in result.completed_courses),
            ("MATH 119", "CENG 140", "MATH 120", "PHYS 105", "MATH 119"),
        )
        self.assertEqual(tuple(str(course.grade) for course in result.completed_courses), ("DD", "CC", "BA", "BB", "FF"))
        self.assertEqual(
            tuple(course.completed_semester_no for course in result.completed_courses),
            ("20241", "20241", "20242", "20242", "20251"),
        )
        self.assertEqual(tuple(course.attempt_order for course in result.completed_courses), (1, 2, 3, 4, 5))
        self.assertEqual(result.completed_courses[0].ects, 7.5)
        self.assertEqual(result.completed_courses[0].credits, 4.0)
        self.assertEqual(tuple(course.course_code for course in result.in_progress_courses), ("CENG 213",))
        self.assertEqual(result.in_progress_courses[0].semester_no, "20251")
        self.assertFalse(result.metadata["raw_transcript_retained"])
        self.assertEqual(result.metadata["detected_program_abbr"], "CENG")
        self.assertEqual(result.metadata["detected_program_name"], "Computer Engineering")
        self.assertEqual(result.metadata["latest_standing"], "HONOR")
        self.assertEqual(result.metadata["latest_cgpa"], 2.47)
        self.assertEqual(result.metadata["latest_gpa"], 3.2)
        self.assertEqual(result.metadata["latest_standing_semester_no"], "20242")
        self.assertNotIn("raw_text", result.metadata)
        self.assertNotIn("lines", result.metadata)

    def test_build_planning_input_from_transcript_text_keeps_only_planner_data(self) -> None:
        planning_input = build_planning_input_from_transcript_text(
            SAMPLE_TRANSCRIPT_TEXT,
            program_abbr=None,
            goal=PlanningGoal("20252", difficulty_preference="balanced"),
        )

        payload = student_planning_input_to_dict(planning_input)

        self.assertEqual(payload["program_abbr"], "CENG")
        self.assertEqual(payload["goal"]["target_semester_no"], "20252")
        self.assertEqual(payload["metadata"]["input_source"], "transcript_pdf")
        self.assertFalse(payload["metadata"]["transcript_parse"]["raw_transcript_retained"])
        self.assertEqual(len(payload["completed_courses"]), 5)
        self.assertEqual(payload["in_progress_courses"][0]["course_code"], "CENG 213")
        self.assertNotIn("Middle East Technical University", json.dumps(payload))
        self.assertNotIn("Student Transcript", json.dumps(payload))

    def test_parser_handles_metu_split_exemption_and_starred_rows(self) -> None:
        result = TranscriptTextParser().parse(SPLIT_TRANSCRIPT_TEXT)

        self.assertEqual(
            tuple((course.course_code, str(course.grade), course.completed_semester_no) for course in result.completed_courses),
            (("IS 100", "EX", "20192"), ("MATH 119", "DC", "20201")),
        )
        self.assertEqual(result.completed_courses[0].credits, 0.0)
        self.assertEqual(result.completed_courses[0].ects, 0.0)
        self.assertTrue(result.completed_courses[0].earns_credit)
        self.assertEqual(result.completed_courses[1].credits, 5.0)
        self.assertEqual(result.completed_courses[1].ects, 7.5)

    def test_cli_writes_planner_json_without_transcript_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            transcript_path = temp_path / "transcript.txt"
            output_path = temp_path / "planning_input.json"
            transcript_path.write_text(SAMPLE_TRANSCRIPT_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    "scripts/extract_transcript_planning_input.py",
                    "--transcript-text",
                    str(transcript_path),
                    "--program",
                    "CENG",
                    "--target-semester",
                    "20252",
                    "--output",
                    str(output_path),
                ],
                check=True,
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["program_abbr"], "CENG")
        self.assertEqual(payload["completed_courses"][0]["course_code"], "MATH 119")
        self.assertNotIn("Student Transcript", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
