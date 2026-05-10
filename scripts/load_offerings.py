from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from contextlib import closing
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load processed SAIS offerings into SQLite.")
    parser.add_argument(
        "--db",
        default="data/db/student_planner.sqlite",
        help="SQLite database path.",
    )
    parser.add_argument(
        "--offerings-dir",
        default="data/processed/offerings",
        help="Directory containing *.offerings.json files.",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Delete all existing offerings before loading.",
    )
    parser.add_argument(
        "--prune-orphan-non-undergraduate-courses",
        action="store_true",
        help=(
            "Delete non-undergraduate courses that are not referenced by offerings, "
            "curriculum, prerequisites, or student records."
        ),
    )
    return parser.parse_args()


def offering_json_paths(offerings_dir: Path) -> list[Path]:
    return sorted(offerings_dir.glob("*/*.offerings.json"))


def upsert_source_document(connection: sqlite3.Connection, payload: dict[str, Any], path: Path) -> int:
    source = payload["source"]
    content_sha256 = source.get("content_sha256") or hashlib.sha256(path.read_bytes()).hexdigest()
    parser_version = source.get("parser_version", "metu_sais_offerings_v1")
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
            source.get("source_name", "METU SAIS Course Details"),
            source.get("source_url", f"local:{path.as_posix()}"),
            source["retrieved_at_utc"],
            source.get("content_path", str(path)),
            content_sha256,
            parser_version,
        ),
    )
    return int(
        connection.execute(
            """
            SELECT id FROM source_documents
            WHERE source_url = ? AND content_sha256 = ?
            """,
            (source.get("source_url", f"local:{path.as_posix()}"), content_sha256),
        ).fetchone()[0]
    )


def get_program_id(connection: sqlite3.Connection, program_abbr: str) -> int | None:
    row = connection.execute(
        "SELECT id FROM programs WHERE abbr = ?",
        (program_abbr.upper(),),
    ).fetchone()
    return int(row[0]) if row else None


def upsert_course(connection: sqlite3.Connection, offering: dict[str, Any]) -> int:
    numeric_code = clean_optional_text(offering.get("numeric_code"))
    display_code = clean_text(offering.get("display_code"), "display_code")
    subject_code, course_number = parse_course_identity(display_code, numeric_code)
    existing = find_existing_course(connection, numeric_code, display_code)

    if existing is not None:
        connection.execute(
            """
            UPDATE courses
            SET numeric_code = COALESCE(numeric_code, ?),
                title_en = COALESCE(NULLIF(?, ''), title_en),
                level = ?
            WHERE id = ?
            """,
            (
                numeric_code,
                clean_optional_text(offering.get("course_name")) or "",
                infer_level(course_number, offering.get("level")),
                existing,
            ),
        )
        return existing

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
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            numeric_code,
            subject_code,
            course_number,
            display_code,
            clean_optional_text(offering.get("course_name")) or "",
            infer_level(course_number, offering.get("level")),
        ),
    )
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def find_existing_course(
    connection: sqlite3.Connection,
    numeric_code: str | None,
    display_code: str,
) -> int | None:
    if numeric_code:
        row = connection.execute(
            "SELECT id FROM courses WHERE numeric_code = ?",
            (numeric_code,),
        ).fetchone()
        if row:
            return int(row[0])

    row = connection.execute(
        "SELECT id FROM courses WHERE display_code = ?",
        (display_code,),
    ).fetchone()
    return int(row[0]) if row else None


def parse_course_identity(display_code: str, numeric_code: str | None) -> tuple[str, int]:
    match = re.match(r"^([A-Z0-9]+)\s+(\d+[A-Z]?)$", display_code.strip().upper())
    if match:
        return match.group(1), int(re.match(r"\d+", match.group(2)).group(0))  # type: ignore[union-attr]
    if numeric_code and numeric_code.isdigit() and len(numeric_code) > 4:
        return numeric_code[:-4], int(numeric_code[-4:])
    raise RuntimeError(f"Could not parse course identity from {display_code!r}.")


def infer_level(course_number: int, sais_level: object) -> str:
    level_text = normalize_ascii(str(sais_level or "").lower())
    if "undergraduate" in level_text:
        return "undergraduate"
    if "lisansustu" in level_text or "graduate" in level_text:
        return "graduate"
    if "lisans" in level_text:
        return "undergraduate"
    if course_number >= 500:
        return "graduate"
    return "undergraduate"


def normalize_ascii(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def insert_offering(
    connection: sqlite3.Connection,
    course_id: int,
    semester_no: str,
    department_program_id: int | None,
    source_document_id: int,
) -> None:
    if department_program_id is None:
        existing = connection.execute(
            """
            SELECT id
            FROM offerings
            WHERE course_id = ?
              AND semester_no = ?
              AND department_program_id IS NULL
            """,
            (course_id, semester_no),
        ).fetchone()
        if existing:
            connection.execute(
                "UPDATE offerings SET source_document_id = ? WHERE id = ?",
                (source_document_id, existing[0]),
            )
            return

    connection.execute(
        """
        INSERT INTO offerings (
            course_id,
            semester_no,
            department_program_id,
            source_document_id
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(course_id, semester_no, department_program_id) DO UPDATE SET
            source_document_id = excluded.source_document_id
        """,
        (course_id, semester_no, department_program_id, source_document_id),
    )


def load_offerings_file(connection: sqlite3.Connection, path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_document_id = upsert_source_document(connection, payload, path)
    program_abbr = payload["program"]["abbr"].upper()
    semester_no = payload["semester"]["semester_no"]
    department_program_id = get_program_id(connection, program_abbr)
    loaded_count = 0

    for offering in payload.get("offerings", []):
        if not is_undergraduate_offering(offering):
            continue
        course_id = upsert_course(connection, offering)
        insert_offering(
            connection=connection,
            course_id=course_id,
            semester_no=semester_no,
            department_program_id=department_program_id,
            source_document_id=source_document_id,
        )
        loaded_count += 1

    return loaded_count


def prune_orphan_non_undergraduate_courses(connection: sqlite3.Connection) -> int:
    before = query_course_count(connection)
    connection.execute(
        """
        DELETE FROM courses
        WHERE level != 'undergraduate'
          AND id NOT IN (SELECT course_id FROM offerings)
          AND id NOT IN (SELECT course_id FROM requirement_options WHERE course_id IS NOT NULL)
          AND id NOT IN (SELECT prerequisite_course_id FROM prerequisite_edges)
          AND id NOT IN (SELECT course_id FROM prerequisite_edges)
          AND id NOT IN (SELECT course_id FROM student_completed_courses)
        """
    )
    return before - query_course_count(connection)


def query_course_count(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT COUNT(*) FROM courses").fetchone()[0])


def is_undergraduate_offering(offering: dict[str, Any]) -> bool:
    _subject_code, course_number = parse_course_identity(
        clean_text(offering.get("display_code"), "display_code"),
        clean_optional_text(offering.get("numeric_code")),
    )
    return infer_level(course_number, offering.get("level")) == "undergraduate"


def clean_text(value: object, field_name: str) -> str:
    if value is None:
        raise RuntimeError(f"{field_name} is required.")
    cleaned = str(value).strip()
    if not cleaned:
        raise RuntimeError(f"{field_name} cannot be empty.")
    return cleaned


def clean_optional_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    paths = offering_json_paths(Path(args.offerings_dir))
    if not paths:
        print(f"No offering JSON files found in {args.offerings_dir}", file=sys.stderr)
        return 2

    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        if args.clear_existing:
            connection.execute("DELETE FROM offerings")

        total_rows = 0
        for path in paths:
            total_rows += load_offerings_file(connection, path)
        pruned_count = (
            prune_orphan_non_undergraduate_courses(connection)
            if args.prune_orphan_non_undergraduate_courses
            else 0
        )
        connection.commit()

    print(f"Loaded {total_rows} offering rows from {len(paths)} files into {db_path.resolve()}")
    if pruned_count:
        print(f"Pruned {pruned_count} orphan non-undergraduate course rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
