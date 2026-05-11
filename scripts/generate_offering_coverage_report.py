from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass(frozen=True)
class CurriculumCourseNeed:
    program_abbr: str
    course_code: str
    subject_code: str
    recommended_term: str
    requirement_type: str
    requirement_label: str


@dataclass(frozen=True)
class CourseOfferingCoverage:
    need: CurriculumCourseNeed
    offered_semesters: tuple[str, ...] = ()

    @property
    def is_seen_in_loaded_offerings(self) -> bool:
        return bool(self.offered_semesters)


@dataclass(frozen=True)
class SubjectCoverage:
    subject_code: str
    curriculum_course_count: int
    program_count: int
    offered_course_count: int
    offered_semesters: tuple[str, ...] = ()
    programs: tuple[str, ...] = ()

    @property
    def has_loaded_offerings(self) -> bool:
        return self.offered_course_count > 0


@dataclass(frozen=True)
class OfferingCoverageSummary:
    semester_counts: dict[str, int]
    program_semester_counts: dict[tuple[str, str], int]
    subject_coverages: tuple[SubjectCoverage, ...]
    course_coverages: tuple[CourseOfferingCoverage, ...]

    @property
    def curriculum_course_count(self) -> int:
        return len(self.course_coverages)

    @property
    def seen_curriculum_course_count(self) -> int:
        return sum(1 for item in self.course_coverages if item.is_seen_in_loaded_offerings)

    @property
    def missing_curriculum_course_count(self) -> int:
        return self.curriculum_course_count - self.seen_curriculum_course_count

    @property
    def missing_subjects(self) -> tuple[SubjectCoverage, ...]:
        return tuple(item for item in self.subject_coverages if not item.has_loaded_offerings)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate offering coverage reports from the local planner database."
    )
    parser.add_argument(
        "--db",
        default="data/db/student_planner.sqlite",
        help="SQLite database path.",
    )
    parser.add_argument(
        "--report",
        default="data/processed/reports/offering_coverage_report.md",
        help="Markdown report output path.",
    )
    parser.add_argument(
        "--missing-csv",
        default="data/processed/reports/offering_missing_curriculum_courses.csv",
        help="CSV output for curriculum courses not seen in loaded offerings.",
    )
    parser.add_argument(
        "--semesters",
        nargs="*",
        help="Restrict coverage analysis to selected semester numbers.",
    )
    return parser.parse_args()


def build_summary(
    connection: sqlite3.Connection,
    semesters: list[str] | None = None,
) -> OfferingCoverageSummary:
    selected_semesters = normalize_semester_filter(semesters)
    semester_counts = fetch_semester_counts(connection, selected_semesters)
    program_semester_counts = fetch_program_semester_counts(connection, selected_semesters)
    needs = fetch_latest_curriculum_course_needs(connection)
    offerings_by_course = fetch_offerings_by_course(connection, selected_semesters)
    subject_coverages = build_subject_coverages(needs, offerings_by_course)
    course_coverages = tuple(
        CourseOfferingCoverage(
            need=need,
            offered_semesters=offerings_by_course.get(need.course_code, ()),
        )
        for need in needs
    )
    return OfferingCoverageSummary(
        semester_counts=semester_counts,
        program_semester_counts=program_semester_counts,
        subject_coverages=subject_coverages,
        course_coverages=course_coverages,
    )


def normalize_semester_filter(semesters: list[str] | None) -> tuple[str, ...]:
    return tuple(sorted({semester.strip() for semester in semesters or [] if semester.strip()}))


def semester_filter_clause(semesters: tuple[str, ...], table_alias: str = "o") -> tuple[str, tuple[str, ...]]:
    if not semesters:
        return "", ()
    placeholders = ", ".join("?" for _ in semesters)
    return f"WHERE {table_alias}.semester_no IN ({placeholders})", semesters


def fetch_semester_counts(
    connection: sqlite3.Connection,
    semesters: tuple[str, ...] = (),
) -> dict[str, int]:
    where_clause, params = semester_filter_clause(semesters, table_alias="offerings")
    rows = connection.execute(
        f"""
        SELECT semester_no, COUNT(*) AS offering_count
        FROM offerings
        {where_clause}
        GROUP BY semester_no
        ORDER BY semester_no
        """,
        params,
    )
    return {row["semester_no"]: int(row["offering_count"]) for row in rows}


def fetch_program_semester_counts(
    connection: sqlite3.Connection,
    semesters: tuple[str, ...] = (),
) -> dict[tuple[str, str], int]:
    semester_predicate = ""
    params: tuple[str, ...] = ()
    if semesters:
        placeholders = ", ".join("?" for _ in semesters)
        semester_predicate = f"WHERE o.semester_no IN ({placeholders})"
        params = semesters
    rows = connection.execute(
        f"""
        SELECT p.abbr AS program_abbr,
               o.semester_no,
               COUNT(*) AS offering_count
        FROM offerings o
        LEFT JOIN programs p ON p.id = o.department_program_id
        {semester_predicate}
        GROUP BY p.abbr, o.semester_no
        ORDER BY p.abbr, o.semester_no
        """,
        params,
    )
    return {
        (row["program_abbr"] or "UNKNOWN", row["semester_no"]): int(row["offering_count"])
        for row in rows
    }


def fetch_latest_curriculum_course_needs(connection: sqlite3.Connection) -> tuple[CurriculumCourseNeed, ...]:
    rows = connection.execute(
        """
        SELECT DISTINCT
               p.abbr AS program_abbr,
               c.display_code,
               c.subject_code,
               cr.recommended_term,
               cr.requirement_type,
               cr.label
        FROM curriculum_versions cv
        JOIN programs p ON p.id = cv.program_id
        JOIN curriculum_requirements cr ON cr.curriculum_version_id = cv.id
        JOIN requirement_options ro ON ro.requirement_id = cr.id
        JOIN courses c ON c.id = ro.course_id
        WHERE cv.is_latest = 1
          AND p.is_active_undergraduate = 1
        ORDER BY p.abbr, c.display_code, cr.sort_order
        """
    )
    return tuple(
        CurriculumCourseNeed(
            program_abbr=row["program_abbr"],
            course_code=row["display_code"],
            subject_code=row["subject_code"],
            recommended_term=row["recommended_term"] or "",
            requirement_type=row["requirement_type"],
            requirement_label=row["label"],
        )
        for row in rows
    )


def fetch_offerings_by_course(
    connection: sqlite3.Connection,
    semesters: tuple[str, ...] = (),
) -> dict[str, tuple[str, ...]]:
    semester_predicate = ""
    params: tuple[str, ...] = ()
    if semesters:
        placeholders = ", ".join("?" for _ in semesters)
        semester_predicate = f"WHERE o.semester_no IN ({placeholders})"
        params = semesters
    rows = connection.execute(
        f"""
        SELECT c.display_code,
               o.semester_no
        FROM offerings o
        JOIN courses c ON c.id = o.course_id
        {semester_predicate}
        ORDER BY c.display_code, o.semester_no
        """,
        params,
    )
    grouped: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        grouped[row["display_code"]].add(row["semester_no"])
    return {
        course_code: tuple(sorted(semesters))
        for course_code, semesters in grouped.items()
    }


def build_subject_coverages(
    needs: Iterable[CurriculumCourseNeed],
    offerings_by_course: dict[str, tuple[str, ...]],
) -> tuple[SubjectCoverage, ...]:
    curriculum_courses_by_subject: dict[str, set[str]] = defaultdict(set)
    programs_by_subject: dict[str, set[str]] = defaultdict(set)
    offered_courses_by_subject: dict[str, set[str]] = defaultdict(set)
    offered_semesters_by_subject: dict[str, set[str]] = defaultdict(set)

    for need in needs:
        curriculum_courses_by_subject[need.subject_code].add(need.course_code)
        programs_by_subject[need.subject_code].add(need.program_abbr)

    for course_code, semesters in offerings_by_course.items():
        subject = subject_code(course_code)
        offered_courses_by_subject[subject].add(course_code)
        offered_semesters_by_subject[subject].update(semesters)

    subjects = sorted(set(curriculum_courses_by_subject).union(offered_courses_by_subject))
    return tuple(
        SubjectCoverage(
            subject_code=subject,
            curriculum_course_count=len(curriculum_courses_by_subject.get(subject, set())),
            program_count=len(programs_by_subject.get(subject, set())),
            offered_course_count=len(offered_courses_by_subject.get(subject, set())),
            offered_semesters=tuple(sorted(offered_semesters_by_subject.get(subject, set()))),
            programs=tuple(sorted(programs_by_subject.get(subject, set()))),
        )
        for subject in subjects
    )


def subject_code(course_code: str) -> str:
    return course_code.split(" ", 1)[0].upper()


def write_markdown_report(
    summary: OfferingCoverageSummary,
    report_path: Path,
    selected_semesters: tuple[str, ...] = (),
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Offering Coverage Report",
        "",
        "Status: generated from the local SQLite database.",
        "",
        "## Summary",
        "",
        f"- Coverage scope: {', '.join(selected_semesters) if selected_semesters else 'all loaded semesters'}",
        f"- Loaded semesters: {len(summary.semester_counts)}",
        f"- Loaded offering rows: {sum(summary.semester_counts.values())}",
        f"- Latest-curriculum concrete course references: {summary.curriculum_course_count}",
        f"- Curriculum course references seen in loaded offerings: {summary.seen_curriculum_course_count}",
        f"- Curriculum course references not seen in loaded offerings: {summary.missing_curriculum_course_count}",
        f"- Curriculum subject codes without loaded offering coverage: {len(summary.missing_subjects)}",
        "",
        "## Offering Counts By Semester",
        "",
        "| Semester | Offerings |",
        "| --- | ---: |",
    ]
    for semester_no, count in summary.semester_counts.items():
        lines.append(f"| {semester_no} | {count} |")

    lines.extend(
        [
            "",
            "## Subject Coverage",
            "",
            "| Subject | Curriculum Courses | Programs Using Subject | Offered Courses | Offered Semesters |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for item in sorted(summary.subject_coverages, key=subject_sort_key):
        lines.append(
            "| {subject} | {curriculum_count} | {program_count} | {offered_count} | {semesters} |".format(
                subject=item.subject_code,
                curriculum_count=item.curriculum_course_count,
                program_count=item.program_count,
                offered_count=item.offered_course_count,
                semesters=", ".join(item.offered_semesters) or "-",
            )
        )

    lines.extend(
        [
            "",
            "## Missing High-Impact Service Subjects",
            "",
            "If any rows appear below, those curriculum subjects have no loaded offering rows in this scope.",
            "",
            "| Subject | Curriculum Courses | Programs |",
            "| --- | ---: | --- |",
        ]
    )
    for item in sorted(summary.missing_subjects, key=lambda value: (-value.program_count, value.subject_code)):
        lines.append(
            f"| {item.subject_code} | {item.curriculum_course_count} | {', '.join(item.programs)} |"
        )
    if not summary.missing_subjects:
        lines.append("| - | 0 | All curriculum subjects have loaded offering coverage in this scope. |")

    lines.extend(
        [
            "",
            "## Next Data Actions",
            "",
            "1. For the next planning cycle, scrape one fresh target-semester snapshot after SAIS updates offerings.",
            "2. Load only that target semester with `scripts/load_offerings.py --semesters <TARGET> --clear-existing --prune-orphan-non-undergraduate-courses`.",
            "3. Re-run this report with `--semesters <TARGET>` and then run the data quality audit.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def subject_sort_key(item: SubjectCoverage) -> tuple[int, int, str]:
    missing_rank = 0 if not item.has_loaded_offerings and item.curriculum_course_count else 1
    return (missing_rank, -item.program_count, item.subject_code)


def write_missing_courses_csv(summary: OfferingCoverageSummary, csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "program_abbr",
        "course_code",
        "subject_code",
        "recommended_term",
        "requirement_type",
        "requirement_label",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for item in summary.course_coverages:
            if item.is_seen_in_loaded_offerings:
                continue
            writer.writerow(
                {
                    "program_abbr": item.need.program_abbr,
                    "course_code": item.need.course_code,
                    "subject_code": item.need.subject_code,
                    "recommended_term": item.need.recommended_term,
                    "requirement_type": item.need.requirement_type,
                    "requirement_label": item.need.requirement_label,
                }
            )


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        selected_semesters = normalize_semester_filter(args.semesters)
        summary = build_summary(connection, semesters=args.semesters)

    report_path = Path(args.report)
    csv_path = Path(args.missing_csv)
    write_markdown_report(summary, report_path, selected_semesters=selected_semesters)
    write_missing_courses_csv(summary, csv_path)
    print(f"Offering coverage report: {report_path.resolve()}")
    print(f"Missing curriculum course CSV: {csv_path.resolve()}")
    print(
        f"Loaded offerings={sum(summary.semester_counts.values())}, "
        f"missing curriculum references={summary.missing_curriculum_course_count}, "
        f"missing subjects={len(summary.missing_subjects)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
