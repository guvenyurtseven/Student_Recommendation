from __future__ import annotations

from dataclasses import replace

from student_planner.domain.models import CurriculumRequirementRecord, CurriculumSnapshot, RequirementType


ENGINEERING_PROGRAM_ABBRS = {
    "AE",
    "CE",
    "CENG",
    "CHE",
    "EEE",
    "ENVE",
    "FDE",
    "GEOE",
    "IE",
    "ME",
    "METE",
    "MINE",
    "PETE",
}
TURK_FALL_OPTIONS = {"TURK 105", "TURK 201", "TURK 303"}
TURK_SPRING_OPTIONS = {"TURK 106", "TURK 202", "TURK 304"}
HIST_FALL_OPTIONS = {"HIST 2201", "HIST 2205"}
HIST_SPRING_OPTIONS = {"HIST 2202", "HIST 2206"}


def normalize_curriculum_for_planning(curriculum: CurriculumSnapshot) -> CurriculumSnapshot:
    """Apply product-level curriculum normalization without mutating raw data.

    METU catalog exposes Turkish language and history requirements as
    alternative sets. For this planner's engineering product scope, we
    intentionally keep only TURK 303/304 and HIST 2201/2202 so the UI and
    recommendation engine do not suggest multiple variants.
    """

    if curriculum.program.abbr.upper() not in ENGINEERING_PROGRAM_ABBRS:
        return curriculum
    normalized_requirements = tuple(normalize_engineering_requirement(requirement) for requirement in curriculum.requirements)
    return replace(curriculum, requirements=normalized_requirements)


def normalize_engineering_requirement(
    requirement: CurriculumRequirementRecord,
) -> CurriculumRequirementRecord:
    option_codes = set(requirement.option_course_codes)
    if option_codes == TURK_FALL_OPTIONS:
        return keep_single_option(
            requirement=requirement,
            course_code="TURK 303",
            recommended_term="Fall",
        )
    if option_codes == TURK_SPRING_OPTIONS:
        return keep_single_option(
            requirement=requirement,
            course_code="TURK 304",
            recommended_term="Spring",
        )
    if option_codes == HIST_FALL_OPTIONS:
        return keep_single_option(
            requirement=requirement,
            course_code="HIST 2201",
            recommended_term="Fall",
        )
    if option_codes == HIST_SPRING_OPTIONS:
        return keep_single_option(
            requirement=requirement,
            course_code="HIST 2202",
            recommended_term="Spring",
        )
    return requirement


def keep_single_option(
    requirement: CurriculumRequirementRecord,
    course_code: str,
    recommended_term: str,
) -> CurriculumRequirementRecord:
    selected_options = tuple(
        option
        for option in requirement.options
        if option.course_code == course_code
    )
    if not selected_options:
        return requirement
    return replace(
        requirement,
        requirement_type=RequirementType.REQUIRED_COURSE,
        label=course_code,
        recommended_term=recommended_term,
        course_count_min=1,
        options=selected_options,
    )
