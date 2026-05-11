from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.load_offerings import clear_offerings_for_semesters, load_offerings_file, offering_json_paths
from student_planner.repositories.sqlite import SQLiteStudentPlannerRepository


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "student_planner" / "db" / "schema.sql"


class LoadOfferingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.db_path = self.temp_path / "test.sqlite"
        self.offering_path = self.temp_path / "CENG.offerings.json"
        self._init_db()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _init_db(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            connection.execute(
                """
                INSERT INTO programs (
                    abbr,
                    catalog_program_id,
                    name_en,
                    name_tr,
                    faculty,
                    is_active_undergraduate
                )
                VALUES ('CENG', '571', 'Computer Engineering', 'Bilgisayar Muhendisligi', 'Engineering', 1)
                """
            )
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
                VALUES ('5720202', 'AEE', 202, 'AEE 202', 'MATHEMATICS FOR AEROSPACE ENGINEERS', 'undergraduate')
                """
            )
            connection.commit()

    def test_load_offerings_is_idempotent_and_preserves_existing_display_code(self) -> None:
        self.offering_path.write_text(json.dumps(offering_payload()), encoding="utf-8")

        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            first_count = load_offerings_file(connection, self.offering_path)
            second_count = load_offerings_file(connection, self.offering_path)
            connection.commit()

        repository = SQLiteStudentPlannerRepository(self.db_path)
        self.assertEqual(first_count, 2)
        self.assertEqual(second_count, 2)
        self.assertEqual(repository.count_offerings(), 2)
        self.assertEqual(repository.count_offerings("20242"), 2)
        self.assertEqual(
            set(repository.fetch_offered_course_codes("20242")),
            {"AEE 202", "CENG 140"},
        )
        self.assertEqual(repository.fetch_offering_subject_codes("20242"), ("AEE", "CENG"))

    def test_offering_json_paths_can_filter_by_semester_and_program(self) -> None:
        root = self.temp_path / "offerings"
        (root / "20241").mkdir(parents=True)
        (root / "20242").mkdir(parents=True)
        (root / "20241" / "CENG.offerings.json").write_text("{}", encoding="utf-8")
        (root / "20242" / "CENG.offerings.json").write_text("{}", encoding="utf-8")
        (root / "20242" / "EEE.offerings.json").write_text("{}", encoding="utf-8")

        paths = offering_json_paths(root, semesters=["20242"], programs=["CENG"])

        self.assertEqual([path.name for path in paths], ["CENG.offerings.json"])
        self.assertEqual(paths[0].parent.name, "20242")

    def test_clear_offerings_for_semesters_only_deletes_selected_semester(self) -> None:
        self.offering_path.write_text(json.dumps(offering_payload()), encoding="utf-8")
        other_payload = offering_payload()
        other_payload["semester"] = {"semester_no": "20241", "semester_text": "2024-2025 Fall"}
        other_path = self.temp_path / "CENG-20241.offerings.json"
        other_path.write_text(json.dumps(other_payload), encoding="utf-8")

        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            load_offerings_file(connection, self.offering_path)
            load_offerings_file(connection, other_path)
            clear_offerings_for_semesters(connection, ["20242"])
            connection.commit()

        repository = SQLiteStudentPlannerRepository(self.db_path)
        self.assertEqual(repository.count_offerings("20242"), 0)
        self.assertEqual(repository.count_offerings("20241"), 2)


def offering_payload() -> dict[str, object]:
    return {
        "program": {
            "abbr": "CENG",
            "catalog_program_id": "571",
            "name_en": "Computer Engineering",
            "name_tr": "Bilgisayar Muhendisligi",
            "faculty": "Engineering",
        },
        "semester": {
            "semester_no": "20242",
            "semester_text": "2024-2025 Spring",
        },
        "source": {
            "source_name": "METU SAIS Course Details",
            "source_url": "local:test-offering",
            "retrieved_at_utc": "2026-05-10T00:00:00+00:00",
            "content_path": "data/raw/sais/offerings/20242/CENG/program.html",
            "content_sha256": "abc123",
            "parser_version": "metu_sais_offerings_v1",
        },
        "offerings": [
            {
                "program_abbr": "CENG",
                "department_value": "571",
                "department_text": "Computer Engineering",
                "semester_no": "20242",
                "semester_text": "2024-2025 Spring",
                "numeric_code": "5710140",
                "display_code": "CENG 140",
                "course_number": 140,
                "course_name": "C PROGRAMMING",
                "ects_credit": "6",
                "credit": "4",
                "level": "Undergraduate / Lisans",
                "type": "Must",
            },
            {
                "program_abbr": "AE",
                "department_value": "572",
                "department_text": "Aerospace Engineering",
                "semester_no": "20242",
                "semester_text": "2024-2025 Spring",
                "numeric_code": "5720202",
                "display_code": "AE 202",
                "course_number": 202,
                "course_name": "MATHEMATICS FOR AEROSPACE ENGINEERS",
                "ects_credit": "6",
                "credit": "4",
                "level": "Undergraduate / Lisans",
                "type": "Must",
            },
            {
                "program_abbr": "CENG",
                "department_value": "571",
                "department_text": "Computer Engineering",
                "semester_no": "20242",
                "semester_text": "2024-2025 Spring",
                "numeric_code": "5710501",
                "display_code": "CENG 501",
                "course_number": 501,
                "course_name": "GRADUATE TEST COURSE",
                "ects_credit": "8",
                "credit": "3",
                "level": "Graduate",
                "type": "Elective",
            },
        ],
        "summary": {
            "offering_count": 3,
            "undergraduate_count": 2,
        },
    }


if __name__ == "__main__":
    unittest.main()
