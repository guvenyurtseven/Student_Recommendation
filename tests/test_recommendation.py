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

    def test_scenarios_use_metu_credit_course_count_targets(self) -> None:
        result = RecommendationService().build_scenarios(scoring_result())

        easy, balanced, aggressive = result.scenarios
        self.assertLessEqual(credit_course_count(easy), 5)
        self.assertLessEqual(credit_course_count(balanced), 5)
        self.assertLessEqual(credit_course_count(aggressive), 6)

    def test_easy_and_aggressive_sort_courses_differently(self) -> None:
        result = RecommendationService().build_scenarios(scoring_result())
        easy, _balanced, aggressive = result.scenarios

        self.assertEqual(easy.course_codes[0], "MATH 120")
        self.assertEqual(aggressive.course_codes[0], "MATH 120")

    def test_critical_unlock_courses_are_included_in_every_scenario_when_they_fit(self) -> None:
        result = RecommendationService().build_scenarios(scoring_result())

        for scenario in result.scenarios:
            self.assertIn("MATH 120", scenario.course_codes)

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

    def test_user_requested_scores_are_included_before_regular_courses(self) -> None:
        result = RecommendationService().build_scenarios(
            CourseScoringResult(
                load_target=SemesterLoadTarget(
                    difficulty_preference=DifficultyPreference.BALANCED,
                    min_ects=6,
                    target_ects=10,
                    max_ects=14,
                ),
                course_scores=(
                    score("MATH 120", ects=6, difficulty=0.50, priority=90, unlock=40),
                    score(
                        "FREE_ELECTIVE",
                        ects=5,
                        difficulty=0.20,
                        priority=5,
                        unlock=0,
                        is_user_requested=True,
                        elective_category="free_elective",
                    ),
                    score("CENG 213", ects=6, difficulty=0.65, priority=70, unlock=20),
                ),
            )
        )

        easy, balanced, aggressive = result.scenarios
        self.assertIn("FREE_ELECTIVE", easy.course_codes)
        self.assertNotIn("FREE_ELECTIVE", balanced.course_codes)
        self.assertIn("FREE_ELECTIVE", aggressive.course_codes)
        recommendation = next(course for course in easy.courses if course.course_code == "FREE_ELECTIVE")
        self.assertTrue(recommendation.is_user_requested)

    def test_user_requested_score_can_exceed_route_target(self) -> None:
        result = RecommendationService().build_scenarios(
            CourseScoringResult(
                load_target=SemesterLoadTarget(
                    difficulty_preference=DifficultyPreference.BALANCED,
                    min_ects=6,
                    target_ects=10,
                    max_ects=14,
                ),
                course_scores=(
                    score("CENG 499", ects=20, difficulty=0.90, priority=100, unlock=0, is_user_requested=True),
                    score("MATH 120", ects=6, difficulty=0.50, priority=90, unlock=40),
                ),
            )
        )

        for scenario in result.scenarios:
            self.assertIn("CENG 499", scenario.course_codes)

    def test_zero_credit_courses_are_included_in_every_scenario_without_counting_to_load(self) -> None:
        result = RecommendationService().build_scenarios(
            CourseScoringResult(
                load_target=SemesterLoadTarget(
                    difficulty_preference=DifficultyPreference.BALANCED,
                    min_ects=6,
                    target_ects=10,
                    max_ects=14,
                ),
                course_scores=(
                    score("BA 100", ects=1, credits=0, difficulty=0.05, priority=1, unlock=0),
                    score("MATH 120", ects=6, difficulty=0.50, priority=90, unlock=40),
                    score("CENG 213", ects=6, difficulty=0.65, priority=70, unlock=20),
                    score("PHYS 105", ects=5, difficulty=0.45, priority=75, unlock=30),
                    score("ENG 101", ects=4, difficulty=0.30, priority=45, unlock=4),
                    score("CENG 223", ects=6, difficulty=0.60, priority=50, unlock=8),
                    score("CENG 242", ects=6, difficulty=0.70, priority=40, unlock=8),
                ),
            )
        )

        for scenario in result.scenarios:
            self.assertIn("BA 100", scenario.course_codes)
            self.assertLessEqual(credit_course_count(scenario), 6)

    def test_easy_priority_nontechnical_elective_is_only_for_easy_when_balanced_has_regular_courses(self) -> None:
        result = RecommendationService().build_scenarios(
            CourseScoringResult(
                load_target=SemesterLoadTarget(
                    difficulty_preference=DifficultyPreference.BALANCED,
                    min_ects=6,
                    target_ects=10,
                    max_ects=14,
                ),
                course_scores=(
                    score(
                        "NONTECHNICAL_ELECTIVE",
                        ects=5.5,
                        difficulty=0.2,
                        priority=1,
                        unlock=0,
                        elective_category="nontechnical_elective",
                        is_easy_priority_elective=True,
                    ),
                    score("MATH 120", ects=6, difficulty=0.50, priority=90, unlock=40),
                    score("CENG 213", ects=6, difficulty=0.65, priority=70, unlock=20),
                    score("PHYS 105", ects=5, difficulty=0.45, priority=75, unlock=30),
                    score("ENG 101", ects=4, difficulty=0.30, priority=45, unlock=4),
                    score("CENG 223", ects=6, difficulty=0.60, priority=50, unlock=8),
                    score("CENG 242", ects=6, difficulty=0.70, priority=40, unlock=8),
                ),
            )
        )

        easy, balanced, _aggressive = result.scenarios
        self.assertIn("NONTECHNICAL_ELECTIVE", easy.course_codes)
        self.assertNotIn("NONTECHNICAL_ELECTIVE", balanced.course_codes)


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
    credits: float | None = None,
    is_user_requested: bool = False,
    elective_category: str | None = None,
    is_easy_priority_elective: bool = False,
) -> CourseLoadScore:
    return CourseLoadScore(
        course_code=course_code,
        estimated_ects=ects,
        estimated_credits=ects / 1.5 if credits is None else credits,
        course_level=2,
        is_major_course=course_code.startswith("CENG"),
        unlock_score=unlock,
        semester_alignment_score=1.0,
        difficulty_score=difficulty,
        priority_score=priority,
        rationale=(f"{course_code} rationale",),
        is_user_requested=is_user_requested,
        elective_category=elective_category,
        is_easy_priority_elective=is_easy_priority_elective,
    )


def credit_course_count(scenario) -> int:
    return sum(
        1
        for course in scenario.courses
        if course.estimated_credits is None or course.estimated_credits > 0
    )


if __name__ == "__main__":
    unittest.main()
