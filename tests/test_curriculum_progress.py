from __future__ import annotations

import unittest

from student_planner.domain.models import (
    Course,
    CurriculumRequirementOption,
    CurriculumRequirementRecord,
    CurriculumSnapshot,
    Program,
    RequirementType,
    ReviewStatus,
)
from student_planner.domain.planning import (
    CompletedCourseAttempt,
    PlanningGoal,
    PlanningWarningSeverity,
    RequirementProgressStatus,
    StudentPlanningInput,
)
from student_planner.services.curriculum_progress import (
    CurriculumProgressService,
    latest_completed_credit_courses,
)


class CurriculumProgressServiceTests(unittest.TestCase):
    def test_latest_completed_credit_courses_uses_latest_attempt(self) -> None:
        completed = latest_completed_credit_courses(
            (
                CompletedCourseAttempt("CENG 140", "BB", attempt_order=1),
                CompletedCourseAttempt("ceng140", "FF", attempt_order=2),
                CompletedCourseAttempt("math119", "DD", completed_semester_no="20231"),
            )
        )

        self.assertNotIn("CENG 140", completed)
        self.assertIn("MATH 119", completed)

    def test_evaluate_marks_required_choice_and_review_only_requirements(self) -> None:
        service = CurriculumProgressService()
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(
                CompletedCourseAttempt("ceng140", "CC", attempt_order=1),
                CompletedCourseAttempt("math119", "FF", attempt_order=2),
                CompletedCourseAttempt("eng101", "S", attempt_order=3),
            ),
            goal=PlanningGoal("20252"),
        )

        result = service.evaluate(planning_input, ceng_curriculum_fixture())

        self.assertEqual(result.program_abbr, "CENG")
        self.assertEqual(len(result.requirements), 4)
        self.assertEqual(result.requirements[0].status, RequirementProgressStatus.SATISFIED)
        self.assertEqual(result.requirements[0].completed_course_codes, ("CENG 140",))
        self.assertEqual(result.requirements[1].status, RequirementProgressStatus.UNSATISFIED)
        self.assertEqual(result.requirements[1].remaining_course_codes, ("MATH 119",))
        self.assertEqual(result.requirements[2].status, RequirementProgressStatus.SATISFIED)
        self.assertEqual(result.requirements[2].completed_course_codes, ("ENG 101",))
        self.assertEqual(result.requirements[3].status, RequirementProgressStatus.NEEDS_REVIEW)
        self.assertEqual(result.remaining_concrete_course_codes, ("MATH 119",))
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].severity, PlanningWarningSeverity.WARNING)

    def test_aliases_are_used_when_matching_completed_courses(self) -> None:
        service = CurriculumProgressService(aliases={"5710140": "CENG 140", "355 140": "CENG 140"})
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(CompletedCourseAttempt("355 140", "DD"),),
            goal=PlanningGoal("20252"),
        )

        result = service.evaluate(planning_input, ceng_curriculum_fixture(requirement_count=1))

        self.assertEqual(result.requirements[0].status, RequirementProgressStatus.SATISFIED)
        self.assertEqual(result.requirements[0].completed_course_codes, ("CENG 140",))

    def test_program_mismatch_raises(self) -> None:
        service = CurriculumProgressService()
        planning_input = StudentPlanningInput(
            program_abbr="EEE",
            completed_courses=(),
            goal=PlanningGoal("20252"),
        )

        with self.assertRaises(ValueError):
            service.evaluate(planning_input, ceng_curriculum_fixture())


def ceng_curriculum_fixture(requirement_count: int = 4) -> CurriculumSnapshot:
    program = Program(
        abbr="CENG",
        catalog_program_id="571",
        name_en="Computer Engineering",
        name_tr="Bilgisayar Muhendisligi",
        faculty="Engineering",
    )
    requirements = (
        required_course(1, "CENG 140", 5710140, "CENG", 140, 6.0),
        required_course(2, "MATH 119", 2360119, "MATH", 119, 6.0),
        course_choice(
            3,
            "ENG 101 or ENG 102",
            (
                course("6390101", "ENG", 101, "ENG 101"),
                course("6390102", "ENG", 102, "ENG 102"),
            ),
        ),
        CurriculumRequirementRecord(
            id=4,
            requirement_type=RequirementType.TECHNICAL_ELECTIVE_POOL,
            label="Technical Elective",
            recommended_year=4,
            recommended_term="Spring",
            course_count_min=1,
            ects_min=5.0,
            sort_order=4,
            review_status=ReviewStatus.SCRAPED,
            options=(),
        ),
    )
    return CurriculumSnapshot(
        program=program,
        version_id=1,
        version_label="latest",
        is_latest=True,
        review_status=ReviewStatus.SCRAPED,
        requirements=requirements[:requirement_count],
    )


def required_course(
    requirement_id: int,
    display_code: str,
    numeric_code: int,
    subject_code: str,
    course_number: int,
    ects: float,
) -> CurriculumRequirementRecord:
    return CurriculumRequirementRecord(
        id=requirement_id,
        requirement_type=RequirementType.REQUIRED_COURSE,
        label=display_code,
        recommended_year=1,
        recommended_term="Fall",
        course_count_min=1,
        ects_min=ects,
        sort_order=requirement_id,
        review_status=ReviewStatus.SCRAPED,
        options=(
            CurriculumRequirementOption(
                id=requirement_id,
                course=course(str(numeric_code), subject_code, course_number, display_code),
                option_group=display_code,
            ),
        ),
    )


def course_choice(
    requirement_id: int,
    label: str,
    courses: tuple[Course, ...],
) -> CurriculumRequirementRecord:
    return CurriculumRequirementRecord(
        id=requirement_id,
        requirement_type=RequirementType.COURSE_CHOICE,
        label=label,
        recommended_year=1,
        recommended_term="Fall",
        course_count_min=1,
        ects_min=6.0,
        sort_order=requirement_id,
        review_status=ReviewStatus.SCRAPED,
        options=tuple(
            CurriculumRequirementOption(id=100 + index, course=course_item, option_group=label)
            for index, course_item in enumerate(courses, start=1)
        ),
    )


def course(numeric_code: str, subject_code: str, course_number: int, display_code: str) -> Course:
    return Course(
        numeric_code=numeric_code,
        subject_code=subject_code,
        course_number=course_number,
        display_code=display_code,
        title_en=display_code,
    )


if __name__ == "__main__":
    unittest.main()
