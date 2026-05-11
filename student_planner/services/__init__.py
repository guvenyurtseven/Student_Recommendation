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
from student_planner.services.curriculum_normalization import normalize_curriculum_for_planning
from student_planner.services.difficulty import (
    CourseLoadScore,
    CourseScoringResult,
    CourseScoringService,
    SemesterLoadTarget,
)
from student_planner.services.elective_candidates import (
    ElectiveCandidateResult,
    ElectiveCandidateService,
)
from student_planner.services.elective_requirements import (
    ElectiveCategoryPlan,
    ElectiveRequirementPlan,
    ElectiveRequirementPlanner,
)
from student_planner.services.llm_report_package import (
    LLMReportPackage,
    build_llm_report_package,
    build_llm_user_message,
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
    planning_report_to_text,
    student_planning_input_to_dict,
    student_planning_input_from_dict,
)
from student_planner.services.planning_report_markdown import planning_report_to_markdown
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
from student_planner.services.registration_policy import (
    AcademicRegistrationPolicyService,
    AcademicStandingSnapshot,
    RegistrationPolicyResult,
    RegistrationPolicyState,
)
from student_planner.services.transcript_ingestion import (
    TranscriptParseResult,
    TranscriptParseWarning,
    TranscriptTextParser,
    build_planning_input_from_transcript_text,
    extract_text_from_pdf,
    extract_text_from_pdf_bytes,
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
    "AcademicRegistrationPolicyService",
    "AcademicStandingSnapshot",
    "CompletedCourse",
    "CurriculumProgressResult",
    "CurriculumProgressService",
    "CourseUnlockSummary",
    "CourseLoadScore",
    "CourseScoringResult",
    "CourseScoringService",
    "ElectiveCandidateResult",
    "ElectiveCandidateService",
    "ElectiveCategoryPlan",
    "ElectiveRequirementPlan",
    "ElectiveRequirementPlanner",
    "EligibilityResult",
    "LLMReportPackage",
    "CourseOfferingAvailability",
    "OfferingAvailabilityService",
    "OfferingAvailabilityStatus",
    "OfferingFilterResult",
    "PrerequisiteEdge",
    "PrerequisiteSetEvaluation",
    "RecommendationResult",
    "RecommendationService",
    "RegistrationPolicyResult",
    "RegistrationPolicyState",
    "RequirementEvaluation",
    "ScenarioConfig",
    "ScenarioSortMode",
    "SemesterLoadTarget",
    "SemesterPlanningPipeline",
    "TranscriptParseResult",
    "TranscriptParseWarning",
    "TranscriptTextParser",
    "UnlockAnalysisResult",
    "UnlockAnalysisService",
    "build_planning_input_from_transcript_text",
    "build_completed_course_index",
    "build_llm_report_package",
    "build_llm_user_message",
    "canonicalize_course_code",
    "evaluate_eligibility",
    "extract_text_from_pdf",
    "extract_text_from_pdf_bytes",
    "latest_completed_credit_courses",
    "load_student_planning_input",
    "normalize_course_code",
    "normalize_curriculum_for_planning",
    "planning_report_to_dict",
    "planning_report_to_markdown",
    "planning_report_to_text",
    "student_planning_input_to_dict",
    "student_planning_input_from_dict",
]
