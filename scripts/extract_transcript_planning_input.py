from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from student_planner.domain.planning import PlanningGoal
from student_planner.services.planning_io import student_planning_input_to_dict
from student_planner.services.transcript_ingestion import (
    build_planning_input_from_transcript_text,
    extract_text_from_pdf,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract planner-ready completed course input from a transcript PDF "
            "or already-extracted transcript text. The raw transcript is never "
            "written to disk by this script."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--transcript-pdf",
        help="Transcript PDF path. The file is read in memory and is not copied or stored.",
    )
    source.add_argument(
        "--transcript-text",
        help="Plain text transcript path for local tests or manually extracted text.",
    )
    parser.add_argument(
        "--program",
        help="Optional program abbreviation, e.g. CENG, CE, EEE. If omitted, the script tries to detect it from transcript text.",
    )
    parser.add_argument("--target-semester", required=True, help="Target semester number, e.g. 20252.")
    parser.add_argument(
        "--difficulty-preference",
        choices=("easy", "balanced", "hard"),
        default="balanced",
        help="Desired semester load.",
    )
    parser.add_argument("--target-ects", type=float, help="Optional target ECTS override.")
    parser.add_argument("--min-ects", type=float, help="Optional minimum ECTS override.")
    parser.add_argument("--max-ects", type=float, help="Optional maximum ECTS override.")
    parser.add_argument("--target-term-gpa", type=float, help="Optional target term GPA.")
    parser.add_argument("--target-cumulative-gpa", type=float, help="Optional target cumulative GPA.")
    parser.add_argument("--output", help="Optional output JSON path. Prints to stdout when omitted.")
    parser.add_argument("--compact", action="store_true", help="Write compact JSON.")
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_transcript_text(args: argparse.Namespace) -> str:
    if args.transcript_pdf:
        return extract_text_from_pdf(project_path(args.transcript_pdf))
    return project_path(args.transcript_text).read_text(encoding="utf-8")


def main() -> int:
    args = parse_args()
    goal = PlanningGoal(
        target_semester_no=args.target_semester,
        difficulty_preference=args.difficulty_preference,
        target_ects=args.target_ects,
        min_ects=args.min_ects,
        max_ects=args.max_ects,
        target_term_gpa=args.target_term_gpa,
        target_cumulative_gpa=args.target_cumulative_gpa,
    )
    planning_input = build_planning_input_from_transcript_text(
        load_transcript_text(args),
        program_abbr=args.program,
        goal=goal,
    )
    text = json.dumps(
        student_planning_input_to_dict(planning_input),
        ensure_ascii=False,
        indent=None if args.compact else 2,
        sort_keys=False,
    )

    if args.output:
        output_path = project_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote planner input JSON to {output_path.resolve()}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
