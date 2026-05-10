from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = "data/db/student_planner.sqlite"
DEFAULT_CORRECTIONS_DIR = "data/manual/corrections"
DEFAULT_RAW_ROOT = "data/raw"
PARSER_VERSION = "manual_corrections_v1"
APPLICABLE_REVIEW_STATUSES = {"reviewed", "corrected"}
VALID_REVIEW_STATUSES = {"needs_review", "reviewed", "corrected", "deprecated"}
ALLOWED_COURSE_OVERRIDE_FIELDS = {"title_en", "title_tr", "level"}


@dataclass
class ApplyStats:
    course_aliases_applied: int = 0
    course_overrides_applied: int = 0
    skipped: int = 0
    unsupported: int = 0
    validation_errors: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply reviewed manual corrections to SQLite.")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database path.")
    parser.add_argument(
        "--corrections-dir",
        default=DEFAULT_CORRECTIONS_DIR,
        help="Directory containing manual correction JSON files.",
    )
    parser.add_argument("--raw-root", default=DEFAULT_RAW_ROOT, help="Raw snapshot root.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report planned changes without modifying the database.",
    )
    parser.add_argument(
        "--include-needs-review",
        action="store_true",
        help="Apply entries marked needs_review. Not recommended except for debugging.",
    )
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing correction file: {relative(path)}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {relative(path)}: {exc}") from exc


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    ensure_course_alias_columns(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS manual_correction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correction_type TEXT NOT NULL,
            correction_key TEXT NOT NULL,
            action TEXT NOT NULL,
            review_status TEXT NOT NULL,
            applied_at_utc TEXT NOT NULL,
            source_document_id INTEGER REFERENCES source_documents(id),
            payload_json TEXT NOT NULL,
            notes TEXT,
            UNIQUE(correction_type, correction_key, action, source_document_id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_course_aliases_course ON course_aliases(course_id)"
    )


def ensure_course_alias_columns(connection: sqlite3.Connection) -> None:
    existing = {
        row[1]
        for row in connection.execute("PRAGMA table_info(course_aliases)").fetchall()
    }
    additions = {
        "relation_type": "TEXT NOT NULL DEFAULT 'manual_alias'",
        "review_status": "TEXT NOT NULL DEFAULT 'reviewed'",
        "notes": "TEXT",
    }
    for column, definition in additions.items():
        if column not in existing:
            connection.execute(f"ALTER TABLE course_aliases ADD COLUMN {column} {definition}")


def source_document_id_for_file(
    connection: sqlite3.Connection,
    correction_path: Path,
    raw_root: Path,
    dry_run: bool,
) -> int | None:
    content = correction_path.read_bytes()
    content_hash = hashlib.sha256(content).hexdigest()
    source_url = f"local:{relative(correction_path)}"

    row = connection.execute(
        """
        SELECT id FROM source_documents
        WHERE source_url = ? AND content_sha256 = ?
        """,
        (source_url, content_hash),
    ).fetchone()
    if row:
        return int(row[0])

    if dry_run:
        return None

    now = dt.datetime.now(dt.timezone.utc)
    snapshot_dir = raw_root / "manual_corrections" / now.strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / correction_path.name
    shutil.copyfile(correction_path, snapshot_path)

    connection.execute(
        """
        INSERT INTO source_documents (
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
            "manual_corrections",
            source_url,
            now.isoformat(timespec="seconds"),
            str(snapshot_path.relative_to(PROJECT_ROOT)),
            content_hash,
            PARSER_VERSION,
        ),
    )
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def course_id_by_identifier(connection: sqlite3.Connection, item: dict[str, Any], prefix: str) -> int:
    numeric_code = item.get(f"{prefix}_numeric_code")
    display_code = item.get(f"{prefix}_display_code")
    if numeric_code:
        row = connection.execute(
            "SELECT id FROM courses WHERE numeric_code = ?",
            (numeric_code,),
        ).fetchone()
        if row:
            return int(row[0])
        raise RuntimeError(f"Course not found by numeric_code={numeric_code}")
    if display_code:
        row = connection.execute(
            "SELECT id FROM courses WHERE display_code = ?",
            (display_code,),
        ).fetchone()
        if row:
            return int(row[0])
        raise RuntimeError(f"Course not found by display_code={display_code}")
    raise RuntimeError(f"Missing {prefix}_numeric_code or {prefix}_display_code")


def course_id_by_match(connection: sqlite3.Connection, match: dict[str, str]) -> int:
    numeric_code = match.get("numeric_code")
    display_code = match.get("display_code")
    if numeric_code:
        row = connection.execute(
            "SELECT id FROM courses WHERE numeric_code = ?",
            (numeric_code,),
        ).fetchone()
        if row:
            return int(row[0])
        raise RuntimeError(f"Course not found by numeric_code={numeric_code}")
    if display_code:
        row = connection.execute(
            "SELECT id FROM courses WHERE display_code = ?",
            (display_code,),
        ).fetchone()
        if row:
            return int(row[0])
        raise RuntimeError(f"Course not found by display_code={display_code}")
    raise RuntimeError("Course override match must include numeric_code or display_code")


def should_apply(review_status: str, include_needs_review: bool) -> bool:
    if review_status in APPLICABLE_REVIEW_STATUSES:
        return True
    return include_needs_review and review_status == "needs_review"


def validate_review_status(item: dict[str, Any], context: str) -> str:
    review_status = item.get("review_status", "needs_review")
    if review_status not in VALID_REVIEW_STATUSES:
        raise RuntimeError(
            f"{context} has invalid review_status={review_status!r}. "
            f"Expected one of {sorted(VALID_REVIEW_STATUSES)}"
        )
    return review_status


def log_correction(
    connection: sqlite3.Connection,
    correction_type: str,
    correction_key: str,
    action: str,
    review_status: str,
    source_document_id: int | None,
    payload: dict[str, Any],
    notes: str,
) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO manual_correction_log (
            correction_type,
            correction_key,
            action,
            review_status,
            applied_at_utc,
            source_document_id,
            payload_json,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            correction_type,
            correction_key,
            action,
            review_status,
            dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            source_document_id,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            notes,
        ),
    )


def apply_course_aliases(
    connection: sqlite3.Connection,
    path: Path,
    raw_root: Path,
    stats: ApplyStats,
    dry_run: bool,
    include_needs_review: bool,
) -> None:
    payload = load_json(path)
    aliases = payload.get("aliases")
    if not isinstance(aliases, list):
        raise RuntimeError(f"{relative(path)} must contain an aliases list.")

    source_document_id = source_document_id_for_file(connection, path, raw_root, dry_run)
    for index, item in enumerate(aliases, start=1):
        context = f"{relative(path)} aliases[{index}]"
        if not isinstance(item, dict):
            raise RuntimeError(f"{context} must be an object.")
        review_status = validate_review_status(item, context)
        if not should_apply(review_status, include_needs_review):
            stats.skipped += 1
            continue

        canonical_course_id = course_id_by_identifier(connection, item, "canonical")
        relation_type = item.get("relation_type", "manual_alias")
        notes = item.get("notes", "")
        alias_values = [
            item.get("alias_display_code"),
            item.get("alias_numeric_code"),
            item.get("alias"),
        ]
        aliases_to_insert = sorted({value.strip() for value in alias_values if isinstance(value, str) and value.strip()})
        if not aliases_to_insert:
            raise RuntimeError(f"{context} must include alias_display_code, alias_numeric_code, or alias.")

        for alias in aliases_to_insert:
            if not dry_run:
                connection.execute(
                    """
                    INSERT INTO course_aliases (
                        course_id,
                        alias,
                        relation_type,
                        review_status,
                        notes,
                        source_document_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(alias) DO UPDATE SET
                        course_id = excluded.course_id,
                        relation_type = excluded.relation_type,
                        review_status = excluded.review_status,
                        notes = excluded.notes,
                        source_document_id = excluded.source_document_id
                    """,
                    (
                        canonical_course_id,
                        alias,
                        relation_type,
                        review_status,
                        notes,
                        source_document_id,
                    ),
                )
                log_correction(
                    connection,
                    "course_alias",
                    alias,
                    "upsert_alias",
                    review_status,
                    source_document_id,
                    item,
                    notes,
                )
            stats.course_aliases_applied += 1


def apply_course_overrides(
    connection: sqlite3.Connection,
    path: Path,
    raw_root: Path,
    stats: ApplyStats,
    dry_run: bool,
    include_needs_review: bool,
) -> None:
    payload = load_json(path)
    overrides = payload.get("overrides")
    if not isinstance(overrides, list):
        raise RuntimeError(f"{relative(path)} must contain an overrides list.")

    source_document_id = source_document_id_for_file(connection, path, raw_root, dry_run)
    for index, item in enumerate(overrides, start=1):
        context = f"{relative(path)} overrides[{index}]"
        if not isinstance(item, dict):
            raise RuntimeError(f"{context} must be an object.")
        review_status = validate_review_status(item, context)
        if not should_apply(review_status, include_needs_review):
            stats.skipped += 1
            continue

        match = item.get("match")
        fields = item.get("fields")
        if not isinstance(match, dict):
            raise RuntimeError(f"{context} must include a match object.")
        if not isinstance(fields, dict) or not fields:
            raise RuntimeError(f"{context} must include a non-empty fields object.")
        unknown_fields = sorted(set(fields).difference(ALLOWED_COURSE_OVERRIDE_FIELDS))
        if unknown_fields:
            raise RuntimeError(
                f"{context} uses unsupported course override fields: {', '.join(unknown_fields)}"
            )

        course_id = course_id_by_match(connection, match)
        notes = item.get("notes", "")
        if not dry_run:
            assignments = ", ".join(f"{field_name} = ?" for field_name in sorted(fields))
            values = [fields[field_name] for field_name in sorted(fields)]
            connection.execute(
                f"UPDATE courses SET {assignments} WHERE id = ?",
                (*values, course_id),
            )
            correction_key = match.get("numeric_code") or match.get("display_code") or str(course_id)
            log_correction(
                connection,
                "course_override",
                correction_key,
                "update_course_fields",
                review_status,
                source_document_id,
                item,
                notes,
            )
        stats.course_overrides_applied += 1


def validate_reserved_file(path: Path, key: str, stats: ApplyStats) -> None:
    payload = load_json(path)
    entries = payload.get(key)
    if not isinstance(entries, list):
        raise RuntimeError(f"{relative(path)} must contain a {key} list.")
    if entries:
        stats.unsupported += len(entries)
        raise RuntimeError(
            f"{relative(path)} contains entries, but this correction type is reserved "
            "and is not applied by this script version."
        )


def apply_all(args: argparse.Namespace) -> ApplyStats:
    db_path = project_path(args.db)
    corrections_dir = project_path(args.corrections_dir)
    raw_root = project_path(args.raw_root)
    stats = ApplyStats()

    expected_files = {
        "course_aliases": corrections_dir / "course_aliases.json",
        "course_overrides": corrections_dir / "course_overrides.json",
        "prerequisite_overrides": corrections_dir / "prerequisite_overrides.json",
        "curriculum_overrides": corrections_dir / "curriculum_overrides.json",
    }

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        ensure_schema(connection)
        try:
            apply_course_aliases(
                connection,
                expected_files["course_aliases"],
                raw_root,
                stats,
                args.dry_run,
                args.include_needs_review,
            )
            apply_course_overrides(
                connection,
                expected_files["course_overrides"],
                raw_root,
                stats,
                args.dry_run,
                args.include_needs_review,
            )
            validate_reserved_file(expected_files["prerequisite_overrides"], "overrides", stats)
            validate_reserved_file(expected_files["curriculum_overrides"], "overrides", stats)
        except Exception:
            connection.rollback()
            raise

        if args.dry_run:
            connection.rollback()
        else:
            connection.commit()

    return stats


def main() -> int:
    args = parse_args()
    try:
        stats = apply_all(args)
    except Exception as exc:
        print(f"Manual correction application failed: {exc}", file=sys.stderr)
        return 1

    mode = "dry-run" if args.dry_run else "applied"
    print(f"Manual corrections {mode}.")
    print(f"Course aliases applied: {stats.course_aliases_applied}")
    print(f"Course overrides applied: {stats.course_overrides_applied}")
    print(f"Skipped entries: {stats.skipped}")
    print(f"Unsupported entries: {stats.unsupported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
