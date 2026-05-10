from __future__ import annotations

import argparse
import datetime as dt
import hashlib
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
    parser = argparse.ArgumentParser(description="Load prerequisite closure JSON into SQLite.")
    parser.add_argument(
        "--db",
        default="data/db/student_planner.sqlite",
        help="SQLite database path.",
    )
    parser.add_argument(
        "--closure",
        default="data/processed/prerequisites/engineering-latest-prerequisite-closure.json",
        help="Prerequisite closure JSON path.",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Delete existing prerequisite_edges before loading.",
    )
    return parser.parse_args()


def parse_display_code(display_code: str, numeric_code: str) -> tuple[str, int]:
    match = re.match(r"^([A-Z0-9]+)\s+(\d+)", display_code.strip())
    if match:
        return match.group(1), int(match.group(2))
    if numeric_code.isdigit() and len(numeric_code) > 4:
        return numeric_code[:-4], int(numeric_code[-4:])
    raise RuntimeError(f"Could not parse display course code: {display_code}")


def upsert_source_document(connection: sqlite3.Connection, path: Path) -> int:
    content = path.read_bytes()
    content_hash = hashlib.sha256(content).hexdigest()
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    source_url = f"local:{path.as_posix()}"
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
            "processed_prerequisite_closure",
            source_url,
            retrieved_at,
            str(path),
            content_hash,
            "build_prerequisite_closure_v1",
        ),
    )
    return int(
        connection.execute(
            """
            SELECT id FROM source_documents
            WHERE source_url = ? AND content_sha256 = ?
            """,
            (source_url, content_hash),
        ).fetchone()[0]
    )


def upsert_course(connection: sqlite3.Connection, node: dict[str, Any]) -> int:
    subject_code, course_number = parse_display_code(node["course_code"], node["id"])
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
        ON CONFLICT(numeric_code) DO UPDATE SET
            display_code = COALESCE(NULLIF(courses.display_code, ''), excluded.display_code),
            title_en = COALESCE(NULLIF(courses.title_en, ''), excluded.title_en),
            level = excluded.level
        """,
        (
            node["id"],
            subject_code,
            course_number,
            node["course_code"],
            node.get("course_name", ""),
        ),
    )
    return int(
        connection.execute(
            "SELECT id FROM courses WHERE numeric_code = ?",
            (node["id"],),
        ).fetchone()[0]
    )


def load_closure(connection: sqlite3.Connection, graph: dict[str, Any], source_document_id: int) -> None:
    node_id_to_db_id: dict[str, int] = {}
    for node in graph["nodes"]:
        node_id_to_db_id[node["id"]] = upsert_course(connection, node)

    for edge in graph["edges"]:
        prereq_id = node_id_to_db_id[edge["from"]]
        course_id = node_id_to_db_id[edge["to"]]
        connection.execute(
            """
            INSERT OR IGNORE INTO prerequisite_edges (
                prerequisite_course_id,
                course_id,
                set_no,
                min_grade,
                edge_type,
                position,
                source_document_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prereq_id,
                course_id,
                edge["set_no"],
                edge["min_grade"],
                edge["type"],
                edge["position"],
                source_document_id,
            ),
        )


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    closure_path = Path(args.closure)
    graph = json.loads(closure_path.read_text(encoding="utf-8"))

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        source_document_id = upsert_source_document(connection, closure_path)
        if args.clear_existing:
            connection.execute("DELETE FROM prerequisite_edges")
        load_closure(connection, graph, source_document_id)

    print(
        f"Loaded {graph['metadata']['edge_count']} prerequisite edges "
        f"from {closure_path} into {db_path.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
