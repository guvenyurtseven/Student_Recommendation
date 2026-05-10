from __future__ import annotations

import unittest

from student_planner.domain.grades import Grade
from student_planner.services.prerequisite_evaluator import (
    CompletedCourse,
    PrerequisiteEdge,
    build_completed_course_index,
    canonicalize_course_code,
    evaluate_eligibility,
    normalize_course_code,
)


class PrerequisiteEvaluatorTests(unittest.TestCase):
    def test_normalize_course_code(self) -> None:
        self.assertEqual(normalize_course_code("ceng140"), "CENG 140")
        self.assertEqual(normalize_course_code(" CENG   140 "), "CENG 140")
        self.assertEqual(normalize_course_code("355 140"), "355 140")
        self.assertEqual(normalize_course_code("5710140"), "5710140")

    def test_canonicalize_course_code_uses_aliases(self) -> None:
        aliases = {"355 140": "CENG 140", "5710140": "CENG 140"}
        self.assertEqual(canonicalize_course_code("355 140", aliases), "CENG 140")
        self.assertEqual(canonicalize_course_code("5710140", aliases), "CENG 140")
        self.assertEqual(canonicalize_course_code("CENG140", aliases), "CENG 140")

    def test_no_prerequisite_records_is_eligible(self) -> None:
        result = evaluate_eligibility(
            "CENG 111",
            prerequisite_edges=[],
            completed_courses={},
        )
        self.assertTrue(result.is_eligible)
        self.assertEqual(result.set_evaluations, ())
        self.assertIn("no prerequisite", result.explanation)

    def test_single_prerequisite_is_eligible_when_completed_with_minimum_grade(self) -> None:
        result = evaluate_eligibility(
            "MATH 120",
            prerequisite_edges=[
                PrerequisiteEdge("MATH 119", "MATH 120", set_no="1", min_grade="DD"),
            ],
            completed_courses={"MATH119": "DD"},
        )
        self.assertTrue(result.is_eligible)
        self.assertEqual(result.satisfied_set_nos, ("1",))
        self.assertEqual(result.missing_by_set, {})

    def test_single_prerequisite_is_blocked_when_grade_is_insufficient(self) -> None:
        result = evaluate_eligibility(
            "MATH 120",
            prerequisite_edges=[
                PrerequisiteEdge("MATH 119", "MATH 120", set_no="1", min_grade="DD"),
            ],
            completed_courses={"MATH 119": "FD"},
        )
        self.assertFalse(result.is_eligible)
        missing = result.missing_by_set["1"][0]
        self.assertEqual(missing.prerequisite_course_code, "MATH 119")
        self.assertEqual(missing.earned_grade, Grade.FD)
        self.assertEqual(missing.reason, "insufficient_grade")

    def test_same_set_is_and_logic(self) -> None:
        result = evaluate_eligibility(
            "CENG 384",
            prerequisite_edges=[
                PrerequisiteEdge("MATH 219", "CENG 384", set_no="1", min_grade="DD"),
                PrerequisiteEdge("MATH 260", "CENG 384", set_no="1", min_grade="DD"),
            ],
            completed_courses={"MATH 219": "CB"},
        )
        self.assertFalse(result.is_eligible)
        self.assertEqual([item.prerequisite_course_code for item in result.missing_by_set["1"]], ["MATH 260"])

        result = evaluate_eligibility(
            "CENG 384",
            prerequisite_edges=[
                PrerequisiteEdge("MATH 219", "CENG 384", set_no="1", min_grade="DD"),
                PrerequisiteEdge("MATH 260", "CENG 384", set_no="1", min_grade="DD"),
            ],
            completed_courses={"MATH 219": "CB", "MATH 260": "DD"},
        )
        self.assertTrue(result.is_eligible)

    def test_different_sets_are_or_logic(self) -> None:
        result = evaluate_eligibility(
            "MATH 120",
            prerequisite_edges=[
                PrerequisiteEdge("MATH 119", "MATH 120", set_no="1", min_grade="DD"),
                PrerequisiteEdge("357 119", "MATH 120", set_no="2", min_grade="DD"),
            ],
            completed_courses={"357 119": "CC"},
        )
        self.assertTrue(result.is_eligible)
        self.assertEqual(result.satisfied_set_nos, ("2",))
        self.assertIn("1", result.missing_by_set)
        self.assertNotIn("2", result.missing_by_set)

    def test_s_u_and_ex_grades_work_for_prerequisites(self) -> None:
        result = evaluate_eligibility(
            "HIST 2202",
            prerequisite_edges=[
                PrerequisiteEdge("HIST 2201", "HIST 2202", set_no="1", min_grade="U"),
            ],
            completed_courses={"HIST 2201": "U"},
        )
        self.assertTrue(result.is_eligible)

        result = evaluate_eligibility(
            "ENG 102",
            prerequisite_edges=[
                PrerequisiteEdge("ENG 101", "ENG 102", set_no="1", min_grade="S"),
            ],
            completed_courses={"ENG 101": "EX"},
        )
        self.assertTrue(result.is_eligible)

    def test_withdrawn_course_does_not_satisfy_prerequisite(self) -> None:
        result = evaluate_eligibility(
            "CENG 213",
            prerequisite_edges=[
                PrerequisiteEdge("CENG 140", "CENG 213", set_no="1", min_grade="DD"),
            ],
            completed_courses={"CENG 140": "W"},
        )
        self.assertFalse(result.is_eligible)
        self.assertEqual(result.missing_by_set["1"][0].reason, "insufficient_grade")

    def test_aliases_apply_to_completed_courses_and_edges(self) -> None:
        aliases = {"355 140": "CENG 140", "5710140": "CENG 140"}
        result = evaluate_eligibility(
            "CENG 213",
            prerequisite_edges=[
                PrerequisiteEdge("355 140", "CENG 213", set_no="1", min_grade="DD"),
            ],
            completed_courses={"5710140": "CC"},
            aliases=aliases,
        )
        self.assertTrue(result.is_eligible)
        requirement = result.set_evaluations[0].requirements[0]
        self.assertEqual(requirement.prerequisite_course_code, "CENG 140")

    def test_latest_attempt_wins_for_repeated_courses_by_input_order(self) -> None:
        completed = build_completed_course_index(
            [
                CompletedCourse("CENG 140", "CC"),
                CompletedCourse("ceng140", "FD"),
            ]
        )
        self.assertEqual(completed["CENG 140"], Grade.FD)

    def test_latest_attempt_wins_for_repeated_courses_by_semester(self) -> None:
        completed = build_completed_course_index(
            [
                CompletedCourse("CENG 140", "FD", completed_semester_no="20242"),
                CompletedCourse("ceng140", "CC", completed_semester_no="20231"),
            ]
        )
        self.assertEqual(completed["CENG 140"], Grade.FD)

    def test_latest_attempt_wins_for_repeated_courses_by_attempt_order(self) -> None:
        completed = build_completed_course_index(
            [
                CompletedCourse("CENG 140", "FD", attempt_order=2),
                CompletedCourse("ceng140", "CC", attempt_order=1),
            ]
        )
        self.assertEqual(completed["CENG 140"], Grade.FD)

    def test_failed_retake_of_transitive_prerequisite_does_not_block_target(self) -> None:
        edges = [
            PrerequisiteEdge("MATH 119", "MATH 120", set_no="1", min_grade="DD"),
            PrerequisiteEdge("MATH 120", "MATH 219", set_no="1", min_grade="DD"),
        ]
        result = evaluate_eligibility(
            "MATH 219",
            prerequisite_edges=edges,
            completed_courses=[
                CompletedCourse("MATH 119", "DD", attempt_order=1),
                CompletedCourse("MATH 120", "DD", attempt_order=2),
                CompletedCourse("MATH 119", "FF", attempt_order=3),
            ],
        )
        self.assertTrue(result.is_eligible)
        self.assertEqual(result.satisfied_set_nos, ("1",))

    def test_failed_latest_retake_of_direct_prerequisite_blocks_target(self) -> None:
        result = evaluate_eligibility(
            "MATH 120",
            prerequisite_edges=[
                PrerequisiteEdge("MATH 119", "MATH 120", set_no="1", min_grade="DD"),
            ],
            completed_courses=[
                CompletedCourse("MATH 119", "DD", attempt_order=1),
                CompletedCourse("MATH 119", "FF", attempt_order=2),
            ],
        )
        self.assertFalse(result.is_eligible)
        self.assertEqual(result.missing_by_set["1"][0].earned_grade, Grade.FF)


if __name__ == "__main__":
    unittest.main()
