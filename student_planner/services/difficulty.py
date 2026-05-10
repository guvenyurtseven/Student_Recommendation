from __future__ import annotations

import re
from dataclasses import dataclass

from student_planner.domain.planning import (
    CourseRecommendation,
    DifficultyPreference,
    PlanningGoal,
)
from student_planner.services.candidate_courses import CandidateCourse, CandidateCourseResult
from student_planner.services.unlock_analysis import CourseUnlockSummary, UnlockAnalysisResult


DEFAULT_COURSE_ECTS = 5.0


@dataclass(frozen=True)
class SemesterLoadTarget:
    difficulty_preference: DifficultyPreference
    min_ects: float
    target_ects: float
    max_ects: float


@dataclass(frozen=True)
class CourseLoadScore:
    course_code: str
    estimated_ects: float
    estimated_credits: float | None
    course_level: int
    is_major_course: bool
    unlock_score: float
    semester_alignment_score: float
    difficulty_score: float
    priority_score: float
    rationale: tuple[str, ...]

    def to_recommendation(self) -> CourseRecommendation:
        return CourseRecommendation(
            course_code=self.course_code,
            priority_score=self.priority_score,
            rationale=self.rationale,
            estimated_ects=self.estimated_ects,
            estimated_credits=self.estimated_credits,
            difficulty_score=self.difficulty_score,
            unlock_count=round(self.unlock_score),
        )


@dataclass(frozen=True)
class CourseScoringResult:
    load_target: SemesterLoadTarget
    course_scores: tuple[CourseLoadScore, ...]

    @property
    def ranked_courses(self) -> tuple[CourseLoadScore, ...]:
        return tuple(
            sorted(
                self.course_scores,
                key=lambda score: (-score.priority_score, score.difficulty_score, score.course_code),
            )
        )

    @property
    def recommendations(self) -> tuple[CourseRecommendation, ...]:
        return tuple(score.to_recommendation() for score in self.ranked_courses)


class CourseScoringService:
    """Score eligible candidate courses for later recommendation basket building."""

    def score_eligible_candidates(
        self,
        candidate_result: CandidateCourseResult,
        unlock_result: UnlockAnalysisResult,
        goal: PlanningGoal,
        program_abbr: str,
    ) -> CourseScoringResult:
        unlock_by_course = unlock_result.by_course_code
        max_unlock_score = max(
            (summary.critical_path_score for summary in unlock_by_course.values()),
            default=0.0,
        )
        load_target = load_target_from_goal(goal)
        scores = tuple(
            self.score_course(
                candidate=candidate,
                unlock_summary=unlock_by_course.get(candidate.course_code),
                max_unlock_score=max_unlock_score,
                goal=goal,
                program_abbr=program_abbr,
            )
            for candidate in candidate_result.eligible_courses
        )
        return CourseScoringResult(load_target=load_target, course_scores=scores)

    def score_course(
        self,
        candidate: CandidateCourse,
        unlock_summary: CourseUnlockSummary | None,
        max_unlock_score: float,
        goal: PlanningGoal,
        program_abbr: str,
    ) -> CourseLoadScore:
        estimated_ects = candidate.estimated_ects if candidate.estimated_ects is not None else DEFAULT_COURSE_ECTS
        course_level = course_level_from_code(candidate.course_code)
        is_major_course = subject_code(candidate.course_code) == program_abbr.upper()
        unlock_component = normalized_unlock_score(unlock_summary, max_unlock_score)
        semester_component = semester_alignment_score(candidate.recommended_term, goal.target_semester_no)
        difficulty = course_difficulty_score(
            estimated_ects=estimated_ects,
            course_level=course_level,
            is_major_course=is_major_course,
        )
        priority = priority_score(
            difficulty_preference=goal.difficulty_preference,
            unlock_component=unlock_component,
            semester_component=semester_component,
            difficulty_score=difficulty,
        )
        return CourseLoadScore(
            course_code=candidate.course_code,
            estimated_ects=estimated_ects,
            estimated_credits=candidate.estimated_credits,
            course_level=course_level,
            is_major_course=is_major_course,
            unlock_score=unlock_summary.critical_path_score if unlock_summary else 0.0,
            semester_alignment_score=semester_component,
            difficulty_score=difficulty,
            priority_score=priority,
            rationale=score_rationale(
                candidate=candidate,
                unlock_summary=unlock_summary,
                used_default_ects=candidate.estimated_ects is None,
                difficulty=difficulty,
                semester_component=semester_component,
            ),
        )


def load_target_from_goal(goal: PlanningGoal) -> SemesterLoadTarget:
    defaults = {
        DifficultyPreference.EASY: (18.0, 21.0, 24.0),
        DifficultyPreference.BALANCED: (26.0, 30.0, 34.0),
        DifficultyPreference.HARD: (32.0, 36.0, 42.0),
    }
    default_min, default_target, default_max = defaults[goal.difficulty_preference]
    target = goal.target_ects if goal.target_ects is not None else default_target
    minimum = goal.min_ects if goal.min_ects is not None else default_min
    maximum = goal.max_ects if goal.max_ects is not None else default_max
    return SemesterLoadTarget(
        difficulty_preference=goal.difficulty_preference,
        min_ects=minimum,
        target_ects=target,
        max_ects=maximum,
    )


def normalized_unlock_score(unlock_summary: CourseUnlockSummary | None, max_unlock_score: float) -> float:
    if unlock_summary is None or max_unlock_score <= 0:
        return 0.0
    return clamp(unlock_summary.critical_path_score / max_unlock_score)


def course_difficulty_score(estimated_ects: float, course_level: int, is_major_course: bool) -> float:
    ects_component = clamp(estimated_ects / 10.0)
    level_component = clamp(course_level / 4.0)
    major_component = 0.1 if is_major_course else 0.0
    return clamp((0.55 * ects_component) + (0.35 * level_component) + major_component)


def priority_score(
    difficulty_preference: DifficultyPreference,
    unlock_component: float,
    semester_component: float,
    difficulty_score: float,
) -> float:
    load_fit = load_fit_component(difficulty_preference, difficulty_score)
    weights = {
        DifficultyPreference.EASY: (0.30, 0.30, 0.40),
        DifficultyPreference.BALANCED: (0.45, 0.25, 0.30),
        DifficultyPreference.HARD: (0.60, 0.20, 0.20),
    }
    unlock_weight, semester_weight, load_weight = weights[difficulty_preference]
    return round(
        100.0
        * (
            (unlock_weight * unlock_component)
            + (semester_weight * semester_component)
            + (load_weight * load_fit)
        ),
        4,
    )


def load_fit_component(difficulty_preference: DifficultyPreference, difficulty_score: float) -> float:
    if difficulty_preference == DifficultyPreference.EASY:
        return 1.0 - difficulty_score
    if difficulty_preference == DifficultyPreference.HARD:
        return difficulty_score
    return 1.0 - min(1.0, abs(difficulty_score - 0.55) / 0.55)


def semester_alignment_score(recommended_term: str | None, target_semester_no: str) -> float:
    recommended = normalize_term_label(recommended_term)
    target = target_term_label(target_semester_no)
    if recommended is None or target is None:
        return 0.65
    if recommended == target:
        return 1.0
    if target == "summer":
        return 0.25
    return 0.35


def normalize_term_label(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "fall", "autumn", "guz", "güz"}:
        return "fall"
    if normalized in {"2", "spring", "bahar"}:
        return "spring"
    if normalized in {"3", "summer", "yaz"}:
        return "summer"
    return None


def target_term_label(semester_no: str) -> str | None:
    if not semester_no:
        return None
    last_digit = semester_no.strip()[-1]
    return {"1": "fall", "2": "spring", "3": "summer"}.get(last_digit)


def course_level_from_code(course_code: str) -> int:
    match = re.search(r"\s+(\d+)", course_code)
    if not match:
        return 1
    course_number = int(match.group(1))
    if course_number >= 1000:
        folded = course_number % 1000
        course_number = folded if folded >= 100 else course_number
    return min(4, max(1, course_number // 100))


def subject_code(course_code: str) -> str:
    return course_code.split(" ", 1)[0].upper()


def score_rationale(
    candidate: CandidateCourse,
    unlock_summary: CourseUnlockSummary | None,
    used_default_ects: bool,
    difficulty: float,
    semester_component: float,
) -> tuple[str, ...]:
    rationale = [
        f"estimated difficulty {difficulty:.2f}",
        f"semester alignment {semester_component:.2f}",
    ]
    if unlock_summary:
        rationale.append(
            "unlocks "
            f"{unlock_summary.curriculum_relevant_unlock_count} curriculum-relevant "
            f"course(s), {unlock_summary.direct_unlock_count} direct course(s)"
        )
    else:
        rationale.append("no downstream prerequisite unlock signal found")
    if candidate.estimated_ects is not None:
        rationale.append(f"uses curriculum ECTS estimate {candidate.estimated_ects:g}")
    if used_default_ects:
        rationale.append(f"ECTS missing; used default {DEFAULT_COURSE_ECTS:g}")
    return tuple(rationale)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
