from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from student_planner.domain.models import CurriculumSnapshot, RequirementType
from student_planner.services.curriculum_normalization import ENGINEERING_PROGRAM_ABBRS
from student_planner.services.prerequisite_evaluator import (
    CourseAliases,
    PrerequisiteEdge,
    canonicalize_course_code,
)


PRACTICE_RULE_EDGE_TYPE = "product_rule"
PRACTICE_RULE_POSITION = "engineering_summer_practice"
OHS_301 = "OHS 301"


@dataclass(frozen=True)
class EngineeringPracticeChain:
    practice_300_code: str | None = None
    practice_400_code: str | None = None


def augment_prerequisite_edges_by_course(
    edges_by_course: Mapping[str, list[PrerequisiteEdge] | tuple[PrerequisiteEdge, ...]],
    curriculum: CurriculumSnapshot,
    aliases: CourseAliases | None = None,
) -> dict[str, list[PrerequisiteEdge]]:
    """Inject engineering summer-practice product rules into candidate edges.

    Rules:

    - If the curriculum has OHS 301 and a 300-level summer practice, OHS 301 is
      required before that summer practice.
    - If the curriculum has matching 300 and 400 summer practices with the same
      subject code, the 300-level practice is required before the 400-level one.

    If a target course already has prerequisite alternatives, the synthetic
    prerequisite is added to every existing set so it acts as an additional
    requirement, not as a new alternative.
    """

    normalized = {
        canonicalize_course_code(course_code, aliases): list(edges)
        for course_code, edges in edges_by_course.items()
    }
    for edge in synthetic_engineering_practice_edges(curriculum, normalized, aliases):
        normalized.setdefault(canonicalize_course_code(edge.course_code, aliases), []).append(edge)
    return normalized


def augment_all_prerequisite_edges(
    edges: tuple[PrerequisiteEdge, ...] | list[PrerequisiteEdge],
    curriculum: CurriculumSnapshot,
    aliases: CourseAliases | None = None,
) -> tuple[PrerequisiteEdge, ...]:
    grouped: dict[str, list[PrerequisiteEdge]] = {}
    for edge in edges:
        grouped.setdefault(canonicalize_course_code(edge.course_code, aliases), []).append(edge)
    augmented = augment_prerequisite_edges_by_course(grouped, curriculum, aliases)
    return tuple(
        edge
        for course_code in sorted(augmented)
        for edge in augmented[course_code]
    )


def synthetic_engineering_practice_edges(
    curriculum: CurriculumSnapshot,
    edges_by_course: Mapping[str, list[PrerequisiteEdge] | tuple[PrerequisiteEdge, ...]],
    aliases: CourseAliases | None = None,
) -> tuple[PrerequisiteEdge, ...]:
    if curriculum.program.abbr.upper() not in ENGINEERING_PROGRAM_ABBRS:
        return ()

    chains = engineering_practice_chains(curriculum)
    if not chains:
        return ()

    curriculum_codes = {canonicalize_course_code(course_code, aliases) for course_code in curriculum.concrete_course_codes}
    has_ohs = canonicalize_course_code(OHS_301, aliases) in curriculum_codes
    synthetic: list[PrerequisiteEdge] = []
    for chain in chains:
        if has_ohs and chain.practice_300_code:
            synthetic.extend(
                required_edges_for_target(
                    prerequisite_code=OHS_301,
                    target_code=chain.practice_300_code,
                    edges_by_course=edges_by_course,
                    aliases=aliases,
                )
            )
        if chain.practice_300_code and chain.practice_400_code:
            synthetic.extend(
                required_edges_for_target(
                    prerequisite_code=chain.practice_300_code,
                    target_code=chain.practice_400_code,
                    edges_by_course=edges_by_course,
                    aliases=aliases,
                )
            )
    return tuple(synthetic)


def engineering_practice_chains(curriculum: CurriculumSnapshot) -> tuple[EngineeringPracticeChain, ...]:
    by_subject: dict[str, dict[int, str]] = {}
    for requirement in curriculum.requirements:
        if requirement.requirement_type != RequirementType.SUMMER_PRACTICE:
            continue
        for option in requirement.options:
            if option.course is None:
                continue
            if option.course.course_number not in {300, 400}:
                continue
            by_subject.setdefault(option.course.subject_code.upper(), {})[option.course.course_number] = (
                option.course.display_code
            )

    return tuple(
        EngineeringPracticeChain(
            practice_300_code=courses.get(300),
            practice_400_code=courses.get(400),
        )
        for _subject, courses in sorted(by_subject.items())
        if courses.get(300) or courses.get(400)
    )


def required_edges_for_target(
    prerequisite_code: str,
    target_code: str,
    edges_by_course: Mapping[str, list[PrerequisiteEdge] | tuple[PrerequisiteEdge, ...]],
    aliases: CourseAliases | None = None,
) -> tuple[PrerequisiteEdge, ...]:
    target = canonicalize_course_code(target_code, aliases)
    prerequisite = canonicalize_course_code(prerequisite_code, aliases)
    existing_edges = tuple(edges_by_course.get(target, ()))
    set_nos = tuple(dict.fromkeys(str(edge.set_no) for edge in existing_edges)) or ("1",)
    synthetic: list[PrerequisiteEdge] = []
    for set_no in set_nos:
        if prerequisite_exists(existing_edges, prerequisite, set_no, aliases):
            continue
        synthetic.append(
            PrerequisiteEdge(
                prerequisite_course_code=prerequisite,
                course_code=target,
                set_no=set_no,
                min_grade="DD",
                edge_type=PRACTICE_RULE_EDGE_TYPE,
                position=PRACTICE_RULE_POSITION,
            )
        )
    return tuple(synthetic)


def prerequisite_exists(
    edges: tuple[PrerequisiteEdge, ...],
    prerequisite_code: str,
    set_no: str,
    aliases: CourseAliases | None = None,
) -> bool:
    return any(
        str(edge.set_no) == str(set_no)
        and canonicalize_course_code(edge.prerequisite_course_code, aliases) == prerequisite_code
        for edge in edges
    )
