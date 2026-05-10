from __future__ import annotations

import unittest

from student_planner.domain.grades import (
    Grade,
    compare_letter_grades,
    earns_credit,
    is_letter_grade,
    is_pass_fail_grade,
    is_supported_grade,
    is_unsuccessful,
    is_withdrawal,
    normalize_grade,
    satisfies_min_grade,
)


class GradeTests(unittest.TestCase):
    def test_normalizes_all_supported_grades(self) -> None:
        for value in ["AA", "BA", "BB", "CB", "CC", "DC", "DD", "FD", "FF", "S", "U", "W", "NA", "EX"]:
            with self.subTest(value=value):
                self.assertEqual(normalize_grade(value), Grade(value))

    def test_normalize_accepts_case_and_descriptive_suffix(self) -> None:
        self.assertEqual(normalize_grade("aa"), Grade.AA)
        self.assertEqual(normalize_grade(" W (withdraw) "), Grade.W)
        self.assertEqual(normalize_grade("na (not allowed)"), Grade.NA)

    def test_rejects_unknown_grades(self) -> None:
        self.assertFalse(is_supported_grade("P"))
        with self.assertRaises(ValueError):
            normalize_grade("")
        with self.assertRaises(ValueError):
            normalize_grade("P")

    def test_grade_families(self) -> None:
        self.assertTrue(is_letter_grade("AA"))
        self.assertTrue(is_letter_grade("NA"))
        self.assertFalse(is_letter_grade("S"))
        self.assertTrue(is_pass_fail_grade("S"))
        self.assertTrue(is_pass_fail_grade("EX"))
        self.assertTrue(is_pass_fail_grade("U"))
        self.assertFalse(is_pass_fail_grade("DD"))

    def test_credit_policy(self) -> None:
        for grade in ["AA", "BA", "BB", "CB", "CC", "DC", "DD", "S", "EX"]:
            with self.subTest(grade=grade):
                self.assertTrue(earns_credit(grade))

        for grade in ["FD", "FF", "NA", "U", "W"]:
            with self.subTest(grade=grade):
                self.assertFalse(earns_credit(grade))
                self.assertTrue(is_unsuccessful(grade))

    def test_withdrawal_policy(self) -> None:
        self.assertTrue(is_withdrawal("W"))
        self.assertFalse(is_withdrawal("FF"))
        for minimum in ["AA", "DD", "FF", "S", "U", "EX"]:
            with self.subTest(minimum=minimum):
                self.assertFalse(satisfies_min_grade("W", minimum))

    def test_letter_grade_ordering(self) -> None:
        self.assertGreater(compare_letter_grades("AA", "BA"), 0)
        self.assertEqual(compare_letter_grades("FF", "NA"), 0)
        self.assertLess(compare_letter_grades("DD", "DC"), 0)
        with self.assertRaises(ValueError):
            compare_letter_grades("S", "DD")

    def test_letter_minimum_satisfaction(self) -> None:
        self.assertTrue(satisfies_min_grade("DD", "DD"))
        self.assertTrue(satisfies_min_grade("DC", "DD"))
        self.assertTrue(satisfies_min_grade("AA", "CC"))
        self.assertFalse(satisfies_min_grade("FD", "DD"))
        self.assertFalse(satisfies_min_grade("FF", "DD"))
        self.assertFalse(satisfies_min_grade("NA", "DD"))

    def test_na_behaves_like_ff(self) -> None:
        self.assertTrue(satisfies_min_grade("NA", "FF"))
        self.assertFalse(satisfies_min_grade("NA", "FD"))
        self.assertFalse(earns_credit("NA"))

    def test_ex_behaves_like_s(self) -> None:
        self.assertTrue(earns_credit("EX"))
        self.assertTrue(satisfies_min_grade("EX", "S"))
        self.assertTrue(satisfies_min_grade("EX", "DD"))
        self.assertFalse(satisfies_min_grade("EX", "CC"))

    def test_s_and_u_minimums(self) -> None:
        self.assertTrue(satisfies_min_grade("S", "S"))
        self.assertTrue(satisfies_min_grade("EX", "S"))
        self.assertTrue(satisfies_min_grade("DD", "S"))
        self.assertFalse(satisfies_min_grade("U", "S"))

        self.assertTrue(satisfies_min_grade("U", "U"))
        self.assertTrue(satisfies_min_grade("S", "U"))
        self.assertTrue(satisfies_min_grade("EX", "U"))
        self.assertTrue(satisfies_min_grade("DD", "U"))
        self.assertFalse(satisfies_min_grade("FF", "U"))


if __name__ == "__main__":
    unittest.main()
