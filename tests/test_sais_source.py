from __future__ import annotations

import unittest

from student_planner.domain.models import Program
from student_planner.sources.sais import (
    choose_department_option,
    extract_course_offerings,
    parse_forms,
)


class SaisSourceTests(unittest.TestCase):
    def test_choose_department_option_prefers_catalog_program_id(self) -> None:
        forms = parse_forms(
            """
            <form action="main.php">
              <select name="select_dept">
                <option value="999">Computer Engineering (Kuzey Kibris)</option>
                <option value="571">Computer Engineering</option>
              </select>
            </form>
            """
        )
        value, text = choose_department_option(
            forms[0],
            Program(
                abbr="CENG",
                catalog_program_id="571",
                name_en="Computer Engineering",
                name_tr="Bilgisayar Muhendisligi",
                faculty="Engineering",
            ),
        )

        self.assertEqual(value, "571")
        self.assertEqual(text, "Computer Engineering")

    def test_extract_course_offerings_reads_course_table(self) -> None:
        html = """
        <table>
          <tr>
            <th>Code</th><th>Name</th><th>ECTS Credit</th>
            <th>Credit</th><th>Level</th><th>Type</th>
          </tr>
          <tr>
            <td>5710140</td><td>C PROGRAMMING</td><td>6</td>
            <td>4</td><td>Undergraduate / Lisans</td><td>Must</td>
          </tr>
        </table>
        """
        offerings = extract_course_offerings(
            result_html=html,
            program=Program(
                abbr="CENG",
                catalog_program_id="571",
                name_en="Computer Engineering",
                name_tr="Bilgisayar Muhendisligi",
                faculty="Engineering",
            ),
            department_value="571",
            department_text="Computer Engineering",
            semester_no="20242",
            semester_text="2024-2025 Spring",
        )

        self.assertEqual(len(offerings), 1)
        self.assertEqual(offerings[0].numeric_code, "5710140")
        self.assertEqual(offerings[0].display_code, "CENG 140")
        self.assertEqual(offerings[0].course_number, 140)
        self.assertEqual(offerings[0].course_name, "C PROGRAMMING")


if __name__ == "__main__":
    unittest.main()
