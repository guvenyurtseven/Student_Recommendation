from __future__ import annotations

import unittest

from student_planner.services.prerequisite_evaluator import PrerequisiteEdge
from student_planner.services.unlock_analysis import UnlockAnalysisService


class UnlockAnalysisServiceTests(unittest.TestCase):
    def test_analyze_direct_transitive_and_curriculum_relevant_unlocks(self) -> None:
        result = UnlockAnalysisService().analyze(
            candidate_course_codes=("MATH 120", "CENG 140"),
            prerequisite_edges=graph_edges(),
            curriculum_course_codes=("MATH 219", "CENG 384", "CENG 213"),
        )

        math120 = result.by_course_code["MATH 120"]
        self.assertEqual(math120.direct_unlock_course_codes, ("EE 281", "MATH 219"))
        self.assertEqual(math120.transitive_unlock_course_codes, ("EE 281", "MATH 219", "CENG 384"))
        self.assertEqual(math120.curriculum_relevant_unlock_course_codes, ("MATH 219", "CENG 384"))
        self.assertEqual(math120.longest_unlock_chain_length, 2)
        self.assertEqual(math120.direct_unlock_count, 2)
        self.assertEqual(math120.curriculum_relevant_unlock_count, 2)

        ceng140 = result.by_course_code["CENG 140"]
        self.assertEqual(ceng140.direct_unlock_course_codes, ("CENG 213",))
        self.assertEqual(ceng140.curriculum_relevant_unlock_course_codes, ("CENG 213",))
        self.assertGreater(math120.critical_path_score, ceng140.critical_path_score)

    def test_ranked_summaries_orders_by_unlock_value(self) -> None:
        result = UnlockAnalysisService().analyze(
            candidate_course_codes=("CENG 140", "MATH 119"),
            prerequisite_edges=graph_edges(),
            curriculum_course_codes=("MATH 120", "MATH 219", "CENG 384", "CENG 213"),
        )

        self.assertEqual(result.ranked_summaries[0].course_code, "MATH 119")
        self.assertEqual(result.by_course_code["MATH 119"].longest_unlock_chain_length, 3)

    def test_aliases_are_applied_to_graph_edges_and_candidates(self) -> None:
        result = UnlockAnalysisService(aliases={"357 119": "MATH 119"}).analyze(
            candidate_course_codes=("357 119",),
            prerequisite_edges=(
                PrerequisiteEdge("357 119", "MATH 120", set_no="2"),
                PrerequisiteEdge("MATH 120", "MATH 219", set_no="1"),
            ),
            curriculum_course_codes=("MATH 120", "MATH 219"),
        )

        summary = result.by_course_code["MATH 119"]
        self.assertEqual(summary.direct_unlock_course_codes, ("MATH 120",))
        self.assertEqual(summary.transitive_unlock_course_codes, ("MATH 120", "MATH 219"))
        self.assertEqual(summary.curriculum_relevant_unlock_count, 2)

    def test_duplicate_candidate_codes_are_ignored_after_canonicalization(self) -> None:
        result = UnlockAnalysisService().analyze(
            candidate_course_codes=("math120", "MATH 120"),
            prerequisite_edges=graph_edges(),
        )

        self.assertEqual(tuple(result.by_course_code), ("MATH 120",))


def graph_edges() -> tuple[PrerequisiteEdge, ...]:
    return (
        PrerequisiteEdge("MATH 119", "MATH 120", set_no="1"),
        PrerequisiteEdge("MATH 120", "MATH 219", set_no="1"),
        PrerequisiteEdge("MATH 120", "EE 281", set_no="1"),
        PrerequisiteEdge("MATH 219", "CENG 384", set_no="1"),
        PrerequisiteEdge("MATH 260", "CENG 384", set_no="1"),
        PrerequisiteEdge("CENG 140", "CENG 213", set_no="1"),
    )


if __name__ == "__main__":
    unittest.main()
