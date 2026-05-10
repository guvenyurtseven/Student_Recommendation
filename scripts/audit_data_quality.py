from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = "data/db/student_planner.sqlite"
DEFAULT_PROCESSED_ROOT = "data/processed"
DEFAULT_RAW_ROOT = "data/raw"
DEFAULT_REPORT = "data/processed/reports/data_quality_report.md"
EXPECTED_ACTIVE_ENGINEERING_PROGRAM_COUNT = 13
MOJIBAKE_MARKERS = ("ý", "þ", "ð", "Ý", "Þ", "Ð", "Ã", "Ä", "Å")


@dataclass
class Finding:
    severity: str
    category: str
    message: str
    details: list[str] = field(default_factory=list)


@dataclass
class Audit:
    metrics: dict[str, Any] = field(default_factory=dict)
    fatal: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    info: list[Finding] = field(default_factory=list)

    def add(self, severity: str, category: str, message: str, details: list[str] | None = None) -> None:
        finding = Finding(severity, category, message, details or [])
        if severity == "fatal":
            self.fatal.append(finding)
        elif severity == "warning":
            self.warnings.append(finding)
        else:
            self.info.append(finding)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit processed METU Student Planner data and write a Markdown report."
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database path.")
    parser.add_argument(
        "--processed-root",
        default=DEFAULT_PROCESSED_ROOT,
        help="Processed data root.",
    )
    parser.add_argument("--raw-root", default=DEFAULT_RAW_ROOT, help="Raw data root.")
    parser.add_argument(
        "--report",
        default=DEFAULT_REPORT,
        help="Markdown report output path.",
    )
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def query_one(connection: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    return connection.execute(sql, params).fetchone()[0]


def query_rows(
    connection: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
) -> list[sqlite3.Row]:
    return list(connection.execute(sql, params).fetchall())


def read_json(path: Path, audit: Audit, category: str) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        audit.add("fatal", category, f"Missing file: {relative(path)}")
    except json.JSONDecodeError as exc:
        audit.add("fatal", category, f"Invalid JSON: {relative(path)}", [str(exc)])
    return None


def read_csv_rows(path: Path, audit: Audit, category: str) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            return list(csv.DictReader(csv_file))
    except FileNotFoundError:
        audit.add("fatal", category, f"Missing file: {relative(path)}")
    except csv.Error as exc:
        audit.add("fatal", category, f"Invalid CSV: {relative(path)}", [str(exc)])
    return []


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def audit_database(db_path: Path, audit: Audit) -> tuple[sqlite3.Connection | None, list[str]]:
    if not db_path.exists():
        audit.add("fatal", "database", f"SQLite database is missing: {relative(db_path)}")
        return None, []

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    integrity = query_one(connection, "PRAGMA integrity_check")
    audit.metrics["db_integrity_check"] = integrity
    if integrity != "ok":
        audit.add("fatal", "database", "SQLite integrity_check failed.", [str(integrity)])

    foreign_key_rows = query_rows(connection, "PRAGMA foreign_key_check")
    audit.metrics["db_foreign_key_errors"] = len(foreign_key_rows)
    if foreign_key_rows:
        audit.add(
            "fatal",
            "database",
            f"Foreign key check found {len(foreign_key_rows)} issue(s).",
            [str(dict(row)) for row in foreign_key_rows[:20]],
        )

    table_names = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    table_counts = {
        table_name: query_one(connection, f"SELECT COUNT(*) FROM {table_name}")
        for table_name in table_names
    }
    audit.metrics["table_counts"] = table_counts

    active_programs = [
        row["abbr"]
        for row in query_rows(
            connection,
            "SELECT abbr FROM programs WHERE is_active_undergraduate = 1 ORDER BY abbr",
        )
    ]
    audit.metrics["active_programs"] = active_programs
    if len(active_programs) != EXPECTED_ACTIVE_ENGINEERING_PROGRAM_COUNT:
        audit.add(
            "warning",
            "programs",
            "Unexpected active undergraduate program count.",
            [
                f"Expected {EXPECTED_ACTIVE_ENGINEERING_PROGRAM_COUNT}, found {len(active_programs)}.",
                f"Programs: {', '.join(active_programs)}",
            ],
        )

    program_name_issues = [
        f"{row['abbr']}: {row['name_tr']}"
        for row in query_rows(connection, "SELECT abbr, name_tr FROM programs ORDER BY abbr")
        if row["name_tr"] and any(marker in row["name_tr"] for marker in MOJIBAKE_MARKERS)
    ]
    audit.metrics["program_name_mojibake_count"] = len(program_name_issues)
    if program_name_issues:
        audit.add(
            "warning",
            "programs",
            "Turkish program names appear to contain mojibake.",
            program_name_issues,
        )

    review_summary = {}
    for table in ("curriculum_versions", "curriculum_requirements"):
        rows = query_rows(
            connection,
            f"SELECT review_status, COUNT(*) AS count FROM {table} GROUP BY review_status ORDER BY review_status",
        )
        review_summary[table] = {row["review_status"]: row["count"] for row in rows}
        if review_summary[table].get("scraped", 0):
            audit.add(
                "warning",
                "review",
                f"{table} still contains automatically scraped records.",
                [f"scraped: {review_summary[table]['scraped']}"],
            )
    audit.metrics["review_summary"] = review_summary

    audit_course_quality(connection, audit)
    audit_curriculum_quality(connection, audit)
    audit_prerequisite_quality(connection, audit)
    audit_sources(connection, audit)

    for table in ("offerings", "student_profiles", "student_completed_courses"):
        count = table_counts.get(table, 0)
        if count == 0:
            audit.add(
                "warning",
                table,
                f"{table} is empty.",
                ["This is expected before the corresponding product phase, but not ready for recommendations."],
            )

    return connection, active_programs


def audit_course_quality(connection: sqlite3.Connection, audit: Audit) -> None:
    checks = {
        "courses_with_null_numeric_code": "SELECT COUNT(*) FROM courses WHERE numeric_code IS NULL OR numeric_code = ''",
        "courses_with_empty_title": "SELECT COUNT(*) FROM courses WHERE title_en IS NULL OR trim(title_en) = ''",
        "courses_level_not_undergraduate": "SELECT COUNT(*) FROM courses WHERE level <> 'undergraduate'",
        "display_code_without_space": "SELECT COUNT(*) FROM courses WHERE display_code NOT LIKE '% %'",
        "numeric_subject_code_courses": "SELECT COUNT(*) FROM courses WHERE subject_code GLOB '[0-9]*'",
        "course_number_5xx_999": "SELECT COUNT(*) FROM courses WHERE course_number BETWEEN 500 AND 999",
        "course_number_over_999": "SELECT COUNT(*) FROM courses WHERE course_number > 999",
    }
    values = {name: query_one(connection, sql) for name, sql in checks.items()}
    audit.metrics["course_quality"] = values

    if values["courses_with_null_numeric_code"]:
        audit.add("fatal", "courses", "Some courses are missing numeric_code.")
    if values["courses_level_not_undergraduate"]:
        audit.add("warning", "courses", "Some courses are not marked undergraduate.")
    if values["display_code_without_space"]:
        audit.add("warning", "courses", "Some display_code values do not contain a subject/number space.")
    if values["courses_with_empty_title"]:
        rows = query_rows(
            connection,
            """
            SELECT display_code, numeric_code
            FROM courses
            WHERE title_en IS NULL OR trim(title_en) = ''
            ORDER BY display_code
            """,
        )
        audit.add(
            "warning",
            "courses",
            "Some courses have empty English titles.",
            [f"{row['display_code']} ({row['numeric_code']})" for row in rows],
        )
    if values["numeric_subject_code_courses"]:
        rows = query_rows(
            connection,
            """
            SELECT display_code, numeric_code, title_en
            FROM courses
            WHERE subject_code GLOB '[0-9]*'
            ORDER BY subject_code, course_number
            LIMIT 80
            """,
        )
        audit.add(
            "warning",
            "course_identity",
            "Some courses have numeric subject display codes.",
            [f"{row['display_code']} ({row['numeric_code']}): {row['title_en']}" for row in rows],
        )
    if values["course_number_5xx_999"]:
        audit.add("warning", "courses", "5xx-999 course numbers are present in undergraduate course table.")
    if values["course_number_over_999"]:
        rows = query_rows(
            connection,
            """
            SELECT display_code, numeric_code, title_en
            FROM courses
            WHERE course_number > 999
            ORDER BY display_code
            """,
        )
        audit.add(
            "info",
            "courses",
            "Course numbers above 999 are present. These may be valid undergraduate service courses.",
            [f"{row['display_code']} ({row['numeric_code']}): {row['title_en']}" for row in rows],
        )


def audit_curriculum_quality(connection: sqlite3.Connection, audit: Audit) -> None:
    rows = query_rows(
        connection,
        """
        SELECT p.abbr,
               cv.version_label,
               cv.review_status,
               COUNT(DISTINCT cr.id) AS requirement_count,
               COUNT(ro.id) AS option_count,
               SUM(CASE WHEN ro.course_id IS NULL THEN 1 ELSE 0 END) AS null_course_options
        FROM curriculum_versions cv
        JOIN programs p ON p.id = cv.program_id
        LEFT JOIN curriculum_requirements cr ON cr.curriculum_version_id = cv.id
        LEFT JOIN requirement_options ro ON ro.requirement_id = cr.id
        GROUP BY p.abbr, cv.id
        ORDER BY p.abbr
        """,
    )
    audit.metrics["curricula_by_program"] = [dict(row) for row in rows]

    duplicate_rows = query_rows(
        connection,
        """
        SELECT p.abbr, c.display_code, COUNT(*) AS duplicate_count
        FROM curriculum_versions cv
        JOIN programs p ON p.id = cv.program_id
        JOIN curriculum_requirements cr ON cr.curriculum_version_id = cv.id
        JOIN requirement_options ro ON ro.requirement_id = cr.id
        JOIN courses c ON c.id = ro.course_id
        GROUP BY p.abbr, c.id
        HAVING COUNT(*) > 1
        ORDER BY p.abbr, c.display_code
        """,
    )
    audit.metrics["duplicate_curriculum_courses_within_program"] = len(duplicate_rows)
    if duplicate_rows:
        audit.add(
            "warning",
            "curricula",
            "Some courses appear more than once in a program curriculum.",
            [f"{row['abbr']} {row['display_code']} x{row['duplicate_count']}" for row in duplicate_rows],
        )

    requirement_type_rows = query_rows(
        connection,
        """
        SELECT requirement_type, COUNT(*) AS count
        FROM curriculum_requirements
        GROUP BY requirement_type
        ORDER BY count DESC, requirement_type
        """,
    )
    audit.metrics["requirement_type_counts"] = {
        row["requirement_type"]: row["count"] for row in requirement_type_rows
    }


def audit_prerequisite_quality(connection: sqlite3.Connection, audit: Audit) -> None:
    values = {
        "edge_count": query_one(connection, "SELECT COUNT(*) FROM prerequisite_edges"),
        "self_edges": query_one(
            connection,
            "SELECT COUNT(*) FROM prerequisite_edges WHERE prerequisite_course_id = course_id",
        ),
        "edges_missing_set_no": query_one(
            connection,
            "SELECT COUNT(*) FROM prerequisite_edges WHERE set_no IS NULL OR trim(set_no) = ''",
        ),
        "edges_missing_min_grade": query_one(
            connection,
            "SELECT COUNT(*) FROM prerequisite_edges WHERE min_grade IS NULL OR trim(min_grade) = ''",
        ),
        "edges_missing_type": query_one(
            connection,
            "SELECT COUNT(*) FROM prerequisite_edges WHERE edge_type IS NULL OR trim(edge_type) = ''",
        ),
        "edges_missing_position": query_one(
            connection,
            "SELECT COUNT(*) FROM prerequisite_edges WHERE position IS NULL OR trim(position) = ''",
        ),
    }
    audit.metrics["prerequisite_quality"] = values

    if values["self_edges"]:
        audit.add("fatal", "prerequisites", "Prerequisite graph contains self edges.")
    missing_field_count = sum(
        values[key]
        for key in (
            "edges_missing_set_no",
            "edges_missing_min_grade",
            "edges_missing_type",
            "edges_missing_position",
        )
    )
    if missing_field_count:
        audit.add("fatal", "prerequisites", "Some prerequisite edges have missing required fields.")

    ncc_edges = query_one(
        connection,
        "SELECT COUNT(*) FROM prerequisite_edges WHERE edge_type LIKE '%NCC%'",
    )
    audit.metrics["ncc_edge_count"] = ncc_edges
    if ncc_edges:
        rows = query_rows(
            connection,
            """
            SELECT prereq.display_code AS prereq,
                   course.display_code AS course,
                   pe.set_no,
                   pe.min_grade
            FROM prerequisite_edges pe
            JOIN courses prereq ON prereq.id = pe.prerequisite_course_id
            JOIN courses course ON course.id = pe.course_id
            WHERE pe.edge_type LIKE '%NCC%'
            ORDER BY course.display_code, pe.set_no, prereq.display_code
            LIMIT 80
            """,
        )
        audit.add(
            "warning",
            "course_identity",
            "NCC prerequisite alternatives are present and need product semantics.",
            [
                f"{row['prereq']} -> {row['course']} (set {row['set_no']}, min {row['min_grade']})"
                for row in rows
            ],
        )

    is_dag, node_count, ordered_count = db_graph_is_dag(connection)
    audit.metrics["db_prerequisite_graph_is_dag"] = is_dag
    audit.metrics["db_prerequisite_graph_node_count"] = node_count
    audit.metrics["db_prerequisite_graph_topological_count"] = ordered_count
    if not is_dag:
        audit.add("fatal", "prerequisites", "DB prerequisite graph contains a cycle.")


def db_graph_is_dag(connection: sqlite3.Connection) -> tuple[bool, int, int]:
    node_ids = {row[0] for row in connection.execute("SELECT id FROM courses")}
    adjacency: dict[int, list[int]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in node_ids}
    for row in connection.execute("SELECT prerequisite_course_id, course_id FROM prerequisite_edges"):
        source, target = int(row[0]), int(row[1])
        adjacency[source].append(target)
        indegree.setdefault(source, 0)
        indegree[target] = indegree.get(target, 0) + 1

    queue: deque[int] = deque(sorted([node_id for node_id, degree in indegree.items() if degree == 0]))
    ordered: list[int] = []
    while queue:
        node_id = queue.popleft()
        ordered.append(node_id)
        for target in sorted(adjacency.get(node_id, [])):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    return len(ordered) == len(indegree), len(indegree), len(ordered)


def audit_sources(connection: sqlite3.Connection, audit: Audit) -> None:
    source_rows = query_rows(
        connection,
        """
        SELECT id, source_name, source_url, content_path, content_sha256
        FROM source_documents
        ORDER BY id
        """,
    )
    missing: list[str] = []
    mismatched: list[str] = []
    for row in source_rows:
        if not row["content_path"] or not row["content_sha256"]:
            continue
        content_path = project_path(row["content_path"])
        if not content_path.exists():
            missing.append(f"{row['id']}: {relative(content_path)}")
            continue
        digest = hashlib.sha256(content_path.read_bytes()).hexdigest()
        if digest != row["content_sha256"]:
            mismatched.append(f"{row['id']}: {relative(content_path)}")

    audit.metrics["source_document_count"] = len(source_rows)
    audit.metrics["source_document_missing_count"] = len(missing)
    audit.metrics["source_document_hash_mismatch_count"] = len(mismatched)
    if missing:
        audit.add("fatal", "sources", "Some source document content paths are missing.", missing)
    if mismatched:
        audit.add("fatal", "sources", "Some source document hashes do not match file contents.", mismatched)


def audit_processed_files(
    processed_root: Path,
    raw_root: Path,
    active_programs: list[str],
    connection: sqlite3.Connection | None,
    audit: Audit,
) -> None:
    curricula_dir = processed_root / "curricula"
    prerequisites_dir = processed_root / "prerequisites"

    audit_curriculum_files(curricula_dir, active_programs, connection, audit)
    audit_prerequisite_files(prerequisites_dir, active_programs, connection, audit)
    audit_raw_catalog(raw_root / "catalog", active_programs, audit)


def audit_curriculum_files(
    curricula_dir: Path,
    active_programs: list[str],
    connection: sqlite3.Connection | None,
    audit: Audit,
) -> None:
    paths = sorted(curricula_dir.glob("*-latest.curriculum.json"))
    found_programs = sorted(path.name.split("-", 1)[0] for path in paths)
    missing = sorted(set(active_programs).difference(found_programs))
    extra = sorted(set(found_programs).difference(active_programs))
    audit.metrics["curriculum_json_count"] = len(paths)
    audit.metrics["curriculum_json_programs"] = found_programs
    if missing:
        audit.add("fatal", "curriculum_files", "Missing curriculum JSON files.", missing)
    if extra:
        audit.add("warning", "curriculum_files", "Unexpected curriculum JSON files are present.", extra)

    json_requirement_total = 0
    json_option_total = 0
    json_placeholder_total = 0
    missing_numeric_options: list[str] = []
    per_program: dict[str, dict[str, int]] = {}
    for path in paths:
        payload = read_json(path, audit, "curriculum_files")
        if not payload:
            continue
        program = payload.get("program", {}).get("abbr", path.name.split("-", 1)[0])
        requirements = payload.get("requirements", [])
        option_count = sum(len(requirement.get("options", [])) for requirement in requirements)
        placeholder_count = sum(1 for requirement in requirements if not requirement.get("options", []))
        unique_course_count = len(
            {
                option.get("course_code")
                for requirement in requirements
                for option in requirement.get("options", [])
                if option.get("course_code")
            }
        )
        json_requirement_total += len(requirements)
        json_option_total += option_count
        json_placeholder_total += placeholder_count
        per_program[program] = {
            "requirements": len(requirements),
            "options": option_count,
            "placeholders": placeholder_count,
            "unique_courses": unique_course_count,
        }
        for requirement in requirements:
            for option in requirement.get("options", []):
                if option.get("course_code") and not option.get("numeric_code"):
                    missing_numeric_options.append(f"{program} {option.get('course_code')}")

    audit.metrics["curriculum_json_requirement_total"] = json_requirement_total
    audit.metrics["curriculum_json_option_total"] = json_option_total
    audit.metrics["curriculum_json_placeholder_total"] = json_placeholder_total
    audit.metrics["curriculum_json_per_program"] = per_program

    if missing_numeric_options:
        audit.add(
            "fatal",
            "curriculum_files",
            "Some curriculum course options are missing numeric_code.",
            missing_numeric_options,
        )

    combined_path = curricula_dir / "all_engineering_latest_curriculum_requirements.csv"
    combined_rows = read_csv_rows(combined_path, audit, "curriculum_files")
    audit.metrics["combined_curriculum_csv_rows"] = len(combined_rows)
    audit.metrics["combined_curriculum_empty_course_rows"] = sum(
        1 for row in combined_rows if not row.get("course_code")
    )
    missing_numeric_csv = [
        f"{row.get('program_abbr')} {row.get('course_code')}"
        for row in combined_rows
        if row.get("course_code") and not row.get("numeric_code")
    ]
    if missing_numeric_csv:
        audit.add(
            "fatal",
            "curriculum_files",
            "Combined curriculum CSV has course rows with missing numeric_code.",
            missing_numeric_csv,
        )

    summary_path = curricula_dir / "curriculum_scrape_summary.csv"
    summary_rows = read_csv_rows(summary_path, audit, "curriculum_files")
    audit.metrics["curriculum_summary_rows"] = len(summary_rows)
    for row in summary_rows:
        program = row.get("program_abbr", "")
        actual = per_program.get(program)
        if not actual:
            continue
        expected_values = {
            "requirement_count": actual["requirements"],
            "course_option_count": actual["options"],
            "unique_course_count": actual["unique_courses"],
            "placeholder_requirement_count": actual["placeholders"],
        }
        for field_name, expected in expected_values.items():
            if str(expected) != row.get(field_name):
                audit.add(
                    "fatal",
                    "curriculum_files",
                    "Curriculum summary CSV does not match JSON payload.",
                    [f"{program} {field_name}: summary={row.get(field_name)} json={expected}"],
                )

    if connection is not None:
        db_requirement_count = query_one(connection, "SELECT COUNT(*) FROM curriculum_requirements")
        db_option_count = query_one(connection, "SELECT COUNT(*) FROM requirement_options")
        if db_requirement_count != json_requirement_total:
            audit.add(
                "fatal",
                "curriculum_db",
                "DB curriculum requirement count does not match processed JSON.",
                [f"db={db_requirement_count}, json={json_requirement_total}"],
            )
        if db_option_count != json_option_total:
            audit.add(
                "fatal",
                "curriculum_db",
                "DB requirement option count does not match processed JSON.",
                [f"db={db_option_count}, json={json_option_total}"],
            )


def audit_prerequisite_files(
    prerequisites_dir: Path,
    active_programs: list[str],
    connection: sqlite3.Connection | None,
    audit: Audit,
) -> None:
    engineering_path = prerequisites_dir / "engineering-latest-prerequisite-closure.json"
    engineering_graph = validate_prerequisite_graph(engineering_path, audit)
    if engineering_graph:
        metadata = engineering_graph.get("metadata", {})
        programs = metadata.get("programs", [])
        if sorted(programs) != sorted(active_programs):
            audit.add(
                "fatal",
                "prerequisite_files",
                "Engineering prerequisite closure does not cover all active programs.",
                [f"metadata={programs}", f"active={active_programs}"],
            )
        validate_prerequisite_csv_counts(engineering_path.with_suffix(""), engineering_graph, audit)
        unresolved = engineering_graph.get("unresolved", [])
        audit.metrics["engineering_prerequisite_unresolved_count"] = len(unresolved)
        if unresolved:
            audit.add(
                "warning",
                "prerequisites",
                "Engineering prerequisite closure has unresolved courses.",
                [
                    f"{row.get('course_code')} ({row.get('course_code_numeric')}): {row.get('reason')}"
                    for row in unresolved
                ],
            )
        if connection is not None:
            db_edges = query_one(connection, "SELECT COUNT(*) FROM prerequisite_edges")
            db_courses = query_one(connection, "SELECT COUNT(*) FROM courses")
            if db_edges != len(engineering_graph.get("edges", [])):
                audit.add(
                    "fatal",
                    "prerequisite_db",
                    "DB prerequisite edge count does not match engineering graph JSON.",
                    [f"db={db_edges}, json={len(engineering_graph.get('edges', []))}"],
                )
            if db_courses != len(engineering_graph.get("nodes", [])):
                audit.add(
                    "warning",
                    "prerequisite_db",
                    "DB course count does not match engineering graph node count.",
                    [f"db={db_courses}, json={len(engineering_graph.get('nodes', []))}"],
                )

    per_program_metrics = {}
    for program in active_programs:
        graph_path = prerequisites_dir / f"{program}-latest-prerequisite-closure.json"
        graph = validate_prerequisite_graph(graph_path, audit)
        if not graph:
            continue
        validate_prerequisite_csv_counts(graph_path.with_suffix(""), graph, audit)
        metadata = graph.get("metadata", {})
        per_program_metrics[program] = {
            "nodes": metadata.get("node_count", len(graph.get("nodes", []))),
            "edges": metadata.get("edge_count", len(graph.get("edges", []))),
            "unresolved": metadata.get("unresolved_count", len(graph.get("unresolved", []))),
            "is_dag": metadata.get("is_dag"),
        }
    audit.metrics["per_program_prerequisite_graphs"] = per_program_metrics

    summary_path = prerequisites_dir / "prerequisite_closure_summary.csv"
    summary_rows = read_csv_rows(summary_path, audit, "prerequisite_files")
    audit.metrics["prerequisite_summary_rows"] = len(summary_rows)
    if len(summary_rows) != len(active_programs):
        audit.add(
            "warning",
            "prerequisite_files",
            "Prerequisite closure summary row count differs from active program count.",
            [f"summary={len(summary_rows)}, active_programs={len(active_programs)}"],
        )
    for row in summary_rows:
        program = row.get("program", "")
        actual = per_program_metrics.get(program)
        if not actual:
            continue
        checks = {
            "node_count": actual["nodes"],
            "edge_count": actual["edges"],
            "unresolved_count": actual["unresolved"],
        }
        for field_name, expected in checks.items():
            if str(expected) != row.get(field_name):
                audit.add(
                    "fatal",
                    "prerequisite_files",
                    "Prerequisite summary CSV does not match JSON metadata.",
                    [f"{program} {field_name}: summary={row.get(field_name)} json={expected}"],
                )
        if str(actual["is_dag"]) != row.get("is_dag"):
            audit.add(
                "fatal",
                "prerequisite_files",
                "Prerequisite summary DAG flag does not match JSON metadata.",
                [f"{program}: summary={row.get('is_dag')} json={actual['is_dag']}"],
            )


def validate_prerequisite_graph(path: Path, audit: Audit) -> dict[str, Any] | None:
    graph = read_json(path, audit, "prerequisite_files")
    if graph is None:
        return None

    metadata = graph.get("metadata", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    unresolved = graph.get("unresolved", [])
    node_ids = {node.get("id") for node in nodes}

    if metadata.get("node_count") != len(nodes):
        audit.add(
            "fatal",
            "prerequisite_files",
            "Prerequisite graph metadata node_count does not match nodes length.",
            [f"{relative(path)}: metadata={metadata.get('node_count')} actual={len(nodes)}"],
        )
    if metadata.get("edge_count") != len(edges):
        audit.add(
            "fatal",
            "prerequisite_files",
            "Prerequisite graph metadata edge_count does not match edges length.",
            [f"{relative(path)}: metadata={metadata.get('edge_count')} actual={len(edges)}"],
        )
    if metadata.get("unresolved_count") != len(unresolved):
        audit.add(
            "fatal",
            "prerequisite_files",
            "Prerequisite graph metadata unresolved_count does not match unresolved length.",
            [f"{relative(path)}: metadata={metadata.get('unresolved_count')} actual={len(unresolved)}"],
        )

    missing_endpoints = [
        f"{edge.get('from_course_code')} -> {edge.get('to_course_code')}"
        for edge in edges
        if edge.get("from") not in node_ids or edge.get("to") not in node_ids
    ]
    if missing_endpoints:
        audit.add(
            "fatal",
            "prerequisite_files",
            "Prerequisite graph has edges with missing endpoint nodes.",
            [relative(path), *missing_endpoints[:40]],
        )

    duplicate_edge_count = len(edges) - len(
        {
            (edge.get("from"), edge.get("to"), edge.get("set_no"), edge.get("min_grade"))
            for edge in edges
        }
    )
    if duplicate_edge_count:
        audit.add(
            "fatal",
            "prerequisite_files",
            "Prerequisite graph has duplicate edge keys.",
            [f"{relative(path)} duplicate_edge_count={duplicate_edge_count}"],
        )

    if metadata.get("is_dag") is not True:
        audit.add("fatal", "prerequisite_files", "Prerequisite graph is not marked as DAG.", [relative(path)])

    topological_order = graph.get("topological_order", [])
    if len(topological_order) != len(node_ids):
        audit.add(
            "fatal",
            "prerequisite_files",
            "Topological order length does not match node count.",
            [f"{relative(path)} topo={len(topological_order)} nodes={len(node_ids)}"],
        )

    numeric_display_count = sum(
        1
        for node in nodes
        if str(node.get("course_code", "")).split(" ", 1)[0].isdigit()
    )
    if numeric_display_count:
        audit.add(
            "warning",
            "course_identity",
            "Prerequisite graph contains numeric display course codes.",
            [f"{relative(path)} numeric_display_nodes={numeric_display_count}"],
        )

    return graph


def validate_prerequisite_csv_counts(stem_path: Path, graph: dict[str, Any], audit: Audit) -> None:
    for suffix, key in (("nodes", "nodes"), ("edges", "edges"), ("unresolved", "unresolved")):
        csv_path = stem_path.parent / f"{stem_path.name}-{suffix}.csv"
        rows = read_csv_rows(csv_path, audit, "prerequisite_files")
        if len(rows) != len(graph.get(key, [])):
            audit.add(
                "fatal",
                "prerequisite_files",
                "Prerequisite CSV row count does not match JSON payload.",
                [f"{relative(csv_path)} csv={len(rows)} json={len(graph.get(key, []))}"],
            )


def audit_raw_catalog(catalog_root: Path, active_programs: list[str], audit: Audit) -> None:
    if not catalog_root.exists():
        audit.add("warning", "raw_catalog", f"Raw catalog directory is missing: {relative(catalog_root)}")
        return

    snapshot_counts = {}
    for program in active_programs:
        program_dir = catalog_root / program
        snapshots = sorted(path.name for path in program_dir.iterdir() if path.is_dir()) if program_dir.exists() else []
        snapshot_counts[program] = len(snapshots)
        if not snapshots:
            audit.add("warning", "raw_catalog", f"No raw catalog snapshots for {program}.")
    audit.metrics["raw_catalog_snapshot_counts"] = snapshot_counts

    multiple_snapshot_programs = [
        f"{program}: {count}"
        for program, count in snapshot_counts.items()
        if count > 1
    ]
    if multiple_snapshot_programs:
        audit.add(
            "info",
            "raw_catalog",
            "Multiple raw catalog snapshots are present for some programs.",
            multiple_snapshot_programs,
        )


def write_report(audit: Audit, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    status = "FAIL" if audit.fatal else "PASS_WITH_WARNINGS" if audit.warnings else "PASS"

    lines: list[str] = [
        "# Data Quality Report",
        "",
        f"Generated at UTC: `{generated_at}`",
        f"Status: `{status}`",
        "",
        "## Summary",
        "",
        f"- Fatal findings: {len(audit.fatal)}",
        f"- Warnings: {len(audit.warnings)}",
        f"- Info items: {len(audit.info)}",
        "",
    ]

    table_counts = audit.metrics.get("table_counts", {})
    if table_counts:
        lines.extend(
            [
                "## Database Table Counts",
                "",
                "| Table | Rows |",
                "| --- | ---: |",
            ]
        )
        for table, count in sorted(table_counts.items()):
            lines.append(f"| `{table}` | {count} |")
        lines.append("")

    active_programs = audit.metrics.get("active_programs", [])
    if active_programs:
        lines.extend(
            [
                "## Program Coverage",
                "",
                f"Active undergraduate programs: {len(active_programs)}",
                "",
                "`" + "`, `".join(active_programs) + "`",
                "",
            ]
        )

    add_metric_block(lines, "Course Quality Metrics", audit.metrics.get("course_quality", {}))
    add_metric_block(lines, "Prerequisite Quality Metrics", audit.metrics.get("prerequisite_quality", {}))
    add_metric_block(lines, "Review Summary", audit.metrics.get("review_summary", {}))

    per_program_curricula = audit.metrics.get("curriculum_json_per_program", {})
    if per_program_curricula:
        lines.extend(
            [
                "## Curriculum Files",
                "",
                "| Program | Requirements | Options | Placeholders | Unique Courses |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for program, values in sorted(per_program_curricula.items()):
            lines.append(
                "| {program} | {requirements} | {options} | {placeholders} | {unique_courses} |".format(
                    program=program,
                    **values,
                )
            )
        lines.append("")

    per_program_prereq = audit.metrics.get("per_program_prerequisite_graphs", {})
    if per_program_prereq:
        lines.extend(
            [
                "## Per-Program Prerequisite Graphs",
                "",
                "| Program | Nodes | Edges | Unresolved | DAG |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for program, values in sorted(per_program_prereq.items()):
            lines.append(
                f"| {program} | {values['nodes']} | {values['edges']} | "
                f"{values['unresolved']} | {values['is_dag']} |"
            )
        lines.append("")

    write_findings(lines, "Fatal Findings", audit.fatal)
    write_findings(lines, "Warnings", audit.warnings)
    write_findings(lines, "Info", audit.info)

    lines.extend(
        [
            "## Recommended Next Actions",
            "",
            "1. Fix all fatal findings before trusting generated data.",
            "2. Treat warnings as review queue items before production recommendation logic.",
            "3. Keep `offerings` empty status visible until the offerings pipeline is implemented.",
            "4. Resolve course identity warnings before showing graph nodes directly to students.",
            "",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")


def add_metric_block(lines: list[str], title: str, payload: Any) -> None:
    if not payload:
        return
    lines.extend([f"## {title}", "", "```json", json.dumps(payload, ensure_ascii=False, indent=2), "```", ""])


def write_findings(lines: list[str], title: str, findings: list[Finding]) -> None:
    lines.extend([f"## {title}", ""])
    if not findings:
        lines.extend(["None.", ""])
        return

    for index, finding in enumerate(findings, start=1):
        lines.append(f"{index}. **{finding.category}**: {finding.message}")
        for detail in finding.details[:100]:
            lines.append(f"   - {detail}")
        if len(finding.details) > 100:
            lines.append(f"   - ... {len(finding.details) - 100} more")
    lines.append("")


def main() -> int:
    args = parse_args()
    audit = Audit()
    db_path = project_path(args.db)
    processed_root = project_path(args.processed_root)
    raw_root = project_path(args.raw_root)
    report_path = project_path(args.report)

    connection, active_programs = audit_database(db_path, audit)
    audit_processed_files(processed_root, raw_root, active_programs, connection, audit)
    if connection is not None:
        connection.close()

    write_report(audit, report_path)
    status = "FAIL" if audit.fatal else "PASS_WITH_WARNINGS" if audit.warnings else "PASS"
    print(f"Data quality audit: {status}")
    print(f"Report: {report_path.resolve()}")
    print(f"Fatal findings: {len(audit.fatal)}")
    print(f"Warnings: {len(audit.warnings)}")
    return 1 if audit.fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
