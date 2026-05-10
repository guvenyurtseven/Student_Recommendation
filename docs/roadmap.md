# Roadmap

## Phase 0: Foundation

Goal: Create maintainable structure before adding more scrapers.

Deliverables:

- Project layout.
- SQLite schema.
- Engineering program config.
- Architecture docs.
- Data import conventions.

## Phase 1: Curriculum Ingestion

Goal: Get latest curricula for target engineering programs.

Deliverables:

- Catalog source adapter.
- Curriculum parser.
- Review reports.
- SQLite persistence.

## Phase 2: Prerequisite Closure

Goal: Build full prerequisite graph from curriculum seed courses, not only
department-offered courses.

Deliverables:

- Recursive prerequisite scraper.
- DAG validation.
- AND/OR prerequisite set preservation.
- External service-course nodes.

## Phase 3: Student Planning Logic

Goal: Produce recommendations from completed courses and curriculum graph.

Inputs:

- Program.
- Completed courses.
- Optional failed/in-progress courses.
- Target semester.

Outputs:

- Available required courses.
- Blocked required courses with explanations.
- High-unlock-value courses.
- Risk warnings.
- Suggested next semester basket.

## Phase 4: UI Prototype

Goal: Make this usable by students.

Views:

- Curriculum progress.
- Course graph.
- "Why can't I take this?" explanation.
- Next-semester recommendation.

