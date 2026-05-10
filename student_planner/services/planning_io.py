from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from student_planner.domain.planning import (
    CompletedCourseAttempt,
    InProgressCourse,
    PlanningGoal,
    PlanningReport,
    StudentPlanningInput,
)


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
        goal=parse_goal(goal_payload),
        student_id=optional_string(payload.get("student_id")),
        curriculum_version_label=optional_string(payload.get("curriculum_version_label")),
        metadata=payload.get("metadata", {}) if isinstance(payload.get("metadata", {}), Mapping) else {},
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
