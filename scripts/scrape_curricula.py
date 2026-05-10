from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from student_planner.config import load_engineering_programs
from student_planner.sources.metu_catalog import (
    fetch_program_snapshot,
    parse_program_curriculum,
    write_curriculum_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape latest METU Catalog curricula for engineering programs."
    )
    parser.add_argument(
        "--programs",
        nargs="*",
        help="Program abbreviations to scrape. Defaults to all active undergraduate programs.",
    )
    parser.add_argument(
        "--config",
        default="config/engineering_programs.json",
        help="Engineering program config path.",
    )
    parser.add_argument(
        "--raw-root",
        default="data/raw",
        help="Directory for raw source snapshots.",
    )
    parser.add_argument(
        "--processed-root",
        default="data/processed",
        help="Directory for normalized curriculum outputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wanted = {abbr.upper() for abbr in args.programs} if args.programs else None
    programs = [
        program
        for program in load_engineering_programs(Path(args.config))
        if program.is_active_undergraduate and (wanted is None or program.abbr in wanted)
    ]

    if wanted:
        found = {program.abbr for program in programs}
        missing = wanted.difference(found)
        if missing:
            print(f"Unknown or inactive programs: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2

    raw_root = Path(args.raw_root)
    processed_root = Path(args.processed_root)
    summary_rows = []
    generated_csv_paths: list[Path] = []

    for program in programs:
        snapshot = fetch_program_snapshot(program, raw_root)
        curriculum = parse_program_curriculum(snapshot, program)
        json_path, csv_path = write_curriculum_outputs(curriculum, processed_root)
        generated_csv_paths.append(csv_path)
        summary = curriculum["summary"]
        summary_rows.append(
            {
                "program_abbr": program.abbr,
                "catalog_program_id": program.catalog_program_id,
                "requirement_count": summary["requirement_count"],
                "unique_course_count": summary["unique_course_count"],
                "course_option_count": summary["course_option_count"],
                "placeholder_requirement_count": summary["placeholder_requirement_count"],
                "json_path": str(json_path),
                "csv_path": str(csv_path),
            }
        )
        print(
            f"{program.abbr}: {summary['requirement_count']} requirements, "
            f"{summary['unique_course_count']} unique courses"
        )

    summary_path = processed_root / "curricula" / "curriculum_scrape_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        fieldnames = [
            "program_abbr",
            "catalog_program_id",
            "requirement_count",
            "unique_course_count",
            "course_option_count",
            "placeholder_requirement_count",
            "json_path",
            "csv_path",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    combined_path = write_combined_requirements_csv(
        generated_csv_paths,
        processed_root / "curricula" / "all_engineering_latest_curriculum_requirements.csv",
    )
    report_path = write_review_report(
        summary_rows,
        processed_root / "curricula" / "curriculum_review_report.md",
    )

    print(f"Summary: {summary_path.resolve()}")
    print(f"Combined requirements: {combined_path.resolve()}")
    print(f"Review report: {report_path.resolve()}")
    return 0


def write_combined_requirements_csv(csv_paths: list[Path], output_path: Path) -> Path:
    rows = []
    fieldnames: list[str] | None = None

    for csv_path in csv_paths:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            fieldnames = fieldnames or list(reader.fieldnames or [])
            rows.extend(reader)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames or [])
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def write_review_report(summary_rows: list[dict[str, object]], output_path: Path) -> Path:
    total_requirements = sum(int(row["requirement_count"]) for row in summary_rows)
    total_unique_courses = sum(int(row["unique_course_count"]) for row in summary_rows)

    lines = [
        "# Curriculum Scrape Review Report",
        "",
        "Status: automatically scraped, requires human review before production use.",
        "",
        f"Programs scraped: {len(summary_rows)}",
        f"Total requirement slots: {total_requirements}",
        f"Sum of per-program unique course counts: {total_unique_courses}",
        "",
        "| Program | Requirements | Unique courses | Course option rows | Placeholder requirements |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            "| {program_abbr} | {requirement_count} | {unique_course_count} | "
            "{course_option_count} | {placeholder_requirement_count} |".format(**row)
        )

    lines.extend(
        [
            "",
            "## Required Manual Checks",
            "",
            "- Confirm each curriculum is the latest applicable undergraduate curriculum.",
            "- Confirm elective placeholders are semantically correct.",
            "- Confirm course-choice groups such as HIST/TURK alternatives are represented correctly.",
            "- Confirm service courses from other departments are present.",
            "- Confirm no department-specific website has a newer curriculum than Catalog.",
            "",
            "## Source",
            "",
            "Primary source is METU Academic Catalog `program.php?fac_prog=<program_id>` pages.",
        ]
    )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


if __name__ == "__main__":
    raise SystemExit(main())
