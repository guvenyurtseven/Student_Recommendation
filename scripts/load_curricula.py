from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load processed curriculum JSON files into SQLite.")
    parser.add_argument(
        "--db",
        default="data/db/student_planner.sqlite",
        help="SQLite database path.",
    )
    parser.add_argument(
        "--curricula-dir",
        default="data/processed/curricula",
        help="Directory containing *-latest.curriculum.json files.",
    )
    return parser.parse_args()


def parse_display_code(display_code: str) -> tuple[str, int]:
    match = re.match(r"^([A-Z]+)\s+(\d+)", display_code.strip())
    if not match:
        raise RuntimeError(f"Could not parse display course code: {display_code}")
    return match.group(1), int(match.group(2))


def upsert_source_document(connection: sqlite3.Connection, curriculum: dict[str, Any]) -> int:
    source = curriculum["source"]
    parser_version = curriculum["curriculum"].get("parser_version", "")
    connection.execute(
        """
        INSERT OR IGNORE INTO source_documents (
            source_name,
            source_url,
            retrieved_at_utc,
            content_path,
            content_sha256,
            parser_version
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            source["source_name"],
            source["source_url"],
            source["retrieved_at_utc"],
            source["content_path"],
            source["content_sha256"],
            parser_version,
        ),
    )
    return int(
        connection.execute(
            """
            SELECT id FROM source_documents
            WHERE source_url = ? AND content_sha256 = ?
            """,
            (source["source_url"], source["content_sha256"]),
        ).fetchone()[0]
    )


def get_program_id(connection: sqlite3.Connection, abbr: str) -> int:
    row = connection.execute("SELECT id FROM programs WHERE abbr = ?", (abbr,)).fetchone()
    if not row:
        raise RuntimeError(f"Program {abbr} is not loaded. Run scripts/load_programs.py first.")
    return int(row[0])


def upsert_curriculum_version(
    connection: sqlite3.Connection,
    curriculum: dict[str, Any],
    program_id: int,
    source_document_id: int,
) -> int:
    payload = curriculum["curriculum"]
    connection.execute(
        """
        INSERT INTO curriculum_versions (
            program_id,
            version_label,
            is_latest,
            review_status,
            source_document_id
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(program_id, version_label) DO UPDATE SET
            is_latest = excluded.is_latest,
            review_status = excluded.review_status,
            source_document_id = excluded.source_document_id
        """,
        (
            program_id,
            payload["version_label"],
            1 if payload["is_latest"] else 0,
            payload["review_status"],
            source_document_id,
        ),
    )
    version_id = int(
        connection.execute(
            """
            SELECT id FROM curriculum_versions
            WHERE program_id = ? AND version_label = ?
            """,
            (program_id, payload["version_label"]),
        ).fetchone()[0]
    )
    connection.execute(
        "DELETE FROM curriculum_requirements WHERE curriculum_version_id = ?",
        (version_id,),
    )
    return version_id


def upsert_course(connection: sqlite3.Connection, option: dict[str, str]) -> int:
    subject_code, course_number = parse_display_code(option["course_code"])
    numeric_code = option.get("numeric_code") or None
    connection.execute(
        """
        INSERT INTO courses (
            numeric_code,
            subject_code,
            course_number,
            display_code,
            title_en,
            level
        )
        VALUES (?, ?, ?, ?, ?, 'undergraduate')
        ON CONFLICT(display_code) DO UPDATE SET
            numeric_code = COALESCE(excluded.numeric_code, courses.numeric_code),
            title_en = COALESCE(NULLIF(excluded.title_en, ''), courses.title_en),
            level = excluded.level
        """,
        (
            numeric_code,
            subject_code,
            course_number,
            option["course_code"],
            option.get("course_title", ""),
        ),
    )
    return int(
        connection.execute(
            "SELECT id FROM courses WHERE display_code = ?",
            (option["course_code"],),
        ).fetchone()[0]
    )


def insert_requirements(
    connection: sqlite3.Connection,
    curriculum: dict[str, Any],
    curriculum_version_id: int,
    source_document_id: int,
) -> None:
    for sort_order, requirement in enumerate(curriculum["requirements"], start=1):
        connection.execute(
            """
            INSERT INTO curriculum_requirements (
                curriculum_version_id,
                requirement_type,
                label,
                recommended_year,
                recommended_term,
                course_count_min,
                credits_min,
                ects_min,
                sort_order,
                review_status,
                source_document_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                curriculum_version_id,
                requirement["requirement_type"],
                requirement["label"],
                requirement["year"],
                requirement["semester_label"],
                requirement["option_min_count"],
                number_or_none(requirement.get("metu_credit")),
                number_or_none(requirement.get("ects")),
                sort_order,
                curriculum["curriculum"]["review_status"],
                source_document_id,
            ),
        )
        requirement_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

        for option in requirement["options"]:
            course_id = upsert_course(connection, option)
            connection.execute(
                """
                INSERT INTO requirement_options (
                    requirement_id,
                    course_id,
                    option_group,
                    is_required_option,
                    source_document_id
                )
                VALUES (?, ?, ?, 1, ?)
                """,
                (
                    requirement_id,
                    course_id,
                    requirement["requirement_id"],
                    source_document_id,
                ),
            )


def number_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def load_curriculum_file(connection: sqlite3.Connection, path: Path) -> None:
    curriculum = json.loads(path.read_text(encoding="utf-8"))
    program_id = get_program_id(connection, curriculum["program"]["abbr"])
    source_document_id = upsert_source_document(connection, curriculum)
    version_id = upsert_curriculum_version(
        connection,
        curriculum,
        program_id,
        source_document_id,
    )
    insert_requirements(connection, curriculum, version_id, source_document_id)


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    curricula_dir = Path(args.curricula_dir)
    paths = sorted(curricula_dir.glob("*-latest.curriculum.json"))
    if not paths:
        print(f"No curriculum JSON files found in {curricula_dir}", file=sys.stderr)
        return 2

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for path in paths:
            load_curriculum_file(connection, path)

    print(f"Loaded {len(paths)} curriculum files into {db_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
