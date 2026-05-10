from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from student_planner.domain.planning import (
    CourseRecommendation,
    DifficultyPreference,
    PlanningWarning,
    PlanningWarningSeverity,
    RecommendationScenario,
    RecommendationScenarioKind,
)
from student_planner.services.difficulty import CourseLoadScore, CourseScoringResult, SemesterLoadTarget


class ScenarioSortMode(StrEnum):
    LOW_LOAD = "low_load"
    BALANCED_PRIORITY = "balanced_priority"
    UNLOCK_FIRST = "unlock_first"


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    kind: RecommendationScenarioKind
    target_ects: float
    max_ects: float
    warning_min_ects: float
    sort_mode: ScenarioSortMode


@dataclass(frozen=True)
class RecommendationResult:
    scenarios: tuple[RecommendationScenario, ...]
    warnings: tuple[PlanningWarning, ...] = ()
    preferred_kind: RecommendationScenarioKind = RecommendationScenarioKind.BALANCED

    @property
    def preferred_scenario(self) -> RecommendationScenario | None:
        for scenario in self.scenarios:
            if scenario.kind == self.preferred_kind:
                return scenario
        return self.scenarios[0] if self.scenarios else None


class RecommendationService:
    """Build first-pass course basket scenarios from scored eligible courses."""

    def build_scenarios(self, scoring_result: CourseScoringResult) -> RecommendationResult:
        if not scoring_result.course_scores:
            return RecommendationResult(
                scenarios=(),
                warnings=(
                    PlanningWarning(
                        code="no_eligible_courses_for_recommendation",
                        message="No eligible scored courses were available to build recommendation scenarios.",
                        severity=PlanningWarningSeverity.WARNING,
                    ),
                ),
                preferred_kind=preferred_kind_for(scoring_result.load_target.difficulty_preference),
            )

        scenarios = tuple(
            self.build_scenario(scoring_result.course_scores, config)
            for config in scenario_configs(scoring_result.load_target)
        )
        return RecommendationResult(
            scenarios=scenarios,
            warnings=tuple(warning for scenario in scenarios for warning in scenario.warnings),
            preferred_kind=preferred_kind_for(scoring_result.load_target.difficulty_preference),
        )

    def build_scenario(
        self,
        course_scores: tuple[CourseLoadScore, ...],
        config: ScenarioConfig,
    ) -> RecommendationScenario:
        sorted_scores = sort_scores(course_scores, config.sort_mode)
        selected_scores = select_course_basket(sorted_scores, config.target_ects, config.max_ects)
        total_ects = sum(score.estimated_ects for score in selected_scores)
        total_credits = total_known_credits(selected_scores)
        average_difficulty = weighted_average_difficulty(selected_scores)
        warnings = scenario_warnings(config, selected_scores, total_ects)
        return RecommendationScenario(
            name=config.name,
            kind=config.kind,
            courses=tuple(to_recommendation(score, config) for score in selected_scores),
            rationale=scenario_rationale(config, selected_scores, total_ects, average_difficulty),
            total_ects=total_ects,
            total_credits=total_credits,
            difficulty_score=average_difficulty,
            warnings=warnings,
        )


def scenario_configs(load_target: SemesterLoadTarget) -> tuple[ScenarioConfig, ...]:
    return (
        ScenarioConfig(
            name="Easy Load",
            kind=RecommendationScenarioKind.EASY,
            target_ects=load_target.min_ects,
            max_ects=min(load_target.target_ects, load_target.max_ects),
            warning_min_ects=load_target.min_ects,
            sort_mode=ScenarioSortMode.LOW_LOAD,
        ),
        ScenarioConfig(
            name="Balanced Progress",
            kind=RecommendationScenarioKind.BALANCED,
            target_ects=load_target.target_ects,
            max_ects=load_target.max_ects,
            warning_min_ects=load_target.min_ects,
            sort_mode=ScenarioSortMode.BALANCED_PRIORITY,
        ),
        ScenarioConfig(
            name="Aggressive Progress",
            kind=RecommendationScenarioKind.AGGRESSIVE,
            target_ects=load_target.max_ects,
            max_ects=load_target.max_ects,
            warning_min_ects=load_target.target_ects,
            sort_mode=ScenarioSortMode.UNLOCK_FIRST,
        ),
    )


def preferred_kind_for(preference: DifficultyPreference) -> RecommendationScenarioKind:
    if preference == DifficultyPreference.EASY:
        return RecommendationScenarioKind.EASY
    if preference == DifficultyPreference.HARD:
        return RecommendationScenarioKind.AGGRESSIVE
    return RecommendationScenarioKind.BALANCED


def sort_scores(
    course_scores: tuple[CourseLoadScore, ...],
    sort_mode: ScenarioSortMode,
) -> tuple[CourseLoadScore, ...]:
    if sort_mode == ScenarioSortMode.LOW_LOAD:
        return tuple(
            sorted(
                course_scores,
                key=lambda score: (
                    score.difficulty_score,
                    score.estimated_ects,
                    -score.priority_score,
                    score.course_code,
                ),
            )
        )
    if sort_mode == ScenarioSortMode.UNLOCK_FIRST:
        return tuple(
            sorted(
                course_scores,
                key=lambda score: (
                    -score.unlock_score,
                    -score.priority_score,
                    -score.difficulty_score,
                    score.course_code,
                ),
            )
        )
    return tuple(
        sorted(
            course_scores,
            key=lambda score: (
                -score.priority_score,
                score.difficulty_score,
                score.course_code,
            ),
        )
    )


def select_course_basket(
    sorted_scores: tuple[CourseLoadScore, ...],
    target_ects: float,
    max_ects: float,
) -> tuple[CourseLoadScore, ...]:
    selected: list[CourseLoadScore] = []
    total_ects = 0.0
    for score in sorted_scores:
        if total_ects >= target_ects:
            break
        if total_ects + score.estimated_ects > max_ects and selected:
            continue
        if total_ects + score.estimated_ects > max_ects and not selected:
            continue
        selected.append(score)
        total_ects += score.estimated_ects
    return tuple(selected)


def to_recommendation(score: CourseLoadScore, config: ScenarioConfig) -> CourseRecommendation:
    base = score.to_recommendation()
    return CourseRecommendation(
        course_code=base.course_code,
        priority_score=base.priority_score,
        rationale=(
            *base.rationale,
            f"included in {config.name} scenario",
        ),
        estimated_ects=base.estimated_ects,
        estimated_credits=base.estimated_credits,
        difficulty_score=base.difficulty_score,
        unlock_count=base.unlock_count,
        status=base.status,
    )


def total_known_credits(scores: tuple[CourseLoadScore, ...]) -> float | None:
    if not scores or any(score.estimated_credits is None for score in scores):
        return None
    return sum(score.estimated_credits or 0.0 for score in scores)


def weighted_average_difficulty(scores: tuple[CourseLoadScore, ...]) -> float | None:
    total_ects = sum(score.estimated_ects for score in scores)
    if total_ects <= 0:
        return None
    return round(
        sum(score.difficulty_score * score.estimated_ects for score in scores) / total_ects,
        4,
    )


def scenario_warnings(
    config: ScenarioConfig,
    selected_scores: tuple[CourseLoadScore, ...],
    total_ects: float,
) -> tuple[PlanningWarning, ...]:
    warnings: list[PlanningWarning] = []
    if not selected_scores:
        warnings.append(
            PlanningWarning(
                code="empty_recommendation_scenario",
                message=f"{config.name} could not include any course within its ECTS cap.",
                severity=PlanningWarningSeverity.WARNING,
            )
        )
    elif total_ects < config.warning_min_ects:
        warnings.append(
            PlanningWarning(
                code="scenario_below_minimum_load",
                message=(
                    f"{config.name} totals {total_ects:g} ECTS, below the "
                    f"{config.warning_min_ects:g} ECTS target for this scenario."
                ),
                severity=PlanningWarningSeverity.INFO,
            )
        )
    return tuple(warnings)


def scenario_rationale(
    config: ScenarioConfig,
    selected_scores: tuple[CourseLoadScore, ...],
    total_ects: float,
    average_difficulty: float | None,
) -> tuple[str, ...]:
    if not selected_scores:
        return (
            f"Targets up to {config.max_ects:g} ECTS.",
            "No eligible course fit within the scenario constraints.",
        )
    difficulty_text = "unknown" if average_difficulty is None else f"{average_difficulty:.2f}"
    return (
        f"Targets about {config.target_ects:g} ECTS with a cap of {config.max_ects:g} ECTS.",
        f"Selected {len(selected_scores)} course(s), total {total_ects:g} ECTS.",
        f"Average estimated difficulty is {difficulty_text}.",
    )
