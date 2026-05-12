from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from student_planner.domain.planning import (
    CourseEligibilitySummary,
    CourseRecommendation,
    PlanningReport,
    PlanningWarning,
    RecommendationScenario,
    RequirementProgress,
    RequirementProgressStatus,
)


def planning_report_to_markdown(report: PlanningReport) -> str:
    lines: list[str] = [
        f"# {report.program_abbr} Next-Semester Planning Report",
        "",
        "## Summary",
        "",
        f"- Target semester: {report.goal.target_semester_no}",
        f"- Difficulty preference: {enum_value(report.goal.difficulty_preference)}",
        f"- Generated at: {report.generated_at_utc}",
        f"- Preferred scenario: {report.metadata.get('preferred_scenario_kind', 'unknown')}",
        f"- Eligible courses: {len(report.eligible_courses)}",
        f"- Blocked courses: {len(report.blocked_courses)}",
        f"- Recommendation scenarios: {len(report.scenarios)}",
    ]
    lines.extend(registration_policy_summary_lines(report.metadata))
    lines.extend(offering_summary_lines(report.metadata))
    lines.extend(elective_summary_lines(report.metadata))
    lines.extend(scenario_lines(report.scenarios))
    lines.extend(warning_lines(report.warnings))
    lines.extend(blocked_course_lines(report.blocked_courses))
    lines.extend(curriculum_progress_lines(report.curriculum_progress))
    return "\n".join(lines).rstrip() + "\n"


def registration_policy_summary_lines(metadata: Mapping[str, Any]) -> list[str]:
    if "registration_policy_source_url" not in metadata:
        return []
    standing = metadata.get("registration_policy_academic_standing") or "unknown"
    cgpa = metadata.get("registration_policy_cgpa")
    max_course_count = metadata.get("registration_policy_max_course_count")
    normal_load = metadata.get("registration_policy_normal_course_load")
    return [
        f"- Academic standing: {standing}",
        f"- CGPA used for registration policy: {number_text(cgpa)}",
        f"- Normal course load: {number_text(normal_load)} course(s)",
        f"- Registration course-count cap: {number_text(max_course_count)} course(s)",
    ]


def offering_summary_lines(metadata: Mapping[str, Any]) -> list[str]:
    if "target_semester_offerings_count" not in metadata:
        return []
    return [
        f"- Loaded target-semester offerings: {metadata.get('target_semester_offerings_count', 0)}",
        f"- Known offered candidates: {metadata.get('offered_candidate_count', 0)}",
        f"- Known not-offered candidates: {metadata.get('not_offered_candidate_count', 0)}",
        f"- Unknown offering candidates: {metadata.get('unknown_offering_candidate_count', 0)}",
    ]


def elective_summary_lines(metadata: Mapping[str, Any]) -> list[str]:
    remaining = metadata.get("elective_remaining_slots_by_category")
    requested = metadata.get("elective_requested_counts_by_category")
    matched = metadata.get("elective_matched_counts_by_category")
    unplanned = metadata.get("elective_unplanned_counts_by_category")
    extra = metadata.get("elective_extra_counts_by_category")
    if not all(isinstance(item, Mapping) for item in (remaining, requested, matched, unplanned, extra)):
        return []

    categories = sorted(
        set(remaining)
        | set(requested)
        | set(matched)
        | set(unplanned)
        | set(extra)
    )
    lines = [
        "",
        "## Elective Fit",
        "",
        markdown_table(
            ("Category", "Remaining", "Requested", "Matched", "Unplanned Later", "Extra"),
            (
                (
                    category,
                    number_text(remaining.get(category, 0)),
                    number_text(requested.get(category, 0)),
                    number_text(matched.get(category, 0)),
                    number_text(unplanned.get(category, 0)),
                    number_text(extra.get(category, 0)),
                )
                for category in categories
            ),
        ),
    ]
    return lines


def scenario_lines(scenarios: tuple[RecommendationScenario, ...]) -> list[str]:
    lines = [
        "",
        "## Recommendation Scenarios",
        "",
    ]
    if not scenarios:
        lines.append("No recommendation scenario could be built.")
        return lines

    lines.append(
        markdown_table(
            ("Scenario", "Kind", "ECTS", "Difficulty", "Courses"),
            (
                (
                    scenario.name,
                    enum_value(scenario.kind),
                    number_text(scenario.total_ects),
                    number_text(scenario.difficulty_score),
                    ", ".join(scenario.course_codes),
                )
                for scenario in scenarios
            ),
        )
    )
    for scenario in scenarios:
        lines.extend(single_scenario_lines(scenario))
    return lines


def single_scenario_lines(scenario: RecommendationScenario) -> list[str]:
    lines = [
        "",
        f"### {scenario.name}",
        "",
    ]
    if scenario.rationale:
        lines.extend(f"- {item}" for item in scenario.rationale)
        lines.append("")
    if not scenario.courses:
        lines.append("No courses selected.")
        return lines
    lines.append(
        markdown_table(
            ("Course", "ECTS", "Difficulty", "Requested", "Course Selection", "Policy"),
            (course_row(course) for course in scenario.courses),
        )
    )
    return lines


def course_row(course: CourseRecommendation) -> tuple[str, str, str, str, str, str]:
    if course.requires_explicit_course_selection:
        course_selection = "needs concrete course"
    elif course.is_placeholder:
        course_selection = "placeholder"
    else:
        course_selection = "concrete"
    policy_flags = []
    if course.is_new_course:
        policy_flags.append("new")
    if course.is_repeat_priority:
        policy_flags.append("repeat-priority")
    return (
        course.course_code,
        number_text(course.estimated_ects),
        number_text(course.difficulty_score),
        "yes" if course.is_user_requested else "no",
        course_selection,
        ", ".join(policy_flags) or "-",
    )


def warning_lines(warnings: tuple[PlanningWarning, ...]) -> list[str]:
    lines = [
        "",
        "## Warnings",
        "",
    ]
    if not warnings:
        lines.append("No warnings.")
        return lines
    lines.append(
        markdown_table(
            ("Count", "Severity", "Code", "Message"),
            grouped_warning_rows(warnings),
        )
    )
    return lines


def grouped_warning_rows(warnings: tuple[PlanningWarning, ...]) -> tuple[tuple[str, str, str, str], ...]:
    counts: dict[tuple[str, str, str], int] = {}
    for warning in warnings:
        key = (enum_value(warning.severity), warning.code, warning.message)
        counts[key] = counts.get(key, 0) + 1
    return tuple(
        (str(count), severity, code, message)
        for (severity, code, message), count in sorted(
            counts.items(),
            key=lambda item: (item[0][0], item[0][1], item[0][2]),
        )
    )


def blocked_course_lines(blocked_courses: tuple[CourseEligibilitySummary, ...]) -> list[str]:
    lines = [
        "",
        "## Blocked Courses",
        "",
    ]
    if not blocked_courses:
        lines.append("No blocked concrete course candidates.")
        return lines
    lines.append(
        markdown_table(
            ("Course", "Missing Prerequisites", "Explanation"),
            (
                (
                    course.course_code,
                    ", ".join(course.missing_prerequisite_codes) or "-",
                    course.explanation or "-",
                )
                for course in blocked_courses
            ),
        )
    )
    return lines


def curriculum_progress_lines(requirements: tuple[RequirementProgress, ...]) -> list[str]:
    counts: dict[str, int] = {
        RequirementProgressStatus.SATISFIED.value: 0,
        RequirementProgressStatus.PARTIALLY_SATISFIED.value: 0,
        RequirementProgressStatus.UNSATISFIED.value: 0,
        RequirementProgressStatus.NEEDS_REVIEW.value: 0,
    }
    for requirement in requirements:
        counts[enum_value(requirement.status)] = counts.get(enum_value(requirement.status), 0) + 1

    return [
        "",
        "## Curriculum Progress Snapshot",
        "",
        markdown_table(
            ("Status", "Count"),
            ((status, str(count)) for status, count in counts.items()),
        ),
    ]


def markdown_table(headers: tuple[str, ...], rows: Iterable[Iterable[Any]]) -> str:
    rendered_rows = [tuple(markdown_cell(item) for item in row) for row in rows]
    lines = [
        "| " + " | ".join(markdown_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rendered_rows)
    return "\n".join(lines)


def markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def enum_value(value: Any) -> str:
    return getattr(value, "value", str(value))


def number_text(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, int | float):
        return f"{value:g}"
    return str(value)
