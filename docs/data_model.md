# Data Model

## Layers

The data model separates these concerns:

- Catalog identity: departments, programs, courses.
- Curriculum: what a student must complete.
- Prerequisites: course dependency graph.
- Offerings: which courses opened in which semester.
- Student planning: completed courses and recommendations.
- Provenance: where each fact came from and whether it was reviewed.

## Main Entities

### programs

Represents an undergraduate program or department target.

Important fields:

- `code`: internal abbreviation, such as `CENG`.
- `catalog_program_id`: METU numeric program id, such as `571`.
- `name_en`, `name_tr`.
- `faculty`.
- `is_active_undergraduate`.

### courses

Canonical course records.

Important fields:

- `numeric_code`: SAIS/METU numeric code, such as `5710213`.
- `subject_code`: `CENG`.
- `course_number`: `213`.
- `display_code`: `CENG 213`.
- `title_en`, `title_tr`.
- `level`.

### curriculum_versions

Represents a version of a program curriculum.

For the first product version we use only the latest known curriculum, but this
table is designed so entrance-year-specific versions can be added later.

Important fields:

- `program_id`
- `version_label`
- `effective_from_year`
- `effective_to_year`
- `is_latest`
- `review_status`
- `source_document_id`

### curriculum_requirements

Represents a requirement slot in a curriculum.

Examples:

- `required_course`
- `technical_elective_pool`
- `nontechnical_elective_pool`
- `free_elective_pool`
- `summer_practice`

Important fields:

- `curriculum_version_id`
- `requirement_type`
- `recommended_year`
- `recommended_term`
- `credits_min`
- `ects_min`
- `course_count_min`

### requirement_options

Connects a requirement to concrete courses or course groups.

For a must course, one requirement has one option.
For an elective pool, one requirement may have many options.

### prerequisite_edges

Stores directed edges:

```text
prerequisite_course_id -> course_id
```

Important fields:

- `set_no`
- `min_grade`
- `source_document_id`
- `is_equivalent_option`

### offerings

Stores course offerings by semester. This is separate from curriculum.

Important fields:

- `course_id`
- `semester_no`
- `department_program_id`
- `source_document_id`

## Recommended SQLite Schema

See [student_planner/db/schema.sql](../student_planner/db/schema.sql).

## Review Status Values

Use these values consistently:

- `scraped`: extracted automatically, not checked.
- `needs_review`: parser saw ambiguity.
- `reviewed`: human checked and accepted.
- `corrected`: human corrected automated output.
- `deprecated`: old version, kept for history.

