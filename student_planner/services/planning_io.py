from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from student_planner.domain.electives import ElectiveIntent
from student_planner.domain.planning import (
    CompletedCourseAttempt,
    InProgressCourse,
    PlanningGoal,
    PlanningReport,
    StudentPlanningInput,
)
from student_planner.services.llm_report_package import build_llm_report_package
from student_planner.services.planning_report_markdown import planning_report_to_markdown


def load_student_planning_input(path: str | Path) -> StudentPlanningInput:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Planning input JSON must be an object.")
    return student_planning_input_from_dict(payload)


def student_planning_input_from_dict(payload: Mapping[str, Any]) -> StudentPlanningInput:
    program_abbr = payload.get("program_abbr") or payload.get("program")
    if not program_abbr:
        raise ValueError("Planning input must include `program_abbr` or `program`.")

    goal_payload = payload.get("goal")
    if not isinstance(goal_payload, Mapping):
        raise ValueError("Planning input must include a `goal` object.")

    completed_payload = payload.get("completed_courses", ())
    if not isinstance(completed_payload, list | tuple):
        raise ValueError("`completed_courses` must be a list.")

    in_progress_payload = payload.get("in_progress_courses", ())
    if not isinstance(in_progress_payload, list | tuple):
        raise ValueError("`in_progress_courses` must be a list when provided.")

    return StudentPlanningInput(
        program_abbr=str(program_abbr),
        completed_courses=tuple(parse_completed_course(item) for item in completed_payload),
        in_progress_courses=tuple(parse_in_progress_course(item) for item in in_progress_payload),
        elective_intents=parse_elective_intents(payload),
        goal=parse_goal(goal_payload),
        student_id=optional_string(payload.get("student_id")),
        curriculum_version_label=optional_string(payload.get("curriculum_version_label")),
        metadata=payload.get("metadata", {}) if isinstance(payload.get("metadata", {}), Mapping) else {},
    )


def parse_elective_intents(payload: Mapping[str, Any]) -> tuple[ElectiveIntent, ...]:
    if "elective_intents" in payload:
        raw_intents = payload["elective_intents"]
        if not isinstance(raw_intents, list | tuple):
            raise ValueError("`elective_intents` must be a list when provided.")
        intents = tuple(parse_elective_intent(item) for item in raw_intents)
        return tuple(intent for intent in intents if intent.wants_to_take)

    raw_preferences = payload.get("elective_preferences") or payload.get("electives")
    if raw_preferences is None:
        return ()
    if isinstance(raw_preferences, list | tuple):
        intents = tuple(parse_elective_intent(item) for item in raw_preferences)
        return tuple(intent for intent in intents if intent.wants_to_take)
    if not isinstance(raw_preferences, Mapping):
        raise ValueError("`elective_preferences` must be an object or list when provided.")

    intents: list[ElectiveIntent] = []
    for category, value in raw_preferences.items():
        intent = parse_elective_preference_item(str(category), value)
        if intent.wants_to_take:
            intents.append(intent)
    return tuple(intents)


def parse_elective_preference_item(category: str, value: Any) -> ElectiveIntent:
    if isinstance(value, bool | str | int):
        return ElectiveIntent(category=category, wants_to_take=boolish(value))
    if not isinstance(value, Mapping):
        raise ValueError("Elective preference values must be booleans or objects.")
    return parse_elective_intent(value, category_hint=category)


def parse_elective_intent(payload: Mapping[str, Any] | str, category_hint: str | None = None) -> ElectiveIntent:
    if isinstance(payload, str):
        return ElectiveIntent(category=payload)
    if not isinstance(payload, Mapping):
        raise ValueError("Elective intent items must be objects or category strings.")
    category = payload.get("category") or category_hint
    if not category:
        raise ValueError("Elective intent items must include `category`.")
    wants_to_take = boolish(payload.get("wants_to_take", payload.get("selected", True)))
    return ElectiveIntent(
        category=str(category),
        wants_to_take=wants_to_take,
        course_code=optional_string(payload.get("course_code") or payload.get("course")),
        requested_count=optional_int(payload.get("requested_count") or payload.get("count")) or 1,
        notes=optional_string(payload.get("notes")) or "",
    )


def parse_completed_course(payload: Mapping[str, Any] | str) -> CompletedCourseAttempt:
    if isinstance(payload, str):
        course_code, grade = parse_compact_completed_course(payload)
        return CompletedCourseAttempt(course_code=course_code, grade=grade)
    if not isinstance(payload, Mapping):
        raise ValueError("Completed course items must be objects or `COURSE:GRADE` strings.")
    return CompletedCourseAttempt(
        course_code=required_string(payload, "course_code"),
        grade=required_string(payload, "grade"),
        completed_semester_no=optional_string(payload.get("completed_semester_no")),
        attempt_order=optional_int(payload.get("attempt_order")),
        source=optional_string(payload.get("source")) or "manual",
        ects=optional_float(payload.get("ects")),
        credits=optional_float(payload.get("credits")),
    )


def parse_in_progress_course(payload: Mapping[str, Any] | str) -> InProgressCourse:
    if isinstance(payload, str):
        if ":" not in payload:
            raise ValueError("Compact in-progress course strings must use `COURSE:SEMESTER` format.")
        course_code, semester_no = payload.split(":", 1)
        return InProgressCourse(course_code=course_code.strip(), semester_no=semester_no.strip())
    if not isinstance(payload, Mapping):
        raise ValueError("In-progress course items must be objects or course-code strings.")
    return InProgressCourse(
        course_code=required_string(payload, "course_code"),
        semester_no=required_string(payload, "semester_no"),
        source=optional_string(payload.get("source")) or "manual",
    )


def parse_goal(payload: Mapping[str, Any]) -> PlanningGoal:
    target_semester_no = payload.get("target_semester_no") or payload.get("target_semester")
    if not target_semester_no:
        raise ValueError("Goal must include `target_semester_no` or `target_semester`.")
    return PlanningGoal(
        target_semester_no=str(target_semester_no),
        difficulty_preference=str(payload.get("difficulty_preference", "balanced")),
        target_ects=optional_float(payload.get("target_ects")),
        min_ects=optional_float(payload.get("min_ects")),
        max_ects=optional_float(payload.get("max_ects")),
        target_term_gpa=optional_float(payload.get("target_term_gpa")),
        target_cumulative_gpa=optional_float(payload.get("target_cumulative_gpa")),
        notes=optional_string(payload.get("notes")) or "",
    )


def planning_report_to_dict(report: PlanningReport) -> dict[str, Any]:
    payload = to_plain(report)
    if not isinstance(payload, dict):
        raise TypeError("Planning report serialization did not produce an object.")
    return payload


def student_planning_input_to_dict(planning_input: StudentPlanningInput) -> dict[str, Any]:
    payload = to_plain(planning_input)
    if not isinstance(payload, dict):
        raise TypeError("Student planning input serialization did not produce an object.")
    return payload


def planning_report_to_text(report: PlanningReport, output_format: str = "json", compact: bool = False) -> str:
    normalized_format = output_format.strip().lower()
    if normalized_format == "json":
        return json.dumps(
            planning_report_to_dict(report),
            ensure_ascii=False,
            indent=None if compact else 2,
            sort_keys=False,
        )
    if normalized_format in {"markdown", "md"}:
        return planning_report_to_markdown(report)
    if normalized_format in {"llm-package", "llm_package"}:
        return json.dumps(
            build_llm_report_package(report).to_dict(),
            ensure_ascii=False,
            indent=None if compact else 2,
            sort_keys=False,
        )
    raise ValueError(f"Unsupported planning report format: {output_format!r}")


def to_plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_plain(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping) or isinstance(value, MappingProxyType):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [to_plain(item) for item in value]
    return value


def parse_compact_completed_course(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise ValueError("Compact completed course strings must use `COURSE:GRADE` format.")
    course_code, grade = value.split(":", 1)
    return course_code.strip(), grade.strip()


def required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing required field `{key}`.")
    return str(value)


def optional_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
    return bool(value)
