from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from student_planner.domain.planning import PlanningGoal, StudentPlanningInput
from student_planner.repositories.sqlite import SQLiteStudentPlannerRepository
from student_planner.services.operation_semester import load_operation_semester
from student_planner.services.planning_io import (
    parse_elective_intents,
    planning_report_to_dict,
    planning_report_to_text,
    student_planning_input_from_dict,
)
from student_planner.services.planning_pipeline import SemesterPlanningPipeline
from student_planner.services.student_view import planning_report_to_student_view
from student_planner.services.transcript_ingestion import (
    TranscriptTextParser,
    extract_text_from_pdf_bytes,
)

MAX_TRANSCRIPT_BYTES = 6 * 1024 * 1024


def recommendation_from_json_payload(payload: Mapping[str, Any], db_path: str | Path) -> dict[str, Any]:
    planning_input = student_planning_input_from_dict(payload)
    return recommendation_response(planning_input, db_path)


def recommendation_from_transcript_payload(payload: Mapping[str, Any], db_path: str | Path) -> dict[str, Any]:
    goal = goal_from_payload(payload)
    pdf_bytes = decode_pdf_payload(required_text(payload, "file_base64"))
    transcript_text = extract_text_from_pdf_bytes(pdf_bytes)
    parse_result = TranscriptTextParser().parse(transcript_text)
    program_abbr = optional_text(payload.get("program_abbr") or payload.get("program"))
    if program_abbr is None:
        program_abbr = optional_text(parse_result.metadata.get("detected_program_abbr"))
    if program_abbr is None:
        raise ValueError("Program could not be detected from transcript PDF.")
    planning_input = StudentPlanningInput(
        program_abbr=program_abbr,
        completed_courses=parse_result.completed_courses,
        in_progress_courses=parse_result.in_progress_courses,
        elective_intents=parse_elective_intents(payload),
        goal=goal,
        metadata={
            "input_source": "transcript_pdf",
            "transcript_parse": dict(parse_result.metadata),
        },
    )
    response = recommendation_response(planning_input, db_path)
    response["transcript_parse"] = {
        "metadata": dict(parse_result.metadata),
        "warnings": [
            {
                "code": warning.code,
                "message": warning.message,
                "course_code": warning.course_code,
            }
            for warning in parse_result.warnings
        ],
    }
    return response


def recommendation_response(planning_input: StudentPlanningInput, db_path: str | Path) -> dict[str, Any]:
    repository = SQLiteStudentPlannerRepository(db_path)
    report = SemesterPlanningPipeline(repository).build_report(planning_input)
    operation_semester = load_operation_semester()
    return {
        "ok": True,
        "program_abbr": report.program_abbr,
        "target_semester_no": report.goal.target_semester_no,
        "operation_semester": {
            "active_semester_no": operation_semester.active_semester_no,
            "active_semester_label": operation_semester.active_semester_label,
        },
        "report_markdown": planning_report_to_text(report, output_format="markdown"),
        "report": planning_report_to_dict(report),
        "student_view": planning_report_to_student_view(report),
        "summary": {
            "scenario_count": len(report.scenarios),
            "eligible_course_count": len(report.eligible_courses),
            "blocked_course_count": len(report.blocked_courses),
            "warning_count": len(report.warnings),
            "preferred_scenario_kind": report.metadata.get("preferred_scenario_kind"),
        },
    }


def goal_from_payload(payload: Mapping[str, Any]) -> PlanningGoal:
    raw_goal = payload.get("goal")
    if isinstance(raw_goal, Mapping):
        target_semester_no = raw_goal.get("target_semester_no") or raw_goal.get("target_semester")
        difficulty_preference = raw_goal.get("difficulty_preference", payload.get("difficulty_preference", "balanced"))
        source = raw_goal
    else:
        target_semester_no = payload.get("target_semester_no") or payload.get("target_semester")
        difficulty_preference = payload.get("difficulty_preference", "balanced")
        source = payload

    if not target_semester_no:
        target_semester_no = load_operation_semester().active_semester_no

    return PlanningGoal(
        target_semester_no=str(target_semester_no),
        difficulty_preference=str(difficulty_preference),
        target_ects=optional_float(source.get("target_ects")),
        min_ects=optional_float(source.get("min_ects")),
        max_ects=optional_float(source.get("max_ects")),
        target_term_gpa=optional_float(source.get("target_term_gpa")),
        target_cumulative_gpa=optional_float(source.get("target_cumulative_gpa")),
        notes=str(source.get("notes", "") or ""),
    )


def decode_pdf_payload(value: str) -> bytes:
    encoded = value.strip()
    if "," in encoded and encoded.split(",", 1)[0].startswith("data:"):
        encoded = encoded.split(",", 1)[1]
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("file_base64 must contain valid base64-encoded PDF bytes.") from exc
    if not data:
        raise ValueError("Uploaded transcript PDF is empty.")
    if len(data) > MAX_TRANSCRIPT_BYTES:
        raise ValueError("Uploaded transcript PDF is larger than the configured limit.")
    if not data.startswith(b"%PDF"):
        raise ValueError("Uploaded transcript file does not look like a PDF.")
    return data


def required_text(payload: Mapping[str, Any], key: str, fallback_key: str | None = None) -> str:
    value = payload.get(key)
    if value is None and fallback_key:
        value = payload.get(fallback_key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing required field `{key}`.")
    return str(value)


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
