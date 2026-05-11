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
    CourseEligibilitySummary,
    CourseRecommendation,
    PlanningGoal,
    RecommendationScenario,
    StudentPlanningInput,
)
from student_planner.services.candidate_courses import CandidateCourse, CandidateCourseResult
from student_planner.services.recommendation import RecommendationResult
from student_planner.services.registration_policy import AcademicRegistrationPolicyService


class AcademicRegistrationPolicyServiceTests(unittest.TestCase):
    def test_probation_blocks_new_courses_even_when_cgpa_is_above_1_70(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(CompletedCourseAttempt("CENG 140", "FF", attempt_order=1),),
            goal=PlanningGoal("20252"),
            metadata={
                "transcript_parse": {
                    "latest_standing": "PROBATION",
                    "latest_cgpa": 1.85,
                    "latest_gpa": 1.9,
                    "latest_standing_semester_no": "20251",
                }
            },
        )
        result = AcademicRegistrationPolicyService().apply_to_candidates(
            planning_input=planning_input,
            candidate_result=CandidateCourseResult(
                eligible_courses=(
                    candidate("CENG 140"),
                    candidate("MATH 120"),
                ),
                blocked_courses=(),
            ),
            curriculum=curriculum_snapshot(),
        )

        self.assertEqual(result.candidate_result.eligible_course_codes, ("CENG 140",))
        self.assertEqual(result.candidate_result.blocked_course_codes, ("MATH 120",))
        self.assertTrue(result.candidate_result.eligible_courses[0].is_repeat_priority)
        self.assertFalse(result.candidate_result.eligible_courses[0].is_new_course)
        self.assertIn("probation_new_course_block", {warning.code for warning in result.candidate_result.warnings})

    def test_non_probation_flags_new_and_repeat_priority_without_blocking(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(CompletedCourseAttempt("CENG 140", "NA", attempt_order=1),),
            goal=PlanningGoal("20252"),
            metadata={"transcript_parse": {"latest_standing": "SATISFACTORY", "latest_cgpa": 2.2}},
        )
        result = AcademicRegistrationPolicyService().apply_to_candidates(
            planning_input=planning_input,
            candidate_result=CandidateCourseResult(
                eligible_courses=(candidate("CENG 140"), candidate("MATH 120")),
                blocked_courses=(),
            ),
            curriculum=curriculum_snapshot(),
        )

        by_code = {course.course_code: course for course in result.candidate_result.eligible_courses}
        self.assertTrue(by_code["CENG 140"].is_repeat_priority)
        self.assertFalse(by_code["CENG 140"].is_new_course)
        self.assertFalse(by_code["MATH 120"].is_repeat_priority)
        self.assertTrue(by_code["MATH 120"].is_new_course)

    def test_recommendation_scenarios_are_trimmed_to_course_load_cap(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(),
            goal=PlanningGoal("20252"),
            metadata={"transcript_parse": {"latest_standing": "SATISFACTORY", "latest_cgpa": 1.95}},
        )
        service = AcademicRegistrationPolicyService()
        state = service.build_state(planning_input, curriculum_snapshot(normal_load=2))
        result = service.apply_to_recommendations(
            RecommendationResult(
                scenarios=(
                    RecommendationScenario(
                        name="Balanced Progress",
                        kind="balanced",
                        courses=(
                            recommendation("CENG 140"),
                            recommendation("MATH 119"),
                            recommendation("PHYS 105"),
                        ),
                    ),
                )
            ),
            state,
        )

        scenario = result.scenarios[0]
        self.assertEqual(scenario.course_codes, ("CENG 140", "MATH 119"))
        self.assertIn("scenario_trimmed_to_course_load_cap", {warning.code for warning in scenario.warnings})
        self.assertEqual(scenario.total_ects, 12)


def candidate(course_code: str) -> CandidateCourse:
    return CandidateCourse(
        course_code=course_code,
        eligibility=CourseEligibilitySummary(course_code=course_code, is_eligible=True),
        estimated_ects=6,
        estimated_credits=4,
    )


def recommendation(course_code: str) -> CourseRecommendation:
    return CourseRecommendation(
        course_code=course_code,
        priority_score=50,
        estimated_ects=6,
        estimated_credits=4,
        difficulty_score=0.5,
    )


def curriculum_snapshot(normal_load: int = 3) -> CurriculumSnapshot:
    requirements = []
    for index in range(1, normal_load + 1):
        display_code = f"CENG {100 + index}"
        requirements.append(
            CurriculumRequirementRecord(
                id=index,
                requirement_type=RequirementType.REQUIRED_COURSE,
                label=display_code,
                recommended_year=1,
                recommended_term="Fall",
                course_count_min=1,
                credits_min=4,
                ects_min=6,
                options=(
                    CurriculumRequirementOption(
                        id=index,
                        course=Course(
                            numeric_code=f"5710{100 + index}",
                            subject_code="CENG",
                            course_number=100 + index,
                            display_code=display_code,
                        ),
                    ),
                ),
            )
        )
    return CurriculumSnapshot(
        program=Program(
            abbr="CENG",
            catalog_program_id="571",
            name_en="Computer Engineering",
            name_tr="Bilgisayar Muhendisligi",
            faculty="Engineering",
        ),
        version_id=1,
        version_label="latest",
        is_latest=True,
        review_status=ReviewStatus.SCRAPED,
        requirements=tuple(requirements),
    )


if __name__ == "__main__":
    unittest.main()
