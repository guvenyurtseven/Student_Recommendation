from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from student_planner.config import load_engineering_programs
from student_planner.domain.models import Program
from student_planner.sources.sais import (
    SaisCourseDetailsSession,
    load_env_file,
    write_offerings_output,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape METU SAIS course offerings for selected departments and semesters."
    )
    parser.add_argument(
        "--programs",
        nargs="*",
        help="Department/program abbreviations to scrape. Defaults to all active entries in the offering config.",
    )
    parser.add_argument(
        "--semesters",
        nargs="+",
        required=True,
        help="Semester numbers to scrape, for example 20241 20242.",
    )
    parser.add_argument(
        "--config",
        default="config/offering_departments.json",
        help="Offering department config path.",
    )
    parser.add_argument(
        "--raw-root",
        default="data/raw",
        help="Directory for raw SAIS snapshots.",
    )
    parser.add_argument(
        "--processed-root",
        default="data/processed",
        help="Directory for normalized offering outputs.",
    )
    parser.add_argument(
        "--env-file",
        default="env.local",
        help="Credential file containing METU_USERNAME and METU_PASSWORD.",
    )
    return parser.parse_args()


def select_programs(config_path: Path, requested: list[str] | None) -> list[Program]:
    wanted = {abbr.upper() for abbr in requested} if requested else None
    programs = [
        program
        for program in load_engineering_programs(config_path)
        if program.is_active_undergraduate and (wanted is None or program.abbr in wanted)
    ]
    if wanted:
        found = {program.abbr for program in programs}
        missing = wanted.difference(found)
        if missing:
            raise RuntimeError(f"Unknown or inactive programs: {', '.join(sorted(missing))}")
    return programs


def credentials_from_env(env_file: Path) -> tuple[str, str]:
    load_env_file(env_file)
    username = os.environ.get("METU_USERNAME")
    password = os.environ.get("METU_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            f"METU_USERNAME and METU_PASSWORD are required in {env_file} or environment variables."
        )
    return username, password


def write_combined_offerings_csv(payloads: list[dict[str, Any]], processed_root: Path) -> Path:
    output_path = processed_root / "offerings" / "all_scraped_offerings.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "program_abbr",
        "semester_no",
        "semester_text",
        "department_value",
        "department_text",
        "numeric_code",
        "display_code",
        "course_number",
        "course_name",
        "ects_credit",
        "credit",
        "level",
        "type",
        "source_url",
        "retrieved_at_utc",
        "content_path",
    ]

    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for payload in payloads:
            source = payload["source"]
            for offering in payload["offerings"]:
                writer.writerow(
                    {
                        **{key: offering.get(key, "") for key in fieldnames},
                        "source_url": source["source_url"],
                        "retrieved_at_utc": source["retrieved_at_utc"],
                        "content_path": source["content_path"],
                    }
                )

    return output_path


def main() -> int:
    args = parse_args()
    try:
        programs = select_programs(Path(args.config), args.programs)
        username, password = credentials_from_env(Path(args.env_file))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    raw_root = Path(args.raw_root)
    processed_root = Path(args.processed_root)
    payloads: list[dict[str, Any]] = []
    session = SaisCourseDetailsSession.from_credentials(username, password)

    try:
        session.open()
        for semester_no in args.semesters:
            for program in programs:
                payload = session.fetch_offerings(program, semester_no, raw_root)
                payloads.append(payload)
                output_path = write_offerings_output(payload, processed_root)
                print(
                    f"{program.abbr} {semester_no}: "
                    f"{payload['summary']['offering_count']} offerings -> {output_path}"
                )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    combined_path = write_combined_offerings_csv(payloads, processed_root)
    print(f"Combined offerings CSV: {combined_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
