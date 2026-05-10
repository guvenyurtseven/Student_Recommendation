# Curriculum Ingestion Plan

## Why This Is The Next Milestone

The current prerequisite graphs start from courses offered by a department in two
semesters. That is useful, but it does not equal a student's curriculum.

Many required courses are service courses from other departments:

- MATH119, MATH120, MATH219, MATH260
- PHYS105, PHYS106
- ENG101, ENG102, ENG211
- EE281
- CENG240 for non-CENG engineering programs

Therefore the next milestone is to scrape and normalize the latest curriculum
for each target engineering program.

## Target Programs

ODTU's official undergraduate programs page currently lists Ankara-campus
Faculty of Engineering undergraduate programs such as Computer Engineering,
Environmental Engineering, Electrical and Electronics Engineering, Industrial
Engineering, Food Engineering, Aerospace Engineering, Civil Engineering,
Geological Engineering, Chemical Engineering, Mining Engineering, Mechanical
Engineering, Metallurgical and Materials Engineering, and Petroleum and Natural
Gas Engineering.

Source: https://www.metu.edu.tr/tr/lisans-programlari

The project config also leaves room for faculty departments that may not have an
active undergraduate curriculum target.

## Source Priority

1. METU Academic Catalog program pages.
2. METU Catalog program outcome/course matrix pages.
3. Department official curriculum pages.
4. Department PDFs.
5. Manual corrections.

Known useful Catalog URLs:

```text
https://catalog.metu.edu.tr/program.php?fac_prog=<program_id>
https://catalog.metu.edu.tr/prog_courses.php?prog=<program_id>
https://catalog.metu.edu.tr/prog_out_course_matrix.php?prog=<program_id>
```

## Extraction Strategy

Phase 1: Discover program metadata.

- Load `config/engineering_programs.json`.
- Fetch official Catalog pages.
- Store raw HTML snapshots in `data/raw/catalog/<program>/<date>/`.

Phase 2: Parse latest curriculum candidates.

- Extract course-like tokens: `CENG213`, `MATH119`, `PHYS105`.
- Extract recommended year/term if present.
- Extract requirement labels: must, elective, technical elective, summer practice.
- Resolve each token into canonical course records.

Phase 3: Manual review report.

Each program should generate:

- `data/processed/curricula/<abbr>-latest.curriculum.json`
- `data/processed/reports/<abbr>-curriculum-review.md`

The review report should include unresolved tokens and suspicious duplicates.

Phase 4: Store in SQLite.

- Insert source document record.
- Upsert courses.
- Insert curriculum version.
- Insert requirements and options.
- Mark status as `scraped` or `needs_review`.

Phase 5: Expand prerequisite closure.

Starting from curriculum courses, recursively scrape prerequisites until no new
undergraduate prerequisite courses appear.

This solves chains like:

```text
MATH119 -> MATH120 -> MATH219 -> CENG384
MATH119 -> MATH120 -> EE281
```

## Manual Review Rules

An automatically scraped curriculum is not final until:

- Required service courses are present.
- Elective placeholders are represented as categories, not fake courses.
- Course codes resolve to known Catalog/SAIS courses.
- Latest curriculum assumption is documented.
- The reviewer signs off in the database or review report.

