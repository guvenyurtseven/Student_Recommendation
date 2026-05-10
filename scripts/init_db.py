from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the local SQLite database.")
    parser.add_argument(
        "--db",
        default="data/db/student_planner.sqlite",
        help="SQLite database path.",
    )
    parser.add_argument(
        "--schema",
        default="student_planner/db/schema.sql",
        help="Schema SQL path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    schema_path = Path(args.schema)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = schema_path.read_text(encoding="utf-8")

    with sqlite3.connect(db_path) as connection:
        connection.executescript(schema)
        connection.execute("PRAGMA foreign_keys = ON")

    print(f"Initialized database at {db_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
