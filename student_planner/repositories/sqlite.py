from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from student_planner.domain.models import (
    Course,
    CurriculumRequirementOption,
    CurriculumRequirementRecord,
    CurriculumSnapshot,
    Program,
    RequirementType,
    ReviewStatus,
)
from student_planner.services.prerequisite_evaluator import (
    CompletedInput,
    CourseAliases,
    EligibilityResult,
    PrerequisiteEdge,
    canonicalize_course_code,
    evaluate_eligibility,
    normalize_course_code,
)


class SQLiteStudentPlannerRepository:
    def __init__(self, db_path: str | Path = "data/db/student_planner.sqlite") -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def fetch_alias_map(self) -> dict[str, str]:
        """Return aliases that map user/source codes to canonical display codes.

        The map includes:

        - each course display code to itself
        - each course numeric code to its display code
        - reviewed/manual aliases from `course_aliases`
        """

        aliases: dict[str, str] = {}
        with closing(self.connect()) as connection:
            for row in connection.execute(
                """
                SELECT display_code, numeric_code
                FROM courses
                ORDER BY display_code
                """
            ):
                display_code = normalize_course_code(row["display_code"])
                aliases[display_code] = display_code
                if row["numeric_code"]:
                    aliases[normalize_course_code(row["numeric_code"])] = display_code

            for row in connection.execute(
                """
                SELECT ca.alias, c.display_code
                FROM course_aliases ca
                JOIN courses c ON c.id = ca.course_id
                WHERE ca.review_status IN ('reviewed', 'corrected')
                ORDER BY ca.alias
                """
            ):
                aliases[normalize_course_code(row["alias"])] = normalize_course_code(row["display_code"])

        return aliases

    def fetch_latest_curriculum(self, program_abbr: str) -> CurriculumSnapshot:
        """Return the latest curriculum snapshot for a program.

        The snapshot is read-only domain data: requirements preserve their DB ids,
        ordering, review status, and concrete course options.
        """

        program_abbr = program_abbr.strip().upper()
        if not program_abbr:
            raise ValueError("program_abbr cannot be empty.")

        with closing(self.connect()) as connection:
            curriculum_row = connection.execute(
                """
                SELECT p.id AS program_id,
                       p.abbr,
                       p.catalog_program_id,
                       p.name_en,
                       p.name_tr,
                       p.faculty,
                       p.is_active_undergraduate,
                       cv.id AS curriculum_version_id,
                       cv.version_label,
                       cv.is_latest,
                       cv.review_status
                FROM curriculum_versions cv
                JOIN programs p ON p.id = cv.program_id
                WHERE p.abbr = ? AND cv.is_latest = 1
                ORDER BY cv.id DESC
                LIMIT 1
                """,
                (program_abbr,),
            ).fetchone()
            if curriculum_row is None:
                raise LookupError(f"Latest curriculum not found for program {program_abbr}.")

            requirement_rows = list(
                connection.execute(
                    """
                    SELECT id,
                           requirement_type,
                           label,
                           recommended_year,
                           recommended_term,
                           course_count_min,
                           credits_min,
                           ects_min,
                           sort_order,
                           review_status
                    FROM curriculum_requirements
                    WHERE curriculum_version_id = ?
                    ORDER BY COALESCE(sort_order, id), id
                    """,
                    (curriculum_row["curriculum_version_id"],),
                )
            )
            requirement_ids = [row["id"] for row in requirement_rows]
            options_by_requirement = self._fetch_requirement_options(connection, requirement_ids)

        program = Program(
            abbr=curriculum_row["abbr"],
            catalog_program_id=curriculum_row["catalog_program_id"] or "",
            name_en=curriculum_row["name_en"],
            name_tr=curriculum_row["name_tr"] or "",
            faculty=curriculum_row["faculty"],
            is_active_undergraduate=bool(curriculum_row["is_active_undergraduate"]),
        )
        requirements = tuple(
            CurriculumRequirementRecord(
                id=row["id"],
                requirement_type=RequirementType(row["requirement_type"]),
                label=row["label"],
                recommended_year=row["recommended_year"],
                recommended_term=row["recommended_term"],
                course_count_min=row["course_count_min"],
                credits_min=row["credits_min"],
                ects_min=row["ects_min"],
                sort_order=row["sort_order"],
                review_status=ReviewStatus(row["review_status"]),
                options=tuple(options_by_requirement.get(row["id"], ())),
            )
            for row in requirement_rows
        )
        return CurriculumSnapshot(
            program=program,
            version_id=curriculum_row["curriculum_version_id"],
            version_label=curriculum_row["version_label"],
            is_latest=bool(curriculum_row["is_latest"]),
            review_status=ReviewStatus(curriculum_row["review_status"]),
            requirements=requirements,
        )

    def _fetch_requirement_options(
        self,
        connection: sqlite3.Connection,
        requirement_ids: list[int],
    ) -> dict[int, list[CurriculumRequirementOption]]:
        if not requirement_ids:
            return {}

        placeholders = ", ".join("?" for _ in requirement_ids)
        rows = list(
            connection.execute(
                f"""
                SELECT ro.id,
                       ro.requirement_id,
                       ro.option_label,
                       ro.option_group,
                       ro.is_required_option,
                       c.numeric_code,
                       c.subject_code,
                       c.course_number,
                       c.display_code,
                       c.title_en,
                       c.title_tr,
                       c.level
                FROM requirement_options ro
                LEFT JOIN courses c ON c.id = ro.course_id
                WHERE ro.requirement_id IN ({placeholders})
                ORDER BY ro.requirement_id, ro.id
                """,
                tuple(requirement_ids),
            )
        )

        options_by_requirement: dict[int, list[CurriculumRequirementOption]] = {
            requirement_id: [] for requirement_id in requirement_ids
        }
        for row in rows:
            course = None
            if row["display_code"] is not None:
                course = Course(
                    numeric_code=row["numeric_code"],
                    subject_code=row["subject_code"],
                    course_number=row["course_number"],
                    display_code=row["display_code"],
                    title_en=row["title_en"] or "",
                    title_tr=row["title_tr"] or "",
                    level=row["level"] or "undergraduate",
                )
            options_by_requirement[row["requirement_id"]].append(
                CurriculumRequirementOption(
                    id=row["id"],
                    course=course,
                    option_label=row["option_label"],
                    option_group=row["option_group"],
                    is_required_option=bool(row["is_required_option"]),
                )
            )
        return options_by_requirement

    def fetch_prerequisite_edges_for_course(
        self,
        target_course_code: str,
        aliases: CourseAliases | None = None,
    ) -> list[PrerequisiteEdge]:
        aliases = aliases or self.fetch_alias_map()
        target = canonicalize_course_code(target_course_code, aliases)

        with closing(self.connect()) as connection:
            rows = list(
                connection.execute(
                    """
                    SELECT prereq.display_code AS prerequisite_course_code,
                           course.display_code AS course_code,
                           pe.set_no,
                           pe.min_grade,
                           pe.edge_type,
                           pe.position
                    FROM prerequisite_edges pe
                    JOIN courses prereq ON prereq.id = pe.prerequisite_course_id
                    JOIN courses course ON course.id = pe.course_id
                    WHERE course.display_code = ?
                    ORDER BY CAST(pe.set_no AS INTEGER), pe.set_no, prereq.display_code
                    """,
                    (target,),
                )
            )

        return [
            PrerequisiteEdge(
                prerequisite_course_code=row["prerequisite_course_code"],
                course_code=row["course_code"],
                set_no=row["set_no"],
                min_grade=row["min_grade"] or "DD",
                edge_type=row["edge_type"] or "",
                position=row["position"] or "",
            )
            for row in rows
        ]

    def fetch_prerequisite_edges_for_courses(
        self,
        target_course_codes: list[str] | tuple[str, ...],
        aliases: CourseAliases | None = None,
    ) -> dict[str, list[PrerequisiteEdge]]:
        aliases = aliases or self.fetch_alias_map()
        targets = tuple(
            sorted({canonicalize_course_code(course_code, aliases) for course_code in target_course_codes})
        )
        if not targets:
            return {}

        placeholders = ", ".join("?" for _ in targets)
        with closing(self.connect()) as connection:
            rows = list(
                connection.execute(
                    f"""
                    SELECT prereq.display_code AS prerequisite_course_code,
                           course.display_code AS course_code,
                           pe.set_no,
                           pe.min_grade,
                           pe.edge_type,
                           pe.position
                    FROM prerequisite_edges pe
                    JOIN courses prereq ON prereq.id = pe.prerequisite_course_id
                    JOIN courses course ON course.id = pe.course_id
                    WHERE course.display_code IN ({placeholders})
                    ORDER BY course.display_code, CAST(pe.set_no AS INTEGER), pe.set_no, prereq.display_code
                    """,
                    targets,
                )
            )

        edges_by_course: dict[str, list[PrerequisiteEdge]] = {target: [] for target in targets}
        for row in rows:
            edge = PrerequisiteEdge(
                prerequisite_course_code=row["prerequisite_course_code"],
                course_code=row["course_code"],
                set_no=row["set_no"],
                min_grade=row["min_grade"] or "DD",
                edge_type=row["edge_type"] or "",
                position=row["position"] or "",
            )
            edges_by_course[canonicalize_course_code(row["course_code"], aliases)].append(edge)
        return edges_by_course

    def evaluate_course_eligibility(
        self,
        target_course_code: str,
        completed_courses: CompletedInput,
    ) -> EligibilityResult:
        aliases = self.fetch_alias_map()
        edges = self.fetch_prerequisite_edges_for_course(target_course_code, aliases)
        target = canonicalize_course_code(target_course_code, aliases)
        return evaluate_eligibility(
            target_course_code=target,
            prerequisite_edges=edges,
            completed_courses=completed_courses,
            aliases=aliases,
        )
