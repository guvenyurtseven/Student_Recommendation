from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from student_planner.web.app_data import (
    delete_feedback,
    ensure_app_tables,
    list_feedback,
    set_feedback_favorite,
    submit_feedback,
    verify_admin_credentials,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JSON bridge for web app feedback/admin data.")
    parser.add_argument(
        "--mode",
        choices=(
            "ensure",
            "verify-admin",
            "submit-feedback",
            "list-feedback",
            "favorite-feedback",
            "delete-feedback",
        ),
        required=True,
    )
    parser.add_argument("--db", default=str(PROJECT_ROOT / "data" / "db" / "student_planner.sqlite"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = read_payload()
        response = dispatch(args.mode, args.db, payload)
        json.dump(response, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1


def dispatch(mode: str, db_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    if mode == "ensure":
        ensure_app_tables(db_path)
        return {"ok": True}
    if mode == "verify-admin":
        return verify_admin_credentials(
            db_path,
            username=str(payload.get("username", "")),
            password=str(payload.get("password", "")),
        )
    if mode == "submit-feedback":
        return submit_feedback(db_path, str(payload.get("text", "")))
    if mode == "list-feedback":
        return list_feedback(db_path)
    if mode == "favorite-feedback":
        return set_feedback_favorite(
            db_path,
            feedback_id=int(payload["id"]),
            is_favorite=bool(payload.get("is_favorite", True)),
        )
    if mode == "delete-feedback":
        return delete_feedback(db_path, int(payload["id"]))
    raise ValueError(f"Unknown mode: {mode}")


def read_payload() -> dict[str, Any]:
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Bridge payload must be a JSON object.")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
