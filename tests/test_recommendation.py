from __future__ import annotations

import unittest

from student_planner.domain.planning import RecommendationScenarioKind
from student_planner.services.difficulty import CourseLoadScore, CourseScoringResult, SemesterLoadTarget
from student_planner.domain.planning import DifficultyPreference
from student_planner.services.recommendation import RecommendationService


class RecommendationServiceTests(unittest.TestCase):
    def test_builds_easy_balanced_and_aggressive_scenarios(self) -> None:
        result = RecommendationService().build_scenarios(scoring_result())

        self.assertEqual(
            [scenario.kind for scenario in result.scenarios],
            [
                RecommendationScenarioKind.EASY,
                RecommendationScenarioKind.BALANCED,
                RecommendationScenarioKind.AGGRESSIVE,
            ],
        )
        self.assertEqual(result.preferred_kind, RecommendationScenarioKind.BALANCED)
        self.assertEqual(result.preferred_scenario.kind, RecommendationScenarioKind.BALANCED)

    def test_scenarios_respect_ects_caps(self) -> None:
        result = RecommendationService().build_scenarios(scoring_result())

        easy, balanced, aggressive = result.scenarios
        self.assertLessEqual(easy.total_ects, 10)
        self.assertLessEqual(balanced.total_ects, 14)
        self.assertLessEqual(aggressive.total_ects, 14)

    def test_easy_and_aggressive_sort_courses_differently(self) -> None:
        result = RecommendationService().build_scenarios(scoring_result())
        easy, _balanced, aggressive = result.scenarios

        self.assertEqual(easy.course_codes[0], "IS 100")
        self.assertEqual(aggressive.course_codes[0], "MATH 120")

    def test_empty_scoring_result_returns_warning(self) -> None:
        result = RecommendationService().build_scenarios(
            CourseScoringResult(
                load_target=SemesterLoadTarget(
                    difficulty_preference=DifficultyPreference.EASY,
                    min_ects=6,
                    target_ects=10,
                    max_ects=14,
                ),
                course_scores=(),
            )
        )

        self.assertEqual(result.scenarios, ())
        self.assertEqual(result.preferred_scenario, None)
        self.assertEqual(result.preferred_kind, RecommendationScenarioKind.EASY)
        self.assertEqual(result.warnings[0].code, "no_eligible_courses_for_recommendation")

    def test_underfilled_scenario_exposes_warning(self) -> None:
        result = RecommendationService().build_scenarios(
            CourseScoringResult(
                load_target=SemesterLoadTarget(
                    difficulty_preference=DifficultyPreference.BALANCED,
                    min_ects=12,
                    target_ects=18,
                    max_ects=24,
                ),
                course_scores=(score("IS 100", ects=1, difficulty=0.1, priority=10, unlock=0),),
            )
        )

        self.assertTrue(result.warnings)
        self.assertIn("scenario_below_minimum_load", {warning.code for warning in result.warnings})

    def test_course_recommendations_keep_rationale_and_scores(self) -> None:
        result = RecommendationService().build_scenarios(scoring_result())
        recommendation = result.preferred_scenario.courses[0]

        self.assertGreater(recommendation.priority_score, 0)
        self.assertGreater(recommendation.estimated_ects, 0)
        self.assertTrue(any("included in" in item for item in recommendation.rationale))


def scoring_result() -> CourseScoringResult:
    return CourseScoringResult(
        load_target=SemesterLoadTarget(
            difficulty_preference=DifficultyPreference.BALANCED,
            min_ects=6,
            target_ects=10,
            max_ects=14,
        ),
        course_scores=(
            score("MATH 120", ects=6, difficulty=0.50, priority=90, unlock=40),
            score("IS 100", ects=1, difficulty=0.10, priority=35, unlock=0),
            score("CENG 213", ects=6, difficulty=0.65, priority=70, unlock=20),
            score("PHYS 105", ects=5, difficulty=0.45, priority=75, unlock=30),
            score("ENG 101", ects=4, difficulty=0.30, priority=45, unlock=4),
        ),
    )


def score(
    course_code: str,
    ects: float,
    difficulty: float,
    priority: float,
    unlock: float,
) -> CourseLoadScore:
    return CourseLoadScore(
        course_code=course_code,
        estimated_ects=ects,
        estimated_credits=ects / 1.5,
        course_level=2,
        is_major_course=course_code.startswith("CENG"),
        unlock_score=unlock,
        semester_alignment_score=1.0,
        difficulty_score=difficulty,
        priority_score=priority,
        rationale=(f"{course_code} rationale",),
    )


if __name__ == "__main__":
    unittest.main()
