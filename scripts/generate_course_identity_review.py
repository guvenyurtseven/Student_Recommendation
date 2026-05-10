from __future__ import annotations

import argparse
import csv
import datetime as dt
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = "data/db/student_planner.sqlite"
DEFAULT_PREREQUISITES_DIR = "data/processed/prerequisites"
DEFAULT_REPORT = "data/processed/reports/course_identity_review.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a focused course identity review report."
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database path.")
    parser.add_argument(
        "--prerequisites-dir",
        default=DEFAULT_PREREQUISITES_DIR,
        help="Directory containing prerequisite closure CSV files.",
    )
    parser.add_argument("--report", default=DEFAULT_REPORT, help="Markdown report output path.")
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def query_rows(
    connection: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
) -> list[sqlite3.Row]:
    return list(connection.execute(sql, params).fetchall())


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    args = parse_args()
    db_path = project_path(args.db)
    prerequisites_dir = project_path(args.prerequisites_dir)
    report_path = project_path(args.report)

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        payload = collect_review_payload(connection, prerequisites_dir)

    write_report(report_path, payload)
    print(f"Course identity review report: {report_path.resolve()}")
    return 0


def collect_review_payload(
    connection: sqlite3.Connection,
    prerequisites_dir: Path,
) -> dict[str, Any]:
    numeric_subject_courses = query_rows(
        connection,
        """
        SELECT display_code, numeric_code, subject_code, course_number, title_en
        FROM courses
        WHERE subject_code GLOB '[0-9]*'
        ORDER BY subject_code, course_number
        """,
    )
    ncc_edges = query_rows(
        connection,
        """
        SELECT prereq.display_code AS prereq_code,
               prereq.numeric_code AS prereq_numeric,
               prereq.title_en AS prereq_title,
               course.display_code AS course_code,
               course.numeric_code AS course_numeric,
               course.title_en AS course_title,
               pe.set_no,
               pe.min_grade,
               pe.edge_type,
               pe.position
        FROM prerequisite_edges pe
        JOIN courses prereq ON prereq.id = pe.prerequisite_course_id
        JOIN courses course ON course.id = pe.course_id
        WHERE pe.edge_type LIKE '%NCC%'
        ORDER BY course.display_code, pe.set_no, prereq.display_code
        """,
    )
    empty_title_courses = query_rows(
        connection,
        """
        SELECT display_code, numeric_code, subject_code, course_number
        FROM courses
        WHERE title_en IS NULL OR trim(title_en) = ''
        ORDER BY display_code
        """,
    )
    high_number_courses = query_rows(
        connection,
        """
        SELECT display_code, numeric_code, title_en
        FROM courses
        WHERE course_number > 999
        ORDER BY display_code
        """,
    )
    unresolved_rows = collect_unresolved(prerequisites_dir)

    return {
        "numeric_subject_courses": [dict(row) for row in numeric_subject_courses],
        "ncc_edges": [dict(row) for row in ncc_edges],
        "empty_title_courses": [dict(row) for row in empty_title_courses],
        "high_number_courses": [dict(row) for row in high_number_courses],
        "unresolved": unresolved_rows,
    }


def collect_unresolved(prerequisites_dir: Path) -> list[dict[str, str]]:
    by_course: dict[str, dict[str, Any]] = {}
    for path in sorted(prerequisites_dir.glob("*-latest-prerequisite-closure-unresolved.csv")):
        if path.name.startswith("engineering-"):
            program = "engineering"
        else:
            program = path.name.split("-", 1)[0]
        for row in read_csv_rows(path):
            key = row.get("course_code_numeric") or row.get("course_code") or ""
            if not key:
                continue
            entry = by_course.setdefault(
                key,
                {
                    "course_code_numeric": row.get("course_code_numeric", ""),
                    "course_code": row.get("course_code", ""),
                    "reason": row.get("reason", ""),
                    "programs": set(),
                },
            )
            entry["programs"].add(program)

    rows = []
    for entry in by_course.values():
        programs = sorted(program for program in entry["programs"] if program != "engineering")
        rows.append(
            {
                "course_code_numeric": entry["course_code_numeric"],
                "course_code": entry["course_code"],
                "reason": entry["reason"],
                "programs": ", ".join(programs),
            }
        )
    return sorted(rows, key=lambda row: (row["course_code"], row["course_code_numeric"]))


def write_report(report_path: Path, payload: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    numeric_subject_courses = payload["numeric_subject_courses"]
    ncc_edges = payload["ncc_edges"]
    empty_title_courses = payload["empty_title_courses"]
    high_number_courses = payload["high_number_courses"]
    unresolved = payload["unresolved"]

    lines: list[str] = [
        "# Course Identity Review",
        "",
        f"Generated at UTC: `{generated_at}`",
        "",
        "This report is a manual review queue for course identity issues that should be resolved before student-facing recommendations.",
        "",
        "## Summary",
        "",
        f"- Numeric subject-code courses: {len(numeric_subject_courses)}",
        f"- NCC prerequisite edges: {len(ncc_edges)}",
        f"- Unresolved prerequisite courses: {len(unresolved)}",
        f"- Courses with empty title: {len(empty_title_courses)}",
        f"- Course numbers above 999: {len(high_number_courses)}",
        "",
        "## Recommended Review Decisions",
        "",
        "1. Decide whether numeric subject-code courses are Ankara aliases, NCC alternatives, or independent courses.",
        "2. Add approved aliases to `course_aliases` or a manual correction file before UI work.",
        "3. Keep NCC alternatives in the raw graph, but label or filter them in student-facing recommendations.",
        "4. Resolve unresolved courses by checking old course codes, department pages, and SAIS availability.",
        "5. Fill missing titles only from an authoritative source.",
        "",
    ]

    grouped_numeric: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in numeric_subject_courses:
        grouped_numeric[row["subject_code"]].append(row)

    lines.extend(["## Numeric Subject-Code Courses", ""])
    if grouped_numeric:
        for subject_code, rows in grouped_numeric.items():
            lines.extend([f"### Subject `{subject_code}`", "", "| Display | Numeric | Title |", "| --- | --- | --- |"])
            for row in rows:
                lines.append(
                    f"| `{row['display_code']}` | `{row['numeric_code']}` | {row['title_en'] or ''} |"
                )
            lines.append("")
    else:
        lines.extend(["None.", ""])

    lines.extend(
        [
            "## NCC Prerequisite Edges",
            "",
            "| Prerequisite | Course | Set | Min Grade | Type |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    if ncc_edges:
        for row in ncc_edges:
            lines.append(
                f"| `{row['prereq_code']}` | `{row['course_code']}` | "
                f"{row['set_no']} | {row['min_grade']} | {row['edge_type']} |"
            )
    else:
        lines.append("| None |  |  |  |  |")
    lines.append("")

    lines.extend(
        [
            "## Unresolved Prerequisite Courses",
            "",
            f"Source: `{relative(project_path(DEFAULT_PREREQUISITES_DIR))}`",
            "",
            "| Course | Numeric | Programs | Reason |",
            "| --- | --- | --- | --- |",
        ]
    )
    if unresolved:
        for row in unresolved:
            lines.append(
                f"| `{row['course_code']}` | `{row['course_code_numeric']}` | "
                f"{row['programs']} | {row['reason']} |"
            )
    else:
        lines.append("| None |  |  |  |")
    lines.append("")

    lines.extend(["## Courses With Empty Title", "", "| Course | Numeric |", "| --- | --- |"])
    if empty_title_courses:
        for row in empty_title_courses:
            lines.append(f"| `{row['display_code']}` | `{row['numeric_code']}` |")
    else:
        lines.append("| None |  |")
    lines.append("")

    lines.extend(
        [
            "## Course Numbers Above 999",
            "",
            "These are not automatically wrong. METU has undergraduate service courses such as HIST 2201.",
            "",
            "| Course | Numeric | Title |",
            "| --- | --- | --- |",
        ]
    )
    if high_number_courses:
        for row in high_number_courses:
            lines.append(f"| `{row['display_code']}` | `{row['numeric_code']}` | {row['title_en'] or ''} |")
    else:
        lines.append("| None |  |  |")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
