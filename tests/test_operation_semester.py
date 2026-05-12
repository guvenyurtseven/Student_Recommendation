from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from student_planner.services.operation_semester import (
    load_operation_semester,
    semester_label,
    validate_semester_no,
    write_operation_semester,
)


class OperationSemesterTests(unittest.TestCase):
    def test_semester_label_matches_metu_term_codes(self) -> None:
        self.assertEqual(semester_label("20251"), "2025-2026 Fall")
        self.assertEqual(semester_label("20252"), "2025-2026 Spring")
        self.assertEqual(semester_label("20253"), "2025-2026 Summer")

    def test_rejects_invalid_semester_code(self) -> None:
        with self.assertRaises(ValueError):
            validate_semester_no("20254")

    def test_write_and_load_operation_semester(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "operation.json"

            written = write_operation_semester("20252", path, updated_by="test")
            loaded = load_operation_semester(path)

        self.assertEqual(written.active_semester_no, "20252")
        self.assertEqual(loaded.active_semester_no, "20252")
        self.assertEqual(loaded.active_semester_label, "2025-2026 Spring")
        self.assertEqual(loaded.updated_by, "test")


if __name__ == "__main__":
    unittest.main()
