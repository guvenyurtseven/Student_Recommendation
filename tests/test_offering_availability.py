from __future__ import annotations

import unittest

from student_planner.domain.planning import CourseEligibilitySummary
from student_planner.services.candidate_courses import CandidateCourse, CandidateCourseResult
from student_planner.services.offering_availability import (
    OfferingAvailabilityService,
    OfferingAvailabilityStatus,
)


class OfferingAvailabilityServiceTests(unittest.TestCase):
    def test_filters_known_not_offered_but_keeps_unknown_subjects(self) -> None:
        candidate_result = CandidateCourseResult(
            eligible_courses=(
                candidate("CENG 213"),
                candidate("CENG 223"),
                candidate("MATH 120"),
            ),
            blocked_courses=(),
        )

        result = OfferingAvailabilityService().filter_for_target_semester(
            candidate_result=candidate_result,
            target_semester_no="20252",
            offered_course_codes=("CENG 213",),
            covered_subject_codes=("CENG",),
        )

        self.assertEqual(
            tuple(course.course_code for course in result.candidate_result.eligible_courses),
            ("CENG 213", "MATH 120"),
        )
        self.assertEqual(
            tuple(course.course_code for course in result.candidate_result.blocked_courses),
            ("CENG 223",),
        )
        self.assertIn("not listed in loaded offerings", result.candidate_result.blocked_courses[0].eligibility.explanation)
        status_by_course = {item.course_code: item.status for item in result.availability}
        self.assertEqual(status_by_course["CENG 213"], OfferingAvailabilityStatus.OFFERED)
        self.assertEqual(status_by_course["CENG 223"], OfferingAvailabilityStatus.NOT_OFFERED)
        self.assertEqual(status_by_course["MATH 120"], OfferingAvailabilityStatus.UNKNOWN)
        self.assertEqual(
            {warning.code for warning in result.warnings},
            {"target_semester_not_offered", "offering_coverage_unknown"},
        )

    def test_no_coverage_leaves_candidates_unchanged(self) -> None:
        candidate_result = CandidateCourseResult(
            eligible_courses=(candidate("CENG 213"),),
            blocked_courses=(),
        )

        result = OfferingAvailabilityService().filter_for_target_semester(
            candidate_result=candidate_result,
            target_semester_no="20252",
            offered_course_codes=(),
            covered_subject_codes=(),
        )

        self.assertIs(result.candidate_result, candidate_result)
        self.assertEqual(result.availability, ())
        self.assertEqual(result.warnings, ())


def candidate(course_code: str) -> CandidateCourse:
    return CandidateCourse(
        course_code=course_code,
        eligibility=CourseEligibilitySummary(course_code=course_code, is_eligible=True),
    )


if __name__ == "__main__":
    unittest.main()
