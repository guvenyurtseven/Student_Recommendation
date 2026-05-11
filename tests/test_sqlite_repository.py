from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from student_planner.domain.models import RequirementType, ReviewStatus
from student_planner.services.prerequisite_evaluator import CompletedCourse
from student_planner.repositories.sqlite import SQLiteStudentPlannerRepository


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "student_planner" / "db" / "schema.sql"


class SQLiteRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.sqlite"
        self._init_db()
        self.repository = SQLiteStudentPlannerRepository(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _init_db(self) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection = sqlite3.connect(self.db_path)
        try:
            connection.executescript(schema)
            self._insert_program(connection, "CENG", "571", "Computer Engineering")
            self._insert_course(connection, "2360119", "MATH", 119, "MATH 119")
            self._insert_course(connection, "2360120", "MATH", 120, "MATH 120")
            self._insert_course(connection, "2360219", "MATH", 219, "MATH 219")
            self._insert_course(connection, "6390101", "ENG", 101, "ENG 101")
            self._insert_course(connection, "6390102", "ENG", 102, "ENG 102")
            self._insert_course(connection, "5710140", "CENG", 140, "CENG 140")
            self._insert_course(connection, "5710213", "CENG", 213, "CENG 213")
            self._insert_course(connection, "3550140", "355", 140, "355 140")
            self._insert_edge(connection, "MATH 119", "MATH 120", "1", "DD")
            self._insert_edge(connection, "MATH 120", "MATH 219", "1", "DD")
            self._insert_edge(connection, "CENG 140", "CENG 213", "1", "DD")
            self._insert_alias(connection, "CENG 140", "355 140", "ncc_equivalent")
            self._insert_curriculum_fixture(connection)
            connection.commit()
        finally:
            connection.close()

    def _insert_program(
        self,
        connection: sqlite3.Connection,
        abbr: str,
        catalog_program_id: str,
        name_en: str,
    ) -> None:
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
            VALUES (?, ?, ?, ?, 'Engineering', 1)
            """,
            (abbr, catalog_program_id, name_en, name_en),
        )

    def _insert_course(
        self,
        connection: sqlite3.Connection,
        numeric_code: str,
        subject_code: str,
        course_number: int,
        display_code: str,
    ) -> None:
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
            """,
            (numeric_code, subject_code, course_number, display_code, display_code),
        )

    def _course_id(self, connection: sqlite3.Connection, display_code: str) -> int:
        return int(
            connection.execute(
                "SELECT id FROM courses WHERE display_code = ?",
                (display_code,),
            ).fetchone()[0]
        )

    def _insert_curriculum_fixture(self, connection: sqlite3.Connection) -> None:
        program_id = int(connection.execute("SELECT id FROM programs WHERE abbr = 'CENG'").fetchone()[0])
        connection.execute(
            """
            INSERT INTO curriculum_versions (
                program_id,
                version_label,
                is_latest,
                review_status
            )
            VALUES (?, 'latest', 1, 'scraped')
            """,
            (program_id,),
        )
        curriculum_version_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        requirements = [
            ("required_course", "CENG 140", 1, "Fall", 1, 4.0, 6.0, 1, ["CENG 140"]),
            ("course_choice", "ENG 101 or ENG 102", 1, "Fall", 1, 4.0, 6.0, 2, ["ENG 101", "ENG 102"]),
            ("technical_elective_pool", "Technical Elective", 4, "Spring", 1, None, 5.0, 3, []),
        ]
        for (
            requirement_type,
            label,
            year,
            term,
            count_min,
            credits,
            ects,
            sort_order,
            course_codes,
        ) in requirements:
            connection.execute(
                """
                INSERT INTO curriculum_requirements (
                    curriculum_version_id,
                    requirement_type,
                    label,
                    recommended_year,
                    recommended_term,
                    course_count_min,
                    credits_min,
                    ects_min,
                    sort_order,
                    review_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'scraped')
                """,
                (
                    curriculum_version_id,
                    requirement_type,
                    label,
                    year,
                    term,
                    count_min,
                    credits,
                    ects,
                    sort_order,
                ),
            )
            requirement_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            for course_code in course_codes:
                connection.execute(
                    """
                    INSERT INTO requirement_options (
                        requirement_id,
                        course_id,
                        option_group,
                        is_required_option
                    )
                    VALUES (?, ?, ?, 1)
                    """,
                    (requirement_id, self._course_id(connection, course_code), label),
                )

    def _insert_edge(
        self,
        connection: sqlite3.Connection,
        prerequisite: str,
        course: str,
        set_no: str,
        min_grade: str,
    ) -> None:
        prerequisite_id = connection.execute(
            "SELECT id FROM courses WHERE display_code = ?",
            (prerequisite,),
        ).fetchone()[0]
        course_id = connection.execute(
            "SELECT id FROM courses WHERE display_code = ?",
            (course,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO prerequisite_edges (
                prerequisite_course_id,
                course_id,
                set_no,
                min_grade,
                edge_type,
                position
            )
            VALUES (?, ?, ?, ?, 'Undergraduate / Lisans', 'Offered Course / Acik Ders')
            """,
            (prerequisite_id, course_id, set_no, min_grade),
        )

    def _insert_alias(
        self,
        connection: sqlite3.Connection,
        canonical: str,
        alias: str,
        relation_type: str,
    ) -> None:
        course_id = connection.execute(
            "SELECT id FROM courses WHERE display_code = ?",
            (canonical,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO course_aliases (
                course_id,
                alias,
                relation_type,
                review_status,
                notes
            )
            VALUES (?, ?, ?, 'reviewed', 'test alias')
            """,
            (course_id, alias, relation_type),
        )

    def test_fetch_alias_map_includes_display_numeric_and_manual_aliases(self) -> None:
        aliases = self.repository.fetch_alias_map()
        self.assertEqual(aliases["MATH 119"], "MATH 119")
        self.assertEqual(aliases["2360119"], "MATH 119")
        self.assertEqual(aliases["355 140"], "CENG 140")

    def test_fetch_prerequisite_edges_for_course(self) -> None:
        edges = self.repository.fetch_prerequisite_edges_for_course("math219")
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].prerequisite_course_code, "MATH 120")
        self.assertEqual(edges[0].course_code, "MATH 219")

    def test_fetch_prerequisite_edges_for_courses(self) -> None:
        edges_by_course = self.repository.fetch_prerequisite_edges_for_courses(
            ("math219", "ceng213", "eng101")
        )
        self.assertEqual(set(edges_by_course), {"MATH 219", "CENG 213", "ENG 101"})
        self.assertEqual(len(edges_by_course["MATH 219"]), 1)
        self.assertEqual(edges_by_course["MATH 219"][0].prerequisite_course_code, "MATH 120")
        self.assertEqual(edges_by_course["CENG 213"][0].prerequisite_course_code, "CENG 140")
        self.assertEqual(edges_by_course["ENG 101"], [])

    def test_fetch_all_prerequisite_edges(self) -> None:
        edges = self.repository.fetch_all_prerequisite_edges()
        pairs = {(edge.prerequisite_course_code, edge.course_code) for edge in edges}
        self.assertIn(("MATH 119", "MATH 120"), pairs)
        self.assertIn(("MATH 120", "MATH 219"), pairs)
        self.assertIn(("CENG 140", "CENG 213"), pairs)

    def test_count_offerings(self) -> None:
        self.assertEqual(self.repository.count_offerings(), 0)

    def test_fetch_course_ects_estimates_from_curriculum_requirements(self) -> None:
        estimates = self.repository.fetch_course_ects_estimates(("ceng140", "math219"))

        self.assertEqual(estimates["CENG 140"], 6.0)
        self.assertNotIn("MATH 219", estimates)

    def test_fetch_latest_curriculum_returns_requirements_and_options(self) -> None:
        curriculum = self.repository.fetch_latest_curriculum("ceng")
        self.assertEqual(curriculum.program.abbr, "CENG")
        self.assertEqual(curriculum.version_label, "latest")
        self.assertTrue(curriculum.is_latest)
        self.assertEqual(curriculum.review_status, ReviewStatus.SCRAPED)
        self.assertEqual(curriculum.requirement_count, 3)
        self.assertEqual(curriculum.requirements[0].requirement_type, RequirementType.REQUIRED_COURSE)
        self.assertEqual(curriculum.requirements[0].option_course_codes, ("CENG 140",))
        self.assertEqual(curriculum.requirements[1].option_course_codes, ("ENG 101", "ENG 102"))
        self.assertEqual(curriculum.requirements[2].option_course_codes, ())
        self.assertEqual(
            curriculum.concrete_course_codes,
            ("CENG 140", "ENG 101", "ENG 102"),
        )

    def test_evaluate_course_eligibility_from_db(self) -> None:
        result = self.repository.evaluate_course_eligibility(
            "MATH219",
            completed_courses={
                "MATH 120": "DD",
                "MATH 119": "FF",
            },
        )
        self.assertTrue(result.is_eligible)

    def test_repeated_transitive_prerequisite_from_db_does_not_block_target(self) -> None:
        result = self.repository.evaluate_course_eligibility(
            "MATH219",
            completed_courses=[
                CompletedCourse("MATH 119", "DD", attempt_order=1),
                CompletedCourse("MATH 120", "DD", attempt_order=2),
                CompletedCourse("MATH 119", "FF", attempt_order=3),
            ],
        )
        self.assertTrue(result.is_eligible)

    def test_repeated_direct_prerequisite_from_db_blocks_target_when_latest_fails(self) -> None:
        result = self.repository.evaluate_course_eligibility(
            "MATH120",
            completed_courses=[
                CompletedCourse("MATH 119", "DD", attempt_order=1),
                CompletedCourse("MATH 119", "FF", attempt_order=2),
            ],
        )
        self.assertFalse(result.is_eligible)

    def test_manual_aliases_are_used_for_completed_courses(self) -> None:
        result = self.repository.evaluate_course_eligibility(
            "CENG 213",
            completed_courses={"355 140": "CC"},
        )
        self.assertTrue(result.is_eligible)


if __name__ == "__main__":
    unittest.main()
