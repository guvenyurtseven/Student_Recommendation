# Manual Corrections

Manual corrections are the controlled layer between scraped data and
student-facing data.

The important rule is:

```text
Never hand-edit generated processed files or SQLite rows.
```

Instead:

```text
scrape -> parse -> load DB -> apply manual corrections -> audit -> product use
```

## Why This Exists

The scraper can produce technically valid data that still needs academic review.
Examples currently visible in the project:

- Numeric subject-code courses such as `355 140`, `357 119`, `374 321`.
- NCC prerequisite alternatives.
- Unresolved prerequisite courses.
- Empty metadata fields such as `HIST 2202` title.
- Future elective pool decisions.

These should not become hard-coded `if` statements inside scraper code. They
should be stored as explicit, reviewable, reproducible correction records.

## Files

Correction files live in:

```text
data/manual/corrections/
  course_aliases.json
  course_overrides.json
  prerequisite_overrides.json
  curriculum_overrides.json
```

Human notes that are not yet ready to apply live in:

```text
data/manual/reviews/
```

## Apply Command

Dry-run:

```powershell
python .\scripts\apply_manual_corrections.py --dry-run
```

Apply:

```powershell
python .\scripts\apply_manual_corrections.py
```

Then regenerate reports:

```powershell
python .\scripts\audit_data_quality.py
python .\scripts\generate_course_identity_review.py
```

## Provenance

When correction files are applied, the script snapshots the correction file into:

```text
data/raw/manual_corrections/<timestamp>/
```

Then it records that snapshot in `source_documents`.

This matters because `data/manual/corrections/*.json` files are mutable working
files, while `source_documents` should point to stable content. The snapshot
prevents future edits from causing hash mismatch for old correction applications.

## Database Changes

The manual correction layer extends the database with:

```text
course_aliases.relation_type
course_aliases.review_status
course_aliases.notes
manual_correction_log
```

`manual_correction_log` records what was applied, when, from which source
document, and with what payload.

## Supported Correction Types

### Course Aliases

File:

```text
data/manual/corrections/course_aliases.json
```

Purpose:

Map an alias code to an existing canonical course.

Example:

```json
{
  "version": 1,
  "aliases": [
    {
      "alias_display_code": "355 140",
      "alias_numeric_code": "3550140",
      "canonical_display_code": "CENG 140",
      "relation_type": "ncc_equivalent",
      "review_status": "reviewed",
      "notes": "Reviewed as an NCC alternative for CENG 140."
    }
  ]
}
```

Important:

- The canonical course must already exist in `courses`.
- The script inserts every non-empty alias among `alias_display_code`,
  `alias_numeric_code`, and `alias`.
- Default application includes only `reviewed` and `corrected` entries.

### Course Overrides

File:

```text
data/manual/corrections/course_overrides.json
```

Purpose:

Update safe course metadata fields.

Supported fields:

- `title_en`
- `title_tr`
- `level`

Example:

```json
{
  "version": 1,
  "overrides": [
    {
      "match": {
        "numeric_code": "2402202"
      },
      "fields": {
        "title_en": "AUTHORITATIVE TITLE FROM SOURCE"
      },
      "review_status": "corrected",
      "notes": "Use only after checking an authoritative source."
    }
  ]
}
```

Important:

- Do not infer titles from patterns unless the correction is clearly marked as
  needing review and is not applied.
- The first implementation intentionally does not allow changing `display_code`,
  `subject_code`, or `course_number`; those are identity-level changes and need a
  more explicit migration design.

## Reserved Correction Types

These files are present and validated, but their entries are not applied yet:

```text
prerequisite_overrides.json
curriculum_overrides.json
```

If either file contains entries, `apply_manual_corrections.py` stops with an
error. This prevents us from silently pretending that prerequisite/curriculum
manual semantics are implemented before they actually are.

## Review Status Policy

Allowed statuses:

- `needs_review`
- `reviewed`
- `corrected`
- `deprecated`

Applied by default:

- `reviewed`
- `corrected`

Skipped by default:

- `needs_review`
- `deprecated`

There is an `--include-needs-review` flag for debugging, but it should not be
used in normal product data generation.

## Current Status

The correction infrastructure exists and has been tested with empty correction
files. No academic correction has been applied yet because the current review
queue still needs human decisions.

The next practical review targets are listed in:

```text
data/processed/reports/course_identity_review.md
```
