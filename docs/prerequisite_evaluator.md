# Prerequisite Evaluator

The prerequisite evaluator answers:

```text
Can a student take this course, given completed courses and grades?
```

Implementation:

```text
student_planner/services/prerequisite_evaluator.py
tests/test_prerequisite_evaluator.py
```

## Core Semantics

SAIS prerequisite rows are evaluated by `set_no`.

```text
Same set_no     => AND
Different set_no => OR
```

Example:

```text
set 1:
  MATH 219
  MATH 260
```

means both courses are required.

Example:

```text
set 1:
  MATH 119

set 2:
  357 119
```

means either set can satisfy the prerequisite.

This is the current working model and is covered by unit tests. It should still
be reviewed against more real SAIS examples before production use.

## Main Types

```python
CompletedCourse
PrerequisiteEdge
RequirementEvaluation
PrerequisiteSetEvaluation
EligibilityResult
```

`PrerequisiteEdge` follows the project graph direction:

```text
prerequisite -> course
```

## Repeated Courses

The evaluator supports repeated course attempts.

If the same course appears more than once in completed course input, the latest
attempt wins. Latest is decided by:

1. `attempt_order`, when provided.
2. `completed_semester_no`, when provided.
3. input order as fallback.

This matters for chains such as:

```text
MATH 119 -> MATH 120 -> MATH 219
```

To evaluate whether a student can take `MATH 219`, only the direct prerequisite
record for `MATH 219` is checked. If `MATH 120` is currently at least `DD`, a
later failed repeat of `MATH 119` does not block `MATH 219`.

However, if the target is `MATH 120`, then the latest attempt of direct
prerequisite `MATH 119` is used.

## Main Function

```python
evaluate_eligibility(
    target_course_code,
    prerequisite_edges,
    completed_courses,
    aliases=None,
)
```

Inputs:

- `target_course_code`: course to evaluate.
- `prerequisite_edges`: prerequisite rows for one or more courses.
- `completed_courses`: either a mapping like `{"MATH 119": "DD"}` or a list of
  `CompletedCourse`.
- `aliases`: optional mapping from alias code to canonical code.

Output:

- `is_eligible`
- `satisfied_set_nos`
- `missing_by_set`
- `set_evaluations`
- `explanation`

## Course Code Normalization

The evaluator normalizes user-friendly input:

```text
ceng140       -> CENG 140
CENG   140    -> CENG 140
355 140       -> 355 140
5710140       -> 5710140
```

Aliases can map numeric/NCC/old codes to canonical codes:

```python
aliases = {
    "355 140": "CENG 140",
    "5710140": "CENG 140",
}
```

## SQLite Repository

The evaluator is pure logic. Real DB integration starts in:

```text
student_planner/repositories/sqlite.py
tests/test_sqlite_repository.py
```

`SQLiteStudentPlannerRepository` can:

- build an alias map from `courses` and `course_aliases`
- fetch prerequisite edges for a target course
- evaluate target course eligibility using DB edges

Example:

```python
from student_planner.repositories.sqlite import SQLiteStudentPlannerRepository
from student_planner.services.prerequisite_evaluator import CompletedCourse

repo = SQLiteStudentPlannerRepository("data/db/student_planner.sqlite")
result = repo.evaluate_course_eligibility(
    "MATH 219",
    completed_courses=[
        CompletedCourse("MATH 119", "DD", attempt_order=1),
        CompletedCourse("MATH 120", "DD", attempt_order=2),
        CompletedCourse("MATH 119", "FF", attempt_order=3),
    ],
)
```

## Grade Handling

Grade comparisons use:

```text
student_planner/domain/grades.py
```

Important policy:

- `NA` behaves like `FF`.
- `EX` behaves like `S`.
- `W` never satisfies a prerequisite.
- `U` satisfies explicit `U` minimums because SAIS uses `U` on some S/U rows.

## Example

```python
from student_planner.services.prerequisite_evaluator import (
    PrerequisiteEdge,
    evaluate_eligibility,
)

result = evaluate_eligibility(
    "CENG 384",
    prerequisite_edges=[
        PrerequisiteEdge("MATH 219", "CENG 384", set_no="1", min_grade="DD"),
        PrerequisiteEdge("MATH 260", "CENG 384", set_no="1", min_grade="DD"),
    ],
    completed_courses={"MATH 219": "CB"},
)

assert not result.is_eligible
assert result.missing_by_set["1"][0].prerequisite_course_code == "MATH 260"
```

## Test Command

```powershell
python -m unittest discover -s tests -v
```

Current coverage includes:

- no-prerequisite courses
- single prerequisite
- insufficient grade
- same-set AND logic
- different-set OR logic
- S/U/EX behavior
- withdrawal behavior
- alias normalization
- duplicate completed-course rejection
