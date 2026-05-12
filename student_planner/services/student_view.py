from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from student_planner.domain.planning import (
    CourseEligibilitySummary,
    CourseRecommendation,
    PlanningReport,
    PlanningWarning,
    PlanningWarningSeverity,
    RecommendationScenario,
)


ELECTIVE_CATEGORY_LABELS = {
    "technical_elective": "Technical Elective",
    "restricted_elective": "Restricted Elective",
    "nontechnical_elective": "Non-Technical Elective",
    "free_elective": "Free Elective",
}

COURSE_COLOR_PALETTE = (
    "#f6d65b",
    "#d95ad1",
    "#79cf7b",
    "#5fc6dc",
    "#e45757",
    "#ffad61",
    "#8b7cf6",
    "#54c5a8",
)


def planning_report_to_student_view(
    report: PlanningReport,
) -> dict[str, Any]:
    """Return the stable, student-facing UI contract for a planning report."""

    return {
        "program_abbr": report.program_abbr,
        "target_semester_no": report.goal.target_semester_no,
        "routes": [scenario_to_route(scenario) for scenario in report.scenarios],
        "notices": warning_notices(report.warnings),
        "blocked_courses": blocked_course_summaries(report.blocked_courses),
        "elective_status": elective_status(report.metadata),
        "privacy_note": "Transcript PDF and raw transcript text are not retained by the planner.",
    }


def scenario_to_route(
    scenario: RecommendationScenario,
) -> dict[str, Any]:
    courses = [course_to_view(course) for course in scenario.courses]
    route_id = enum_value(scenario.kind)
    colors = color_map_for_course_codes(tuple(course.course_code for course in scenario.courses))
    return {
        "id": route_id,
        "title": scenario.name,
        "tempo_label": tempo_label(route_id),
        "credit_course_count": sum(1 for course in scenario.courses if counts_as_credit_course(course)),
        "zero_credit_course_count": sum(1 for course in scenario.courses if course.estimated_credits == 0),
        "courses": [attach_course_color(course, colors) for course in courses],
        "notices": warning_notices(scenario.warnings),
    }


def color_map_for_course_codes(course_codes: tuple[str, ...]) -> dict[str, str]:
    colors: dict[str, str] = {}
    for course_code in course_codes:
        if course_code not in colors:
            colors[course_code] = COURSE_COLOR_PALETTE[len(colors) % len(COURSE_COLOR_PALETTE)]
    return colors


def attach_course_color(course: dict[str, Any], colors: Mapping[str, str]) -> dict[str, Any]:
    return {
        **course,
        "color": colors.get(course["code"]),
    }


def course_to_view(course: CourseRecommendation) -> dict[str, Any]:
    flags = []
    if course.estimated_credits == 0:
        flags.append("zero_credit")
    if course.is_repeat_priority:
        flags.append("repeat_priority")
    if course.is_placeholder:
        flags.append("placeholder")
    if course.requires_explicit_course_selection:
        flags.append("needs_course_selection")
    if course.is_easy_priority_elective:
        flags.append("priority_elective")
    if course.is_user_requested:
        flags.append("student_requested")

    return {
        "code": course.course_code,
        "summary": course_summary(course),
        "flags": flags,
        "elective_category": course.elective_category,
        "requires_course_selection": course.requires_explicit_course_selection,
    }


def course_summary(course: CourseRecommendation) -> str:
    if is_summer_practice_course(course.course_code):
        return "Eğer stajını resmi olarak yaptıysan bu dersi almalısın."
    if course.is_repeat_priority:
        return "Onceki deneme nedeniyle bu ders oncelikli gorunuyor."
    if course.estimated_credits == 0:
        return "Kredisiz oldugu icin donem yukunu belirgin artirmadan tamamlanabilir."
    if course.is_placeholder and course.elective_category:
        label = ELECTIVE_CATEGORY_LABELS.get(course.elective_category, "Elective")
        return f"{label} slotu icin ders secimi daha sonra netlesmeli."
    if course.is_user_requested:
        return "Belirttigin elective tercihiyle eslesen bir secenek."
    if course.is_easy_priority_elective:
        return "Rahat rota hedefi icin elective ilerlemesini destekler."
    if course.unlock_count > 0:
        return f"Sonraki donemlerde {course.unlock_count} dersin onunu acabilir."
    return "Mufredatindaki siradaki alinabilir derslerden biri."


def is_summer_practice_course(course_code: str) -> bool:
    parts = course_code.split()
    return len(parts) == 2 and parts[1] in {"300", "400"}


def warning_notices(warnings: tuple[PlanningWarning, ...]) -> list[dict[str, str]]:
    notices: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for warning in warnings:
        if warning.severity == PlanningWarningSeverity.INFO:
            continue
        key = (enum_value(warning.severity), warning.code, warning.message)
        if key in seen:
            continue
        seen.add(key)
        notices.append(
            {
                "level": enum_value(warning.severity),
                "code": warning.code,
                "message": warning.message,
            }
        )
    return notices


def blocked_course_summaries(blocked_courses: tuple[CourseEligibilitySummary, ...]) -> list[dict[str, Any]]:
    return [
        {
            "code": course.course_code,
            "missing_prerequisites": list(course.missing_prerequisite_codes),
            "explanation": course.explanation,
        }
        for course in blocked_courses
    ]


def elective_status(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    remaining = mapping_or_empty(metadata.get("elective_remaining_slots_by_category"))
    completed = mapping_or_empty(metadata.get("elective_completed_counts_by_category"))
    requested = mapping_or_empty(metadata.get("elective_requested_counts_by_category"))
    matched = mapping_or_empty(metadata.get("elective_matched_counts_by_category"))
    categories = sorted(set(remaining) | set(completed) | set(requested) | set(matched))
    return [
        {
            "category": category,
            "label": ELECTIVE_CATEGORY_LABELS.get(category, category),
            "completed": int_or_zero(completed.get(category)),
            "remaining": int_or_zero(remaining.get(category)),
            "requested": int_or_zero(requested.get(category)),
            "planned": int_or_zero(matched.get(category)),
        }
        for category in categories
    ]


def mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def int_or_zero(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def counts_as_credit_course(course: CourseRecommendation) -> bool:
    return course.estimated_credits is None or course.estimated_credits > 0


def tempo_label(kind: str) -> str:
    return {
        "easy": "low_tempo",
        "balanced": "standard_tempo",
        "aggressive": "fast_tempo",
    }.get(kind, "alternative")


def enum_value(value: Any) -> str:
    return getattr(value, "value", str(value))
