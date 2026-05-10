"""Application services."""

from student_planner.services.candidate_courses import (
    CandidateCourse,
    CandidateCourseGenerator,
    CandidateCourseResult,
)
from student_planner.services.curriculum_progress import (
    CurriculumProgressResult,
    CurriculumProgressService,
    latest_completed_credit_courses,
)
from student_planner.services.prerequisite_evaluator import (
    CompletedCourse,
    EligibilityResult,
    PrerequisiteEdge,
    PrerequisiteSetEvaluation,
    RequirementEvaluation,
    build_completed_course_index,
    canonicalize_course_code,
    evaluate_eligibility,
    normalize_course_code,
)

__all__ = [
    "CandidateCourse",
    "CandidateCourseGenerator",
    "CandidateCourseResult",
    "CompletedCourse",
    "CurriculumProgressResult",
    "CurriculumProgressService",
    "EligibilityResult",
    "PrerequisiteEdge",
    "PrerequisiteSetEvaluation",
    "RequirementEvaluation",
    "build_completed_course_index",
    "canonicalize_course_code",
    "evaluate_eligibility",
    "latest_completed_credit_courses",
    "normalize_course_code",
]
