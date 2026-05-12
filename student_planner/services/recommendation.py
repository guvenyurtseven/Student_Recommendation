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
    target_credit_course_count: int
    max_credit_course_count: int
    sort_mode: ScenarioSortMode
    include_easy_priority_elective: bool = False
    excluded_elective_categories: frozenset[str] = frozenset()


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

        easy_config, balanced_config, aggressive_config = scenario_configs(scoring_result.load_target)
        easy_scenario = self.build_scenario(scoring_result.course_scores, easy_config)
        if scenario_has_nontech_or_free_elective(easy_scenario):
            balanced_config = ScenarioConfig(
                name=balanced_config.name,
                kind=balanced_config.kind,
                target_credit_course_count=balanced_config.target_credit_course_count,
                max_credit_course_count=balanced_config.max_credit_course_count,
                sort_mode=balanced_config.sort_mode,
                include_easy_priority_elective=balanced_config.include_easy_priority_elective,
                excluded_elective_categories=frozenset({"nontechnical_elective", "free_elective"}),
            )
        scenarios = (
            easy_scenario,
            self.build_scenario(scoring_result.course_scores, balanced_config),
            self.build_scenario(scoring_result.course_scores, aggressive_config),
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
        selected_scores = select_course_basket(sorted_scores, config)
        total_ects = sum(score.estimated_ects for score in selected_scores)
        total_credits = total_known_credits(selected_scores)
        average_difficulty = weighted_average_difficulty(selected_scores)
        warnings = scenario_warnings(config, sorted_scores, selected_scores)
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
            name="Temel Rota",
            kind=RecommendationScenarioKind.EASY,
            target_credit_course_count=5,
            max_credit_course_count=5,
            sort_mode=ScenarioSortMode.LOW_LOAD,
            include_easy_priority_elective=True,
        ),
        ScenarioConfig(
            name="Ana Rota",
            kind=RecommendationScenarioKind.BALANCED,
            target_credit_course_count=5,
            max_credit_course_count=5,
            sort_mode=ScenarioSortMode.BALANCED_PRIORITY,
        ),
        ScenarioConfig(
            name="Hizli Rota",
            kind=RecommendationScenarioKind.AGGRESSIVE,
            target_credit_course_count=6,
            max_credit_course_count=6,
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
    config: ScenarioConfig,
) -> tuple[CourseLoadScore, ...]:
    selected: list[CourseLoadScore] = []
    credit_course_count = 0
    for score in mandatory_first(sorted_scores, config):
        if score in selected:
            continue
        mandatory = must_include_score(score, sorted_scores, config)
        if should_exclude_for_scenario(score, config, mandatory):
            continue
        counts_for_load = counts_as_credit_course(score)
        if not mandatory and credit_course_count >= config.target_credit_course_count:
            continue
        if not mandatory and counts_for_load and credit_course_count >= config.max_credit_course_count:
            continue
        selected.append(score)
        if counts_for_load:
            credit_course_count += 1
    return tuple(selected)


def requested_first(sorted_scores: tuple[CourseLoadScore, ...]) -> tuple[CourseLoadScore, ...]:
    requested = tuple(score for score in sorted_scores if score.is_user_requested)
    regular = tuple(score for score in sorted_scores if not score.is_user_requested)
    return requested + regular


def mandatory_first(
    sorted_scores: tuple[CourseLoadScore, ...],
    config: ScenarioConfig,
) -> tuple[CourseLoadScore, ...]:
    zero_credit = tuple(score for score in sorted_scores if is_zero_credit_score(score))
    zero_credit_codes = {score.course_code for score in zero_credit}
    easy_priority = tuple(
        score
        for score in sorted_scores
        if config.include_easy_priority_elective and score.is_easy_priority_elective and score.course_code not in zero_credit_codes
    )
    easy_priority_codes = {score.course_code for score in easy_priority}
    repeat_priority = tuple(score for score in sorted_scores if score.is_repeat_priority)
    repeat_priority = tuple(score for score in repeat_priority if score.course_code not in zero_credit_codes | easy_priority_codes)
    repeat_codes = {score.course_code for score in repeat_priority}
    requested = tuple(
        score
        for score in sorted_scores
        if score.is_user_requested and score.course_code not in zero_credit_codes | easy_priority_codes | repeat_codes
    )
    requested_codes = {score.course_code for score in requested}
    critical = tuple(
        score
        for score in critical_unlock_scores(sorted_scores)
        if score.course_code not in zero_credit_codes | easy_priority_codes | repeat_codes | requested_codes
    )
    mandatory_codes = (
        zero_credit_codes
        | easy_priority_codes
        | repeat_codes
        | requested_codes
        | {score.course_code for score in critical}
    )
    regular = tuple(score for score in sorted_scores if score.course_code not in mandatory_codes)
    return zero_credit + easy_priority + repeat_priority + requested + critical + regular


def must_include_score(
    score: CourseLoadScore,
    sorted_scores: tuple[CourseLoadScore, ...],
    config: ScenarioConfig,
) -> bool:
    return (
        is_zero_credit_score(score)
        or score.is_repeat_priority
        or score.is_user_requested
        or (config.include_easy_priority_elective and score.is_easy_priority_elective)
        or is_critical_unlock_score(score, sorted_scores)
    )


def should_exclude_for_scenario(score: CourseLoadScore, config: ScenarioConfig, mandatory: bool) -> bool:
    if not score.elective_category or score.elective_category not in config.excluded_elective_categories:
        return False
    return not (is_zero_credit_score(score) or score.is_repeat_priority)


def counts_as_credit_course(score: CourseLoadScore) -> bool:
    return score.estimated_credits is None or score.estimated_credits > 0


def is_zero_credit_score(score: CourseLoadScore) -> bool:
    return score.estimated_credits == 0


def critical_unlock_scores(sorted_scores: tuple[CourseLoadScore, ...]) -> tuple[CourseLoadScore, ...]:
    max_unlock_score = max((score.unlock_score for score in sorted_scores), default=0.0)
    if max_unlock_score <= 0:
        return ()
    threshold = max_unlock_score * 0.75
    return tuple(
        sorted(
            (
                score
                for score in sorted_scores
                if score.unlock_score > 0 and score.unlock_score >= threshold
            ),
            key=lambda score: (-score.unlock_score, -score.priority_score, score.course_code),
        )
    )


def is_critical_unlock_score(score: CourseLoadScore, sorted_scores: tuple[CourseLoadScore, ...]) -> bool:
    return score.course_code in {item.course_code for item in critical_unlock_scores(sorted_scores)}


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
        is_placeholder=base.is_placeholder,
        is_user_requested=base.is_user_requested,
        requires_explicit_course_selection=base.requires_explicit_course_selection,
        is_new_course=base.is_new_course,
        is_repeat_priority=base.is_repeat_priority,
        elective_category=base.elective_category,
        is_easy_priority_elective=base.is_easy_priority_elective,
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
    sorted_scores: tuple[CourseLoadScore, ...],
    selected_scores: tuple[CourseLoadScore, ...],
) -> tuple[PlanningWarning, ...]:
    warnings: list[PlanningWarning] = []
    credit_count = credit_course_count(selected_scores)
    if not selected_scores:
        warnings.append(
            PlanningWarning(
                code="empty_recommendation_scenario",
                message=f"{config.name} could not include any eligible course.",
                severity=PlanningWarningSeverity.WARNING,
            )
        )
    elif credit_count < config.target_credit_course_count:
        warnings.append(
            PlanningWarning(
                code="scenario_below_minimum_load",
                message=(
                    f"{config.name} contains {credit_count} credit course(s), below the "
                    f"{config.target_credit_course_count}-course target for this route."
                ),
                severity=PlanningWarningSeverity.INFO,
            )
        )
    elif credit_count > config.max_credit_course_count:
        warnings.append(
            PlanningWarning(
                code="scenario_above_route_credit_course_count",
                message=(
                    f"{config.name} contains {credit_count} credit course(s) because mandatory "
                    f"items exceeded the route cap of {config.max_credit_course_count}."
                ),
                severity=PlanningWarningSeverity.INFO,
            )
        )
    missed_requested = tuple(
        score.course_code
        for score in sorted_scores
        if score.is_user_requested and score.course_code not in {item.course_code for item in selected_scores}
    )
    if missed_requested:
        warnings.append(
            PlanningWarning(
                code="user_requested_course_excluded_by_load_cap",
                message=(
                    f"{len(missed_requested)} user-requested course/elective item(s) could not fit within "
                    f"the {config.name} course-count target."
                ),
                severity=PlanningWarningSeverity.WARNING,
            )
        )
    missed_repeat_priority = tuple(
        score.course_code
        for score in sorted_scores
        if score.is_repeat_priority and score.course_code not in {item.course_code for item in selected_scores}
    )
    if missed_repeat_priority:
        warnings.append(
            PlanningWarning(
                code="repeat_priority_course_excluded_by_load_cap",
                message=(
                    f"{len(missed_repeat_priority)} repeat-priority course(s) could not fit within "
                    f"the {config.name} course-count target."
                ),
                severity=PlanningWarningSeverity.WARNING,
            )
        )
    missed_critical = tuple(
        score.course_code
        for score in critical_unlock_scores(sorted_scores)
        if score.course_code not in {item.course_code for item in selected_scores}
    )
    if missed_critical:
        warnings.append(
            PlanningWarning(
                code="critical_unlock_course_excluded_by_load_cap",
                message=(
                    f"{len(missed_critical)} critical unlock course(s) could not fit within "
                    f"the {config.name} course-count target."
                ),
                severity=PlanningWarningSeverity.WARNING,
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
            f"Targets {config.target_credit_course_count} credit-bearing course(s).",
            "No eligible course fit within the scenario constraints.",
        )
    difficulty_text = "unknown" if average_difficulty is None else f"{average_difficulty:.2f}"
    zero_credit_count = sum(1 for score in selected_scores if is_zero_credit_score(score))
    credit_count = credit_course_count(selected_scores)
    return (
        f"Targets {config.target_credit_course_count} credit-bearing course(s).",
        f"Selected {credit_count} credit-bearing course(s) and {zero_credit_count} zero-credit item(s).",
        f"Average estimated difficulty is {difficulty_text}.",
    )


def credit_course_count(scores: tuple[CourseLoadScore, ...]) -> int:
    return sum(1 for score in scores if counts_as_credit_course(score))


def scenario_has_nontech_or_free_elective(scenario: RecommendationScenario) -> bool:
    return any(
        course.elective_category in {"nontechnical_elective", "free_elective"}
        for course in scenario.courses
    )
