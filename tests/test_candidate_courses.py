from __future__ import annotations

import unittest

from student_planner.domain.models import RequirementType
from student_planner.domain.planning import (
    CompletedCourseAttempt,
    PlanningGoal,
    RequirementProgress,
    RequirementProgressStatus,
    StudentPlanningInput,
)
from student_planner.services.candidate_courses import CandidateCourseGenerator
from student_planner.services.curriculum_progress import CurriculumProgressResult
from student_planner.services.prerequisite_evaluator import PrerequisiteEdge


class CandidateCourseGeneratorTests(unittest.TestCase):
    def test_generate_splits_remaining_courses_into_eligible_and_blocked(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(CompletedCourseAttempt("ceng140", "CC"),),
            goal=PlanningGoal("20252"),
        )
        progress = progress_fixture()
        prerequisite_edges = {
            "CENG 213": [PrerequisiteEdge("CENG 140", "CENG 213", set_no="1", min_grade="DD")],
            "MATH 219": [PrerequisiteEdge("MATH 120", "MATH 219", set_no="1", min_grade="DD")],
        }

        result = CandidateCourseGenerator().generate(planning_input, progress, prerequisite_edges)

        self.assertEqual(result.eligible_course_codes, ("MATH 119", "CENG 213"))
        self.assertEqual(result.blocked_course_codes, ("MATH 219",))
        blocked = result.blocked_courses[0]
        self.assertEqual(blocked.eligibility.missing_prerequisite_codes, ("MATH 120",))
        self.assertEqual(blocked.requirement_labels, ("MATH 219",))
        self.assertEqual(blocked.estimated_ects, 6.0)

    def test_latest_failed_direct_prerequisite_attempt_blocks_candidate(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(
                CompletedCourseAttempt("math120", "DD", attempt_order=1),
                CompletedCourseAttempt("math120", "FF", attempt_order=2),
            ),
            goal=PlanningGoal("20252"),
        )
        progress = CurriculumProgressResult(
            program_abbr="CENG",
            curriculum_version_label="latest",
            requirements=(
                requirement_progress("MATH 219", ("MATH 219",)),
            ),
        )
        prerequisite_edges = {
            "MATH 219": [PrerequisiteEdge("MATH 120", "MATH 219", set_no="1", min_grade="DD")],
        }

        result = CandidateCourseGenerator().generate(planning_input, progress, prerequisite_edges)

        self.assertEqual(result.eligible_course_codes, ())
        self.assertEqual(result.blocked_course_codes, ("MATH 219",))
        self.assertEqual(result.blocked_courses[0].eligibility.missing_prerequisite_codes, ("MATH 120",))

    def test_aliases_are_used_when_evaluating_candidates(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(CompletedCourseAttempt("355 140", "DD"),),
            goal=PlanningGoal("20252"),
        )
        progress = CurriculumProgressResult(
            program_abbr="CENG",
            curriculum_version_label="latest",
            requirements=(
                requirement_progress("CENG 213", ("CENG 213",)),
            ),
        )
        prerequisite_edges = {
            "CENG 213": [PrerequisiteEdge("CENG 140", "CENG 213", set_no="1", min_grade="DD")],
        }

        result = CandidateCourseGenerator(aliases={"355 140": "CENG 140"}).generate(
            planning_input,
            progress,
            prerequisite_edges,
        )

        self.assertEqual(result.eligible_course_codes, ("CENG 213",))
        self.assertEqual(result.blocked_course_codes, ())

    def test_no_remaining_concrete_courses_adds_info_warning(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(),
            goal=PlanningGoal("20252"),
        )
        progress = CurriculumProgressResult(
            program_abbr="CENG",
            curriculum_version_label="latest",
            requirements=(),
        )

        result = CandidateCourseGenerator().generate(planning_input, progress, {})

        self.assertEqual(result.all_courses, ())
        self.assertEqual(result.warnings[0].code, "no_remaining_concrete_courses")


def progress_fixture() -> CurriculumProgressResult:
    return CurriculumProgressResult(
        program_abbr="CENG",
        curriculum_version_label="latest",
        requirements=(
            requirement_progress("MATH 119", ("MATH 119",)),
            requirement_progress("CENG 213", ("CENG 213",)),
            requirement_progress("MATH 219", ("MATH 219",)),
        ),
    )


def requirement_progress(label: str, remaining_course_codes: tuple[str, ...]) -> RequirementProgress:
    return RequirementProgress(
        requirement_label=label,
        requirement_type=RequirementType.REQUIRED_COURSE,
        status=RequirementProgressStatus.UNSATISFIED,
        remaining_course_codes=remaining_course_codes,
        option_course_codes=remaining_course_codes,
        ects_min=6.0,
    )


if __name__ == "__main__":
    unittest.main()
