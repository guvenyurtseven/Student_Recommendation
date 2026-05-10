from __future__ import annotations

import unittest

from student_planner.domain.planning import (
    CourseEligibilitySummary,
    DifficultyPreference,
    PlanningGoal,
)
from student_planner.services.candidate_courses import CandidateCourse, CandidateCourseResult
from student_planner.services.difficulty import (
    CourseScoringService,
    course_level_from_code,
    load_target_from_goal,
    semester_alignment_score,
)
from student_planner.services.unlock_analysis import CourseUnlockSummary, UnlockAnalysisResult


class DifficultyScoringTests(unittest.TestCase):
    def test_load_target_defaults_follow_preference_and_goal_overrides(self) -> None:
        easy = load_target_from_goal(PlanningGoal("20252", difficulty_preference="easy"))
        self.assertEqual(easy.difficulty_preference, DifficultyPreference.EASY)
        self.assertEqual((easy.min_ects, easy.target_ects, easy.max_ects), (18.0, 21.0, 24.0))

        custom = load_target_from_goal(
            PlanningGoal(
                "20252",
                difficulty_preference="hard",
                min_ects=28,
                target_ects=32,
                max_ects=36,
            )
        )
        self.assertEqual((custom.min_ects, custom.target_ects, custom.max_ects), (28, 32, 36))

    def test_semester_alignment_uses_metu_semester_suffix(self) -> None:
        self.assertEqual(semester_alignment_score("Spring", "20252"), 1.0)
        self.assertEqual(semester_alignment_score("Fall", "20252"), 0.35)
        self.assertEqual(semester_alignment_score(None, "20252"), 0.65)
        self.assertEqual(semester_alignment_score("Fall", "20253"), 0.25)

    def test_course_level_folds_four_digit_service_courses(self) -> None:
        self.assertEqual(course_level_from_code("CENG 213"), 2)
        self.assertEqual(course_level_from_code("CENG 491"), 4)
        self.assertEqual(course_level_from_code("HIST 2201"), 2)
        self.assertEqual(course_level_from_code("IS 100"), 1)

    def test_easy_preference_favors_lighter_course_when_unlocks_are_equal(self) -> None:
        result = CourseScoringService().score_eligible_candidates(
            candidate_result=CandidateCourseResult(
                eligible_courses=(
                    candidate("CENG 111", ects=4, recommended_term="Spring"),
                    candidate("CENG 491", ects=8, recommended_term="Spring"),
                ),
                blocked_courses=(),
            ),
            unlock_result=UnlockAnalysisResult(
                summaries=(
                    unlock("CENG 111", score=1, relevant=1),
                    unlock("CENG 491", score=1, relevant=1),
                )
            ),
            goal=PlanningGoal("20252", difficulty_preference="easy"),
            program_abbr="CENG",
        )

        self.assertEqual(result.ranked_courses[0].course_code, "CENG 111")
        self.assertLess(
            result.ranked_courses[0].difficulty_score,
            result.ranked_courses[1].difficulty_score,
        )

    def test_hard_preference_prioritizes_high_unlock_course(self) -> None:
        result = CourseScoringService().score_eligible_candidates(
            candidate_result=CandidateCourseResult(
                eligible_courses=(
                    candidate("CENG 111", ects=4, recommended_term="Spring"),
                    candidate("MATH 120", ects=6, recommended_term="Spring"),
                ),
                blocked_courses=(),
            ),
            unlock_result=UnlockAnalysisResult(
                summaries=(
                    unlock("CENG 111", score=1, relevant=1),
                    unlock("MATH 120", score=20, relevant=4),
                )
            ),
            goal=PlanningGoal("20252", difficulty_preference="hard"),
            program_abbr="CENG",
        )

        self.assertEqual(result.ranked_courses[0].course_code, "MATH 120")
        self.assertGreater(result.ranked_courses[0].priority_score, result.ranked_courses[1].priority_score)

    def test_scored_courses_convert_to_course_recommendations(self) -> None:
        result = CourseScoringService().score_eligible_candidates(
            candidate_result=CandidateCourseResult(
                eligible_courses=(candidate("MATH 120", ects=6, recommended_term="Spring"),),
                blocked_courses=(),
            ),
            unlock_result=UnlockAnalysisResult(
                summaries=(unlock("MATH 120", score=20, relevant=4),)
            ),
            goal=PlanningGoal("20252", difficulty_preference="balanced"),
            program_abbr="CENG",
        )

        recommendation = result.recommendations[0]
        self.assertEqual(recommendation.course_code, "MATH 120")
        self.assertEqual(recommendation.estimated_ects, 6)
        self.assertGreater(recommendation.priority_score, 0)
        self.assertGreater(recommendation.unlock_count, 0)


def candidate(course_code: str, ects: float | None, recommended_term: str | None) -> CandidateCourse:
    return CandidateCourse(
        course_code=course_code,
        eligibility=CourseEligibilitySummary(course_code, is_eligible=True),
        requirement_labels=(course_code,),
        recommended_year=1,
        recommended_term=recommended_term,
        estimated_ects=ects,
        estimated_credits=ects / 1.5 if ects is not None else None,
    )


def unlock(course_code: str, score: float, relevant: int) -> CourseUnlockSummary:
    relevant_courses = tuple(f"REL {index}" for index in range(relevant))
    return CourseUnlockSummary(
        course_code=course_code,
        direct_unlock_course_codes=relevant_courses,
        transitive_unlock_course_codes=relevant_courses,
        curriculum_relevant_unlock_course_codes=relevant_courses,
        longest_unlock_chain_length=max(0, relevant - 1),
        critical_path_score=score,
    )


if __name__ == "__main__":
    unittest.main()
