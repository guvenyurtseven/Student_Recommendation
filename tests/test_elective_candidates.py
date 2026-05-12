from __future__ import annotations

import unittest

from student_planner.domain.electives import ElectiveIntent
from student_planner.domain.planning import CompletedCourseAttempt, PlanningGoal, StudentPlanningInput
from student_planner.services.elective_candidates import ElectiveCandidateService
from student_planner.services.prerequisite_evaluator import PrerequisiteEdge


class ElectiveCandidateServiceTests(unittest.TestCase):
    def test_builds_placeholder_candidate_for_category_only_intent(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(),
            goal=PlanningGoal("20252"),
            elective_intents=(ElectiveIntent("free_elective"),),
        )

        result = ElectiveCandidateService().build(
            planning_input,
            prerequisite_edges_by_course={},
        )

        self.assertEqual(result.explicit_count, 0)
        self.assertEqual(result.placeholder_count, 1)
        placeholder = result.placeholder_result.eligible_courses[0]
        self.assertEqual(placeholder.course_code, "FREE_ELECTIVE")
        self.assertEqual(placeholder.estimated_ects, 5.0)
        self.assertTrue(placeholder.is_placeholder)
        self.assertTrue(placeholder.is_user_requested)
        self.assertTrue(placeholder.requires_explicit_course_selection)
        self.assertEqual(result.warnings[0].code, "elective_course_selection_required")

    def test_builds_explicit_candidate_with_db_ects_and_prerequisites(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(CompletedCourseAttempt("CENG 213", "CC"),),
            goal=PlanningGoal("20252"),
            elective_intents=(ElectiveIntent("technical_elective", course_code="ceng495"),),
        )

        result = ElectiveCandidateService().build(
            planning_input,
            prerequisite_edges_by_course={
                "CENG 495": [PrerequisiteEdge("CENG 213", "CENG 495", set_no="1")],
            },
            course_ects_estimates={"CENG 495": 8.0},
        )

        self.assertEqual(result.placeholder_count, 0)
        self.assertEqual(result.explicit_count, 1)
        candidate = result.explicit_result.eligible_courses[0]
        self.assertEqual(candidate.course_code, "CENG 495")
        self.assertEqual(candidate.estimated_ects, 8.0)
        self.assertEqual(candidate.difficulty_rank, 4)
        self.assertFalse(candidate.is_placeholder)
        self.assertTrue(candidate.is_user_requested)
        self.assertTrue(any("uses DB ECTS estimate" in item for item in candidate.rationale))

    def test_explicit_candidate_can_be_blocked_by_missing_prerequisite(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(),
            goal=PlanningGoal("20252"),
            elective_intents=(ElectiveIntent("technical_elective", course_code="ceng495"),),
        )

        result = ElectiveCandidateService().build(
            planning_input,
            prerequisite_edges_by_course={
                "CENG 495": [PrerequisiteEdge("CENG 213", "CENG 495", set_no="1")],
            },
        )

        self.assertEqual(result.explicit_result.eligible_courses, ())
        self.assertEqual(result.explicit_result.blocked_courses[0].course_code, "CENG 495")
        self.assertEqual(
            result.explicit_result.blocked_courses[0].eligibility.missing_prerequisite_codes,
            ("CENG 213",),
        )


if __name__ == "__main__":
    unittest.main()
