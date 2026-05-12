from __future__ import annotations

import tempfile
import unittest
import os
from pathlib import Path

from student_planner.web.app_data import (
    delete_feedback,
    ensure_app_tables,
    list_feedback,
    set_feedback_favorite,
    submit_feedback,
    verify_admin_credentials,
)


class WebAppDataTests(unittest.TestCase):
    def test_seeded_admin_can_sign_in(self) -> None:
        db_path = temp_db_path()
        ensure_app_tables(db_path)

        response = verify_admin_credentials(db_path, "roskalot", "gvnyurtsevenroskalot3392")

        self.assertTrue(response["ok"])
        self.assertEqual(response["admin"]["username"], "roskalot")

    def test_wrong_admin_password_fails(self) -> None:
        db_path = temp_db_path()
        ensure_app_tables(db_path)

        response = verify_admin_credentials(db_path, "roskalot", "wrong")

        self.assertFalse(response["ok"])

    def test_feedback_lifecycle_and_favorite_ordering(self) -> None:
        db_path = temp_db_path()
        first = submit_feedback(db_path, "first idea")["feedback"]
        second = submit_feedback(db_path, "second idea")["feedback"]
        third = submit_feedback(db_path, "third idea")["feedback"]

        set_feedback_favorite(db_path, second["id"], True)
        set_feedback_favorite(db_path, third["id"], True)

        listed = list_feedback(db_path)["feedbacks"]
        self.assertEqual([item["id"] for item in listed[:2]], [second["id"], third["id"]])

        delete_feedback(db_path, first["id"])
        listed = list_feedback(db_path)["feedbacks"]
        self.assertNotIn(first["id"], {item["id"] for item in listed})


def temp_db_path() -> Path:
    fd, name = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    return Path(name)


if __name__ == "__main__":
    unittest.main()
