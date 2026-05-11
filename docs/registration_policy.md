# METU Undergraduate Registration Policy Layer

Last updated: 2026-05-11

Source:
https://oidb.metu.edu.tr/en/middle-east-technical-university-rules-and-regulations-governing-undergraduate-studies

This project now has a deterministic registration-policy layer in
`student_planner/services/registration_policy.py`. Its job is to make the
recommendation engine obey METU undergraduate registration constraints before a
course set is shown to a student.

## Implemented Automatically

### Prerequisites and exemptions

Relevant source rule:

- Article 17 says a prerequisite must be completed with at least `DD` or `S`.
- Article 17 also says exemption from a prerequisite/corequisite satisfies that
  requirement.

Implementation:

- `student_planner/domain/grades.py` treats `EX` like `S`.
- `student_planner/services/prerequisite_evaluator.py` uses the latest attempt of
  the direct prerequisite course.
- A failed retake of an older transitive prerequisite does not block a later
  course if the direct prerequisite has already been successfully completed.

Example:

```text
MATH 119 -> MATH 120 -> MATH 219
```

If the student passed `MATH 120`, then a later failed retake of `MATH 119` does
not block `MATH 219`, because `MATH 219` depends directly on `MATH 120`.

### Academic standing and probation

Relevant source rule:

- Article 30 says probation students may not enroll in courses they have not
  previously taken, or courses from which they earned `W`.
- Article 30 says probation students must first repeat previously taken courses,
  especially courses with `FF`, `FD`, `NA`, or `U`.

Implementation:

- Transcript parsing extracts the latest line shaped like:

```text
CumGPA: ... GPA: ... STAN: ...
```

- The parsed values are stored only as sanitized planner metadata:

```json
{
  "latest_cgpa": 2.47,
  "latest_gpa": 3.2,
  "latest_standing": "HONOR",
  "latest_standing_semester_no": "20242"
}
```

- If standing is `PROBATION`, the planner blocks:
  - courses never taken before;
  - courses whose latest attempt is `W`.

Important note:

The user-mentioned older/alternative rule that a probation student above `1.70`
CGPA may take three new courses is not present in the official page checked on
2026-05-11. The implementation therefore follows the current official page and
uses the stricter rule: probation means no new courses.

### Repeat-priority courses

Relevant source rules:

- Article 21 prioritizes courses that must be repeated.
- Article 30 prioritizes courses with `FF`, `FD`, `NA`, or `U` for probation
  students.

Implementation:

- Candidate courses whose latest grade is `FF`, `FD`, `NA`, `U`, or `W` are
  flagged as `is_repeat_priority`.
- Repeat-priority candidates are ordered before user-requested electives and
  before normal priority scoring.
- If a repeat-priority course cannot fit within the computed load cap, the
  planner emits a warning requiring advisor review.

### Course-load cap

Relevant source rule:

- Article 18 defines normal course load as the number of credit courses in the
  heaviest semester of the curriculum.
- Article 18 allows overload by:
  - `+1` course with CGPA at least `2.00`;
  - `+2` courses with CGPA at least `2.50`;
  - both require advisor approval.
- Article 18 defines the minimum course load as three credit courses, except
  graduation or advisor/department approved cases.

Implementation:

- The normal load is computed from the loaded curriculum by grouping credit
  requirements by recommended year and term.
- Scenario course sets are trimmed to the maximum allowed credit-course count:

```text
normal load + allowed overload by CGPA
```

- If a non-probation scenario has fewer than three credit courses, the planner
  keeps the scenario but emits a warning because advisor/department approval or
  a graduation exception may be needed.

### Offering-aware filtering

Relevant source rule:

- Article 7 says course offerings and sections are determined and announced by
  departments and the Registrar's Office.

Implementation:

- The planner does not predict offerings from historical data.
- Before each registration period, the project should scrape the current target
  semester SAIS offering snapshot.
- If a subject has loaded offering coverage and a candidate course is absent from
  that snapshot, the course is excluded.

## Not Yet Fully Machine-Enforced

These rules are acknowledged by the system but cannot yet be proven from the
current data model alone:

- Advisor approval: registration, add/drop, overload, and many exceptions require
  advisor approval. The tool can warn, but it cannot approve.
- Department-specific additional course criteria: Article 17 allows departments
  to define extra criteria beyond prerequisites/corequisites. These criteria are
  not yet scraped as structured data.
- Co-requisites: the prerequisite graph has a generic edge type column, but the
  current planner does not yet model "must be taken in the same semester" as a
  separate registration constraint.
- NI courses: the product does not currently recommend extra-curricular NI
  courses. If NI planning is added, Article 20's "maximum two NI courses" rule
  should become a hard cap.
- Withdrawal planning: Article 22 governs withdrawing from an already registered
  semester. This is outside the current "before registration" recommendation
  flow.
- Graduation exceptions: Article 18's minimum-load exception for graduating
  students requires a reliable graduation-completion check and advisor context.

## Product Stance

The deterministic engine should never present uncertain cases as guaranteed.
When a rule depends on missing data or advisor discretion, the product should
show the recommendation as conditionally valid and explain the required review.

The long-term goal is:

```text
candidate courses
  -> prerequisite/offering filters
  -> METU registration policy filters
  -> scoring and recommendation scenarios
  -> student-readable explanation
```

