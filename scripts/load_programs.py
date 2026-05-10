from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from student_planner.config import load_engineering_programs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load engineering programs into SQLite.")
    parser.add_argument(
        "--db",
        default="data/db/student_planner.sqlite",
        help="SQLite database path.",
    )
    parser.add_argument(
        "--config",
        default="config/engineering_programs.json",
        help="Engineering program config path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    config_path = Path(args.config)
    programs = load_engineering_programs(config_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executemany(
            """
            INSERT INTO programs (
                abbr,
                catalog_program_id,
                name_en,
                name_tr,
                faculty,
                is_active_undergraduate
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(abbr) DO UPDATE SET
                catalog_program_id = excluded.catalog_program_id,
                name_en = excluded.name_en,
                name_tr = excluded.name_tr,
                faculty = excluded.faculty,
                is_active_undergraduate = excluded.is_active_undergraduate
            """,
            [
                (
                    program.abbr,
                    program.catalog_program_id,
                    program.name_en,
                    program.name_tr,
                    program.faculty,
                    1 if program.is_active_undergraduate else 0,
                )
                for program in programs
            ],
        )

    active_count = sum(1 for program in programs if program.is_active_undergraduate)
    print(f"Loaded {len(programs)} programs ({active_count} active undergraduate).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
