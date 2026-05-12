from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from student_planner.services.operation_semester import (
    operation_semester_to_dict,
    validate_semester_no,
    write_operation_semester,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh current semester offerings from METU SAIS, load them into SQLite, "
            "then mark the semester as the active operation semester."
        )
    )
    parser.add_argument("--semester", required=True, help="METU semester number, for example 20252.")
    parser.add_argument("--db", default="data/db/student_planner.sqlite", help="SQLite database path.")
    parser.add_argument("--skip-scrape", action="store_true", help="Use already processed offering JSON files.")
    parser.add_argument("--skip-load", action="store_true", help="Do not load processed offerings into SQLite.")
    parser.add_argument("--skip-coverage", action="store_true", help="Do not regenerate offering coverage report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    semester_no = validate_semester_no(args.semester)

    try:
        if not args.skip_scrape:
            run_step(
                [
                    sys.executable,
                    "scripts/scrape_offerings.py",
                    "--semesters",
                    semester_no,
                ],
                "scrape_offerings",
            )
        if not args.skip_load:
            run_step(
                [
                    sys.executable,
                    "scripts/load_offerings.py",
                    "--db",
                    args.db,
                    "--semesters",
                    semester_no,
                    "--clear-existing",
                    "--prune-orphan-non-undergraduate-courses",
                ],
                "load_offerings",
            )
        if not args.skip_coverage:
            run_step(
                [
                    sys.executable,
                    "scripts/generate_offering_coverage_report.py",
                    "--db",
                    args.db,
                    "--semesters",
                    semester_no,
                ],
                "generate_offering_coverage_report",
            )
        operation = write_operation_semester(semester_no, updated_by="admin_refresh_operation_semester.py")
        print(f"operation_semester_updated={operation_semester_to_dict(operation)}")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"Step failed: {exc}", file=sys.stderr)
        return exc.returncode or 1


def run_step(command: list[str], label: str) -> None:
    print(f"== {label} ==")
    print(" ".join(command))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
