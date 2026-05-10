from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from student_planner.services.prerequisite_evaluator import (
    CourseAliases,
    PrerequisiteEdge,
    canonicalize_course_code,
)


@dataclass(frozen=True)
class CourseUnlockSummary:
    course_code: str
    direct_unlock_course_codes: tuple[str, ...]
    transitive_unlock_course_codes: tuple[str, ...]
    curriculum_relevant_unlock_course_codes: tuple[str, ...]
    longest_unlock_chain_length: int
    critical_path_score: float

    @property
    def direct_unlock_count(self) -> int:
        return len(self.direct_unlock_course_codes)

    @property
    def transitive_unlock_count(self) -> int:
        return len(self.transitive_unlock_course_codes)

    @property
    def curriculum_relevant_unlock_count(self) -> int:
        return len(self.curriculum_relevant_unlock_course_codes)


@dataclass(frozen=True)
class UnlockAnalysisResult:
    summaries: tuple[CourseUnlockSummary, ...]

    @property
    def by_course_code(self) -> dict[str, CourseUnlockSummary]:
        return {summary.course_code: summary for summary in self.summaries}

    @property
    def ranked_summaries(self) -> tuple[CourseUnlockSummary, ...]:
        return tuple(
            sorted(
                self.summaries,
                key=lambda summary: (
                    -summary.critical_path_score,
                    -summary.curriculum_relevant_unlock_count,
                    -summary.transitive_unlock_count,
                    summary.course_code,
                ),
            )
        )


class UnlockAnalysisService:
    """Compute graph-based unlock potential for candidate courses.

    The service follows the project graph direction: prerequisite -> course.
    It measures downstream dependency potential, not guaranteed future
    eligibility. A dependent course may still require other prerequisites.
    """

    def __init__(self, aliases: CourseAliases | None = None) -> None:
        self.aliases = aliases or {}

    def analyze(
        self,
        candidate_course_codes: Iterable[str],
        prerequisite_edges: Iterable[PrerequisiteEdge],
        curriculum_course_codes: Iterable[str] = (),
    ) -> UnlockAnalysisResult:
        candidates = canonical_unique(candidate_course_codes, self.aliases)
        curriculum_relevant = set(canonical_unique(curriculum_course_codes, self.aliases))
        graph = PrerequisiteGraph.from_edges(prerequisite_edges, self.aliases)
        summaries = tuple(
            self.summarize_course(course_code, graph, curriculum_relevant)
            for course_code in candidates
        )
        return UnlockAnalysisResult(summaries=summaries)

    def summarize_course(
        self,
        course_code: str,
        graph: "PrerequisiteGraph",
        curriculum_relevant: set[str],
    ) -> CourseUnlockSummary:
        direct = graph.direct_dependents(course_code)
        transitive = graph.transitive_dependents(course_code)
        relevant = tuple(course for course in transitive if course in curriculum_relevant)
        longest_chain = graph.longest_chain_length_from(course_code)
        score = critical_path_score(
            direct_count=len(direct),
            transitive_count=len(transitive),
            curriculum_relevant_count=len(relevant),
            longest_chain_length=longest_chain,
        )
        return CourseUnlockSummary(
            course_code=course_code,
            direct_unlock_course_codes=direct,
            transitive_unlock_course_codes=transitive,
            curriculum_relevant_unlock_course_codes=relevant,
            longest_unlock_chain_length=longest_chain,
            critical_path_score=score,
        )


@dataclass(frozen=True)
class PrerequisiteGraph:
    adjacency: dict[str, tuple[str, ...]]

    @classmethod
    def from_edges(
        cls,
        prerequisite_edges: Iterable[PrerequisiteEdge],
        aliases: CourseAliases | None = None,
    ) -> "PrerequisiteGraph":
        adjacency_sets: dict[str, set[str]] = {}
        for edge in prerequisite_edges:
            prerequisite = canonicalize_course_code(edge.prerequisite_course_code, aliases)
            dependent = canonicalize_course_code(edge.course_code, aliases)
            if prerequisite == dependent:
                continue
            adjacency_sets.setdefault(prerequisite, set()).add(dependent)
            adjacency_sets.setdefault(dependent, set())
        return cls(
            adjacency={
                course_code: tuple(sorted(dependents))
                for course_code, dependents in adjacency_sets.items()
            }
        )

    def direct_dependents(self, course_code: str) -> tuple[str, ...]:
        return self.adjacency.get(course_code, ())

    def transitive_dependents(self, course_code: str) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        queue: deque[str] = deque(self.direct_dependents(course_code))
        while queue:
            current = queue.popleft()
            if current == course_code or current in seen:
                continue
            seen.add(current)
            ordered.append(current)
            for dependent in self.direct_dependents(current):
                if dependent not in seen:
                    queue.append(dependent)
        return tuple(ordered)

    def longest_chain_length_from(self, course_code: str) -> int:
        memo: dict[str, int] = {}

        def visit(node: str, visiting: set[str]) -> int:
            if node in memo:
                return memo[node]
            if node in visiting:
                return 0
            visiting.add(node)
            best = 0
            for dependent in self.direct_dependents(node):
                best = max(best, 1 + visit(dependent, visiting))
            visiting.remove(node)
            memo[node] = best
            return best

        return visit(course_code, set())


def canonical_unique(course_codes: Iterable[str], aliases: CourseAliases | None = None) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for course_code in course_codes:
        canonical = canonicalize_course_code(course_code, aliases)
        if canonical not in seen:
            seen.add(canonical)
            ordered.append(canonical)
    return tuple(ordered)


def critical_path_score(
    direct_count: int,
    transitive_count: int,
    curriculum_relevant_count: int,
    longest_chain_length: int,
) -> float:
    return (
        direct_count
        + (0.25 * transitive_count)
        + (2.0 * curriculum_relevant_count)
        + (0.5 * longest_chain_length)
    )
