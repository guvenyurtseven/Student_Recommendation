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
from student_planner.services.difficulty import (
    CourseLoadScore,
    CourseScoringResult,
    CourseScoringService,
    SemesterLoadTarget,
)
from student_planner.services.offering_availability import (
    CourseOfferingAvailability,
    OfferingAvailabilityService,
    OfferingAvailabilityStatus,
    OfferingFilterResult,
)
from student_planner.services.planning_io import (
    load_student_planning_input,
    planning_report_to_dict,
    student_planning_input_from_dict,
)
from student_planner.services.planning_pipeline import SemesterPlanningPipeline
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
from student_planner.services.recommendation import (
    RecommendationResult,
    RecommendationService,
    ScenarioConfig,
    ScenarioSortMode,
)
from student_planner.services.unlock_analysis import (
    CourseUnlockSummary,
    UnlockAnalysisResult,
    UnlockAnalysisService,
)

__all__ = [
    "CandidateCourse",
    "CandidateCourseGenerator",
    "CandidateCourseResult",
    "CompletedCourse",
    "CurriculumProgressResult",
    "CurriculumProgressService",
    "CourseUnlockSummary",
    "CourseLoadScore",
    "CourseScoringResult",
    "CourseScoringService",
    "EligibilityResult",
    "CourseOfferingAvailability",
    "OfferingAvailabilityService",
    "OfferingAvailabilityStatus",
    "OfferingFilterResult",
    "PrerequisiteEdge",
    "PrerequisiteSetEvaluation",
    "RecommendationResult",
    "RecommendationService",
    "RequirementEvaluation",
    "ScenarioConfig",
    "ScenarioSortMode",
    "SemesterLoadTarget",
    "SemesterPlanningPipeline",
    "UnlockAnalysisResult",
    "UnlockAnalysisService",
    "build_completed_course_index",
    "canonicalize_course_code",
    "evaluate_eligibility",
    "latest_completed_credit_courses",
    "load_student_planning_input",
    "normalize_course_code",
    "planning_report_to_dict",
    "student_planning_input_from_dict",
]
