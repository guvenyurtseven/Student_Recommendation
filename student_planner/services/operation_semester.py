from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPERATION_CONFIG_PATH = PROJECT_ROOT / "config" / "operation.json"


@dataclass(frozen=True)
class OperationSemester:
    active_semester_no: str
    active_semester_label: str
    updated_at_utc: str | None = None
    updated_by: str | None = None


def load_operation_semester(path: str | Path | None = None) -> OperationSemester:
    config_path = Path(path) if path is not None else DEFAULT_OPERATION_CONFIG_PATH
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    semester_no = str(payload["active_semester_no"]).strip()
    return OperationSemester(
        active_semester_no=semester_no,
        active_semester_label=str(payload.get("active_semester_label") or semester_label(semester_no)),
        updated_at_utc=optional_text(payload.get("updated_at_utc")),
        updated_by=optional_text(payload.get("updated_by")),
    )


def write_operation_semester(
    semester_no: str,
    path: str | Path | None = None,
    *,
    updated_by: str = "admin_refresh",
) -> OperationSemester:
    clean_semester = validate_semester_no(semester_no)
    operation = OperationSemester(
        active_semester_no=clean_semester,
        active_semester_label=semester_label(clean_semester),
        updated_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        updated_by=updated_by,
    )
    config_path = Path(path) if path is not None else DEFAULT_OPERATION_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "active_semester_no": operation.active_semester_no,
                "active_semester_label": operation.active_semester_label,
                "updated_at_utc": operation.updated_at_utc,
                "updated_by": operation.updated_by,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return operation


def validate_semester_no(semester_no: str) -> str:
    clean = str(semester_no).strip()
    if len(clean) != 5 or not clean.isdigit() or clean[-1] not in {"1", "2", "3"}:
        raise ValueError("semester_no must use the METU 5-digit format, for example 20252.")
    return clean


def semester_label(semester_no: str) -> str:
    clean = validate_semester_no(semester_no)
    first_year = int(clean[:4])
    term = clean[-1]
    term_label = {
        "1": "Fall",
        "2": "Spring",
        "3": "Summer",
    }[term]
    return f"{first_year}-{first_year + 1} {term_label}"


def operation_semester_to_dict(operation: OperationSemester) -> dict[str, Any]:
    return {
        "active_semester_no": operation.active_semester_no,
        "active_semester_label": operation.active_semester_label,
        "updated_at_utc": operation.updated_at_utc,
        "updated_by": operation.updated_by,
    }


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None
