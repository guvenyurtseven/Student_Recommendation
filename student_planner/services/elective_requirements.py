from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from student_planner.domain.electives import ElectiveCategory, ElectiveIntent, elective_category_for_requirement_type
from student_planner.domain.planning import (
    PlanningWarning,
    PlanningWarningSeverity,
    RequirementProgress,
    RequirementProgressStatus,
    StudentPlanningInput,
)
from student_planner.services.curriculum_progress import CurriculumProgressResult


@dataclass(frozen=True)
class ElectiveCategoryPlan:
    category: ElectiveCategory
    remaining_slots: int
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
    def matched_counts_by_category(self) -> dict[str, int]:
        return {item.category.value: item.matched_count for item in self.category_plans}

    @property
    def unplanned_counts_by_category(self) -> dict[str, int]:
        return {item.category.value: item.unplanned_count for item in self.category_plans}

    @property
    def extra_counts_by_category(self) -> dict[str, int]:
        return {item.category.value: item.extra_count for item in self.category_plans}


class ElectiveRequirementPlanner:
    """Match user elective intents against remaining curriculum elective slots."""

    def build(
        self,
        planning_input: StudentPlanningInput,
        progress: CurriculumProgressResult,
    ) -> ElectiveRequirementPlan:
        remaining_slots = remaining_elective_slots(progress.requirements)
        requirement_labels = requirement_labels_by_category(progress.requirements)
        requested_counts = requested_elective_counts(planning_input.requested_elective_intents)
        categories = tuple(
            category
            for category in ElectiveCategory
            if remaining_slots.get(category, 0) > 0 or requested_counts.get(category, 0) > 0
        )

        plans = tuple(
            build_category_plan(
                category=category,
                remaining_slots=remaining_slots.get(category, 0),
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
    remaining_slots: int,
    requested_count: int,
    requirement_labels: tuple[str, ...],
) -> ElectiveCategoryPlan:
    matched = min(remaining_slots, requested_count)
    return ElectiveCategoryPlan(
        category=category,
        remaining_slots=remaining_slots,
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
