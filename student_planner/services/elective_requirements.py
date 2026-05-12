from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from student_planner.domain.electives import ElectiveCategory, ElectiveIntent, elective_category_for_requirement_type
from student_planner.domain.planning import (
    CompletedCourseAttempt,
    PlanningWarning,
    PlanningWarningSeverity,
    RequirementProgress,
    RequirementProgressStatus,
    StudentPlanningInput,
)
from student_planner.services.curriculum_progress import CurriculumProgressResult, attempt_sort_key
from student_planner.services.prerequisite_evaluator import CourseAliases, canonicalize_course_code


ENGINEERING_SUBJECTS = {
    "AE",
    "CE",
    "CENG",
    "CHE",
    "EEE",
    "EE",
    "ENVE",
    "FDE",
    "GEOE",
    "IE",
    "ME",
    "METE",
    "MINE",
    "PETE",
}
TECHNICAL_SERVICE_SUBJECTS = {
    "BIO",
    "BIOL",
    "CHEM",
    "ES",
    "MATH",
    "PHYS",
    "STAT",
}
NONTECHNICAL_SUBJECTS = {
    "ADM",
    "ART",
    "BA",
    "ECON",
    "ENG",
    "FLE",
    "HIST",
    "IR",
    "MAN",
    "MUS",
    "PHIL",
    "POLS",
    "PSYC",
    "SOC",
    "TURK",
}


@dataclass(frozen=True)
class ElectiveCategoryPlan:
    category: ElectiveCategory
    remaining_slots: int
    completed_count: int
    requested_count: int
    matched_count: int
    unplanned_count: int
    extra_count: int
    requirement_labels: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ElectiveRequirementPlan:
    category_plans: tuple[ElectiveCategoryPlan, ...]
    warnings: tuple[PlanningWarning, ...] = field(default_factory=tuple)

    @property
    def remaining_slots_by_category(self) -> dict[str, int]:
        return {item.category.value: item.remaining_slots for item in self.category_plans}

    @property
    def requested_counts_by_category(self) -> dict[str, int]:
        return {item.category.value: item.requested_count for item in self.category_plans}

    @property
    def completed_counts_by_category(self) -> dict[str, int]:
        return {item.category.value: item.completed_count for item in self.category_plans}

    @property
    def matched_counts_by_category(self) -> dict[str, int]:
        return {item.category.value: item.matched_count for item in self.category_plans}

    @property
    def unplanned_counts_by_category(self) -> dict[str, int]:
        return {item.category.value: item.unplanned_count for item in self.category_plans}

    @property
    def extra_counts_by_category(self) -> dict[str, int]:
        return {item.category.value: item.extra_count for item in self.category_plans}

    @property
    def easy_priority_category(self) -> ElectiveCategory | None:
        completed_nontech_or_free = sum(
            plan.completed_count
            for plan in self.category_plans
            if plan.category in {ElectiveCategory.NONTECHNICAL, ElectiveCategory.FREE}
        )
        if completed_nontech_or_free > 0:
            return None
        requested_nontech_or_free = sum(
            plan.requested_count
            for plan in self.category_plans
            if plan.category in {ElectiveCategory.NONTECHNICAL, ElectiveCategory.FREE}
        )
        if requested_nontech_or_free > 0:
            return None
        by_category = {plan.category: plan for plan in self.category_plans}
        nontechnical = by_category.get(ElectiveCategory.NONTECHNICAL)
        if nontechnical and nontechnical.remaining_slots > 0:
            return ElectiveCategory.NONTECHNICAL
        free = by_category.get(ElectiveCategory.FREE)
        if free and free.remaining_slots > 0:
            return ElectiveCategory.FREE
        return None


class ElectiveRequirementPlanner:
    """Match user elective intents against remaining curriculum elective slots."""

    def build(
        self,
        planning_input: StudentPlanningInput,
        progress: CurriculumProgressResult,
        aliases: CourseAliases | None = None,
    ) -> ElectiveRequirementPlan:
        remaining_slots = remaining_elective_slots(progress.requirements)
        completed_counts = completed_elective_counts(
            planning_input=planning_input,
            progress=progress,
            aliases=aliases,
        )
        requirement_labels = requirement_labels_by_category(progress.requirements)
        requested_counts = requested_elective_counts(planning_input.requested_elective_intents)
        categories = tuple(
            category
            for category in ElectiveCategory
            if remaining_slots.get(category, 0) > 0
            or requested_counts.get(category, 0) > 0
            or completed_counts.get(category, 0) > 0
        )

        plans = tuple(
            build_category_plan(
                category=category,
                raw_remaining_slots=remaining_slots.get(category, 0),
                completed_count=completed_counts.get(category, 0),
                requested_count=requested_counts.get(category, 0),
                requirement_labels=tuple(requirement_labels.get(category, ())),
            )
            for category in categories
        )
        return ElectiveRequirementPlan(
            category_plans=plans,
            warnings=build_warnings(plans, planning_input.requested_elective_intents),
        )


def remaining_elective_slots(requirements: tuple[RequirementProgress, ...]) -> Counter[ElectiveCategory]:
    counts: Counter[ElectiveCategory] = Counter()
    for requirement in requirements:
        category = elective_category_for_requirement_type(requirement.requirement_type)
        if category is None:
            continue
        if requirement.status == RequirementProgressStatus.SATISFIED:
            continue
        counts[category] += requirement.course_count_min or 1
    return counts


def completed_elective_counts(
    planning_input: StudentPlanningInput,
    progress: CurriculumProgressResult,
    aliases: CourseAliases | None = None,
) -> Counter[ElectiveCategory]:
    curriculum_codes = concrete_curriculum_codes(progress.requirements, aliases)
    latest_attempts = latest_completed_attempts(planning_input.completed_courses, aliases)
    counts: Counter[ElectiveCategory] = Counter()
    for course_code, attempt in latest_attempts.items():
        if course_code in curriculum_codes:
            continue
        if not attempt.earns_credit:
            continue
        if attempt.credits == 0:
            continue
        counts[classify_completed_elective(attempt.course_code, planning_input.program_abbr)] += 1
    return counts


def concrete_curriculum_codes(
    requirements: tuple[RequirementProgress, ...],
    aliases: CourseAliases | None = None,
) -> set[str]:
    codes: set[str] = set()
    for requirement in requirements:
        for course_code in (
            *requirement.completed_course_codes,
            *requirement.remaining_course_codes,
            *requirement.option_course_codes,
        ):
            codes.add(canonicalize_course_code(course_code, aliases))
    return codes


def latest_completed_attempts(
    attempts: tuple[CompletedCourseAttempt, ...],
    aliases: CourseAliases | None = None,
) -> dict[str, CompletedCourseAttempt]:
    latest: dict[str, tuple[tuple[int, int, str], CompletedCourseAttempt]] = {}
    for input_index, attempt in enumerate(attempts):
        course_code = canonicalize_course_code(attempt.course_code, aliases)
        key = attempt_sort_key(attempt, input_index)
        if course_code not in latest or key >= latest[course_code][0]:
            latest[course_code] = (key, attempt)
    return {course_code: attempt for course_code, (_key, attempt) in latest.items()}


def classify_completed_elective(course_code: str, program_abbr: str) -> ElectiveCategory:
    subject = course_code.split(" ", 1)[0].upper()
    program = program_abbr.upper()
    if subject == program:
        return ElectiveCategory.TECHNICAL
    if subject in NONTECHNICAL_SUBJECTS:
        return ElectiveCategory.NONTECHNICAL
    if subject in ENGINEERING_SUBJECTS or subject in TECHNICAL_SERVICE_SUBJECTS:
        return ElectiveCategory.RESTRICTED
    return ElectiveCategory.FREE


def requirement_labels_by_category(
    requirements: tuple[RequirementProgress, ...],
) -> dict[ElectiveCategory, list[str]]:
    labels: dict[ElectiveCategory, list[str]] = {}
    for requirement in requirements:
        category = elective_category_for_requirement_type(requirement.requirement_type)
        if category is None:
            continue
        if requirement.status == RequirementProgressStatus.SATISFIED:
            continue
        labels.setdefault(category, []).append(requirement.requirement_label)
    return labels


def requested_elective_counts(intents: tuple[ElectiveIntent, ...]) -> Counter[ElectiveCategory]:
    counts: Counter[ElectiveCategory] = Counter()
    for intent in intents:
        if intent.wants_to_take:
            counts[intent.category] += intent.requested_count
    return counts


def build_category_plan(
    category: ElectiveCategory,
    raw_remaining_slots: int,
    completed_count: int,
    requested_count: int,
    requirement_labels: tuple[str, ...],
) -> ElectiveCategoryPlan:
    matched_completed = min(raw_remaining_slots, completed_count)
    remaining_slots = max(0, raw_remaining_slots - matched_completed)
    matched = min(remaining_slots, requested_count)
    return ElectiveCategoryPlan(
        category=category,
        remaining_slots=remaining_slots,
        completed_count=matched_completed,
        requested_count=requested_count,
        matched_count=matched,
        unplanned_count=max(0, remaining_slots - requested_count),
        extra_count=max(0, requested_count - remaining_slots),
        requirement_labels=requirement_labels,
    )


def build_warnings(
    plans: tuple[ElectiveCategoryPlan, ...],
    intents: tuple[ElectiveIntent, ...],
) -> tuple[PlanningWarning, ...]:
    warnings: list[PlanningWarning] = []
    for plan in plans:
        if plan.extra_count > 0 and plan.remaining_slots == 0:
            warnings.append(
                PlanningWarning(
                    code="elective_intent_without_curriculum_slot",
                    message=(
                        f"{plan.requested_count} requested {plan.category.value} item(s) do not match a "
                        "remaining curriculum elective slot in the current progress model."
                    ),
                    severity=PlanningWarningSeverity.INFO,
                )
            )
        elif plan.extra_count > 0:
            warnings.append(
                PlanningWarning(
                    code="elective_intent_exceeds_curriculum_slots",
                    message=(
                        f"{plan.extra_count} requested {plan.category.value} item(s) exceed the visible "
                        "remaining curriculum slot count."
                    ),
                    severity=PlanningWarningSeverity.INFO,
                )
            )

    explicit_intents = tuple(intent for intent in intents if intent.wants_to_take and intent.has_explicit_course)
    if explicit_intents:
        warnings.append(
            PlanningWarning(
                code="explicit_elective_category_requires_review",
                message=(
                    f"{len(explicit_intents)} explicit elective course selection(s) are treated under the "
                    "student-selected category, but category validity is not yet verified against official "
                    "elective pool lists."
                ),
                severity=PlanningWarningSeverity.INFO,
            )
        )
    return tuple(warnings)
