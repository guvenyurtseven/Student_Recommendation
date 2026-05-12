from __future__ import annotations

import base64
import hashlib
import hmac
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_ADMIN_USERNAME = "roskalot"
DEFAULT_ADMIN_SALT = "wSPQGld6h6UK4/keYa0m+Q=="
DEFAULT_ADMIN_PASSWORD_HASH = "cVlnffgrcd0UgHUZJpuPOG4HCY3bohE53nTHruY+Xm4="
DEFAULT_ADMIN_ITERATIONS = 210000
MAX_FEEDBACK_LENGTH = 4000


def ensure_app_tables(db_path: str | Path) -> None:
    with closing(connect(db_path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                iterations INTEGER NOT NULL,
                created_at_utc TEXT NOT NULL,
                last_login_at_utc TEXT
            );

            CREATE TABLE IF NOT EXISTS user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feedback_text TEXT NOT NULL,
                is_favorite INTEGER NOT NULL DEFAULT 0,
                favorited_at_utc TEXT,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_user_feedback_order
                ON user_feedback(is_favorite, favorited_at_utc, created_at_utc);
            """
        )
        seed_default_admin(connection)
        connection.commit()


def verify_admin_credentials(db_path: str | Path, username: str, password: str) -> dict[str, Any]:
    ensure_app_tables(db_path)
    clean_username = username.strip()
    if not clean_username or not password:
        return {"ok": False, "error": "Invalid credentials."}

    with closing(connect(db_path)) as connection:
        row = connection.execute(
            """
            SELECT id, username, password_hash, salt, iterations
            FROM admin_users
            WHERE username = ?
            """,
            (clean_username,),
        ).fetchone()
        if row is None or not password_matches(password, row["salt"], row["iterations"], row["password_hash"]):
            return {"ok": False, "error": "Invalid credentials."}
        connection.execute(
            "UPDATE admin_users SET last_login_at_utc = ? WHERE id = ?",
            (utc_now(), row["id"]),
        )
        connection.commit()
        return {"ok": True, "admin": {"username": row["username"]}}


def submit_feedback(db_path: str | Path, feedback_text: str) -> dict[str, Any]:
    ensure_app_tables(db_path)
    text = normalize_feedback_text(feedback_text)
    now = utc_now()
    with closing(connect(db_path)) as connection:
        cursor = connection.execute(
            """
            INSERT INTO user_feedback (feedback_text, created_at_utc, updated_at_utc)
            VALUES (?, ?, ?)
            """,
            (text, now, now),
        )
        connection.commit()
        return {"ok": True, "feedback": feedback_row_to_dict(fetch_feedback(connection, int(cursor.lastrowid)))}


def list_feedback(db_path: str | Path) -> dict[str, Any]:
    ensure_app_tables(db_path)
    with closing(connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT id, feedback_text, is_favorite, favorited_at_utc, created_at_utc, updated_at_utc
            FROM user_feedback
            ORDER BY
                is_favorite DESC,
                CASE WHEN is_favorite = 1 THEN favorited_at_utc END ASC,
                CASE WHEN is_favorite = 1 THEN id END ASC,
                created_at_utc DESC,
                id DESC
            """
        ).fetchall()
        return {"ok": True, "feedbacks": [feedback_row_to_dict(row) for row in rows]}


def set_feedback_favorite(db_path: str | Path, feedback_id: int, is_favorite: bool) -> dict[str, Any]:
    ensure_app_tables(db_path)
    now = utc_now()
    with closing(connect(db_path)) as connection:
        current = fetch_feedback(connection, feedback_id)
        if current is None:
            raise LookupError("Feedback not found.")
        favorited_at = now if is_favorite and not current["favorited_at_utc"] else current["favorited_at_utc"]
        if not is_favorite:
            favorited_at = None
        connection.execute(
            """
            UPDATE user_feedback
            SET is_favorite = ?, favorited_at_utc = ?, updated_at_utc = ?
            WHERE id = ?
            """,
            (1 if is_favorite else 0, favorited_at, now, feedback_id),
        )
        connection.commit()
        return {"ok": True, "feedback": feedback_row_to_dict(fetch_feedback(connection, feedback_id))}


def delete_feedback(db_path: str | Path, feedback_id: int) -> dict[str, Any]:
    ensure_app_tables(db_path)
    with closing(connect(db_path)) as connection:
        cursor = connection.execute("DELETE FROM user_feedback WHERE id = ?", (feedback_id,))
        connection.commit()
        if cursor.rowcount == 0:
            raise LookupError("Feedback not found.")
        return {"ok": True, "deleted_id": feedback_id}


def seed_default_admin(connection: sqlite3.Connection) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT OR IGNORE INTO admin_users (
            username,
            password_hash,
            salt,
            iterations,
            created_at_utc
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            DEFAULT_ADMIN_USERNAME,
            DEFAULT_ADMIN_PASSWORD_HASH,
            DEFAULT_ADMIN_SALT,
            DEFAULT_ADMIN_ITERATIONS,
            now,
        ),
    )


def password_matches(password: str, salt: str, iterations: int, expected_hash: str) -> bool:
    salt_bytes = base64.b64decode(salt)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, int(iterations))
    actual_hash = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(actual_hash, expected_hash)


def normalize_feedback_text(feedback_text: str) -> str:
    text = str(feedback_text or "").strip()
    if not text:
        raise ValueError("Feedback text cannot be empty.")
    if len(text) > MAX_FEEDBACK_LENGTH:
        raise ValueError(f"Feedback text cannot exceed {MAX_FEEDBACK_LENGTH} characters.")
    return text


def fetch_feedback(connection: sqlite3.Connection, feedback_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, feedback_text, is_favorite, favorited_at_utc, created_at_utc, updated_at_utc
        FROM user_feedback
        WHERE id = ?
        """,
        (feedback_id,),
    ).fetchone()


def feedback_row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise LookupError("Feedback not found.")
    return {
        "id": int(row["id"]),
        "text": row["feedback_text"],
        "is_favorite": bool(row["is_favorite"]),
        "favorited_at_utc": row["favorited_at_utc"],
        "created_at_utc": row["created_at_utc"],
        "updated_at_utc": row["updated_at_utc"],
    }


def connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
