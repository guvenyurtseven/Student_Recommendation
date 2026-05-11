from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from student_planner.web.api import (
    recommendation_from_json_payload,
    recommendation_from_transcript_payload,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JSON bridge used by the Node web server.")
    parser.add_argument("--mode", choices=("json", "transcript"), required=True)
    parser.add_argument("--db", default=str(PROJECT_ROOT / "data" / "db" / "student_planner.sqlite"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("Bridge payload must be a JSON object.")
        if args.mode == "json":
            response = recommendation_from_json_payload(payload, args.db)
        else:
            response = recommendation_from_transcript_payload(payload, args.db)
        json.dump(response, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
