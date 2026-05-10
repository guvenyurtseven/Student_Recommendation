# Architecture

## Product Goal

Build a student-facing course planning assistant for METU students. The first
useful version should answer:

- Which required curriculum courses remain?
- Which courses are currently unlocked by completed prerequisites?
- Which courses unlock the most future courses?
- Which prerequisite chain is blocking a target course?
- What is a sensible next-semester recommendation?

The system must eventually support multiple departments and curriculum versions,
but the first version will target the latest curriculum only.

## Core Principle

Do not model "courses offered by a department" as the curriculum. A curriculum is
the set of courses and requirement categories that a student in a program must
complete. Offered-course data and prerequisite data are separate layers.

The architecture therefore has two graph-like layers:

1. Curriculum layer
   - Required courses, elective pools, category requirements, semester placement.
   - Example: CENG curriculum requires MATH119, MATH120, PHYS105, CENG213.

2. Prerequisite layer
   - Directed edges from prerequisite to dependent course.
   - Example: MATH119 -> MATH120 -> MATH219 -> CENG384.

Recommendation uses both layers:

- Curriculum says what matters for the degree.
- Prerequisites say what can be taken and what gets unlocked.
- Offerings say whether a course is likely available in a given semester.

## Proposed Package Layout

```text
student_planner/
  domain/             Pure domain models and graph logic.
  sources/            Source adapters for METU Catalog, SAIS, PDFs, department pages.
  repositories/       Database read/write implementations.
  services/           Application services: curriculum build, prerequisite build, recommendation.
  db/                 SQLite schema and bootstrap helpers.
config/               Program metadata and source configuration.
data/
  raw/                Immutable-ish source snapshots.
  processed/          Normalized artifacts and exported graphs.
  db/                 SQLite database files.
scripts/              Small CLI entrypoints.
docs/                 Architecture and planning docs.
```

Existing root-level scripts can keep working during the transition. New work
should go into `student_planner/` and `scripts/`.

## Source Adapter Pattern

Each source adapter should implement a small interface:

```python
class CurriculumSource:
    def fetch(self, program: Program) -> SourceSnapshot: ...
    def parse(self, snapshot: SourceSnapshot) -> CurriculumDraft: ...
```

This gives us SOLID-friendly separation:

- Fetching is not parsing.
- Source-specific parsing does not leak into the domain model.
- The recommendation engine never knows whether data came from Catalog, SAIS, PDF, or a department site.

Recommended source priority:

1. METU Academic Catalog
2. METU SAIS / OIBS screens
3. Department official curriculum pages
4. Curriculum PDFs
5. Manually reviewed corrections

## Initial Database Choice

Use SQLite first.

Reasons:

- Zero service setup.
- Works well for local scraping and validation.
- Easy to move to PostgreSQL later if the app becomes multi-user.
- Supports relational constraints, which are useful for curriculum consistency.

The database is not the source of truth for scraping code. The source of truth is:

- Source snapshots in `data/raw`
- Normalized records in DB
- Manual review status and provenance fields

## Important Product Concepts

### Course

A course is canonical by numeric METU code when available, for example `5710213`.
Display code is separate, for example `CENG 213`.

### Requirement

A curriculum requirement is not always a single course.

Examples:

- Must take CENG213.
- Choose 1 technical elective.
- Choose 2 non-technical electives.
- Complete summer practice.

### Prerequisite Set

Prerequisites can have alternatives. We must preserve `set_no` from SAIS.

Example:

```text
set 1: CENG213
set 2: CENG301
```

This should not be flattened into a vague list if we want accurate "can I take this?" logic.

## Validation Philosophy

Every automated curriculum extraction should produce a review report:

- Source URL and retrieval timestamp.
- Number of required courses found.
- Elective/category requirements found.
- Courses that could not be resolved to a canonical course.
- Differences from previous scrape.
- Manual review status.

No curriculum should be marked production-ready before review.

