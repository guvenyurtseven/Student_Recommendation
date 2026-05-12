from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from student_planner.domain.planning import PlanningReport, PlanningWarningSeverity
from student_planner.services.planning_report_markdown import planning_report_to_markdown

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREPROMPT_PATH = PROJECT_ROOT / "prompts" / "student_planner_report_preprompt.md"
DEFAULT_PROMPT_VERSION = "student-planner-report-v1"
DEFAULT_TASK = "student_planner_semester_narrative"


@dataclass(frozen=True)
class LLMReportPackage:
    task: str
    prompt_version: str
    system_prompt: str
    deterministic_report_markdown: str
    response_contract: Mapping[str, Any]
    model_policy: Mapping[str, Any]
    safety_contract: Mapping[str, Any]
    metadata: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "prompt_version": self.prompt_version,
            "system_prompt": self.system_prompt,
            "deterministic_report_markdown": self.deterministic_report_markdown,
            "response_contract": dict(self.response_contract),
            "model_policy": dict(self.model_policy),
            "safety_contract": dict(self.safety_contract),
            "metadata": dict(self.metadata),
        }


def build_llm_report_package(
    report: PlanningReport,
    *,
    preprompt_path: str | Path | None = None,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> LLMReportPackage:
    system_prompt = load_preprompt(preprompt_path or DEFAULT_PREPROMPT_PATH)
    deterministic_markdown = planning_report_to_markdown(report)
    return LLMReportPackage(
        task=DEFAULT_TASK,
        prompt_version=prompt_version,
        system_prompt=system_prompt,
        deterministic_report_markdown=deterministic_markdown,
        response_contract=response_contract(),
        model_policy=model_policy(),
        safety_contract=safety_contract(),
        metadata=package_metadata(report, deterministic_markdown, system_prompt),
    )


def build_llm_user_message(package: LLMReportPackage) -> str:
    return (
        "Use the deterministic planning report below as the only source of truth.\n\n"
        "<deterministic_report>\n"
        f"{package.deterministic_report_markdown.rstrip()}\n"
        "</deterministic_report>"
    )


def load_preprompt(path: str | Path) -> str:
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"LLM preprompt file does not exist: {resolved}")
    prompt = resolved.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"LLM preprompt file is empty: {resolved}")
    return prompt


def package_metadata(report: PlanningReport, deterministic_markdown: str, system_prompt: str) -> dict[str, Any]:
    placeholder_count = len(
        {
            course.course_code
            for scenario in report.scenarios
            for course in scenario.courses
            if course.requires_explicit_course_selection
        }
    )
    blocker_count = sum(1 for warning in report.warnings if warning.severity == PlanningWarningSeverity.BLOCKER)
    return {
        "program_abbr": report.program_abbr,
        "target_semester_no": report.goal.target_semester_no,
        "difficulty_preference": enum_value(report.goal.difficulty_preference),
        "generated_at_utc": report.generated_at_utc,
        "preferred_scenario_kind": report.metadata.get("preferred_scenario_kind"),
        "scenario_count": len(report.scenarios),
        "warning_count": len(report.warnings),
        "blocker_count": blocker_count,
        "placeholder_elective_count": placeholder_count,
        "deterministic_report_sha256": sha256_text(deterministic_markdown),
        "system_prompt_sha256": sha256_text(system_prompt),
    }


def response_contract() -> dict[str, Any]:
    return {
        "format": "markdown",
        "language": "tr",
        "sections": (
            "Kisa Ozet",
            "Onerilen Yol",
            "Senaryolarin Karsilastirmasi",
            "Dikkat Edilecek Noktalar",
            "Elective Notu",
            "Sonraki Aksiyonlar",
        ),
        "must_not_return_json": True,
        "must_not_change_deterministic_decisions": True,
    }


def model_policy() -> dict[str, Any]:
    return {
        "api": "Responses API",
        "primary_model_tier": "mini",
        "recommended_primary_model": "gpt-5.4-mini",
        "low_cost_fallback_model": "gpt-5-mini",
        "quality_review_model": "gpt-5.5",
        "reasoning_effort": "low",
        "text_verbosity": "medium",
        "temperature": 0.2,
        "max_output_tokens_hint": 1600,
        "execution_mode": "sync_when_capacity_allows_async_during_peak",
        "fallback_behavior": "return_deterministic_markdown_if_llm_unavailable",
        "cache_key_fields": (
            "prompt_version",
            "system_prompt_sha256",
            "deterministic_report_sha256",
            "language",
            "model",
        ),
    }


def safety_contract() -> dict[str, Any]:
    return {
        "llm_may": (
            "summarize_scenarios",
            "explain_tradeoffs",
            "translate_warnings_to_student_language",
            "suggest_double_checks_based_on_existing_warnings",
        ),
        "llm_must_not": (
            "invent_courses",
            "change_prerequisite_status",
            "change_grades",
            "change_ects",
            "override_offering_availability",
            "ask_for_or_expose_credentials",
        ),
    }


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def enum_value(value: Any) -> str:
    return getattr(value, "value", str(value))
