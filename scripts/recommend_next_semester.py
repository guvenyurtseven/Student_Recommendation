from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from student_planner.repositories.sqlite import SQLiteStudentPlannerRepository
from student_planner.services.planning_io import (
    load_student_planning_input,
    planning_report_to_text,
)
from student_planner.services.planning_pipeline import SemesterPlanningPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic next-semester course recommendation scenarios."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Student planning input JSON path.",
    )
    parser.add_argument(
        "--db",
        default="data/db/student_planner.sqlite",
        help="SQLite database path.",
    )
    parser.add_argument(
        "--output",
        help="Optional output path. Prints to stdout when omitted.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "llm-package"),
        default="json",
        help="Output format.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON instead of pretty-printed JSON.",
    )
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    planning_input = load_student_planning_input(project_path(args.input))
    repository = SQLiteStudentPlannerRepository(project_path(args.db))
    report = SemesterPlanningPipeline(repository).build_report(planning_input)
    text = planning_report_to_text(report, output_format=args.format, compact=args.compact)

    if args.output:
        output_path = project_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.format} recommendation report to {output_path.resolve()}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
