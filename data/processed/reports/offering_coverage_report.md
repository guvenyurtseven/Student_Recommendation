# Offering Coverage Report

Status: generated from the local SQLite database.

## Summary

- Coverage scope: 20252
- Loaded semesters: 1
- Loaded offering rows: 654
- Latest-curriculum concrete course references: 652
- Curriculum course references seen in loaded offerings: 508
- Curriculum course references not seen in loaded offerings: 144
- Curriculum subject codes without loaded offering coverage: 0

## Offering Counts By Semester

| Semester | Offerings |
| --- | ---: |
| 20252 | 654 |

## Subject Coverage

| Subject | Curriculum Courses | Programs Using Subject | Offered Courses | Offered Semesters |
| --- | ---: | ---: | ---: | --- |
| BA | 1 | 13 | 46 | 20252 |
| CENG | 22 | 13 | 30 | 20252 |
| ENG | 3 | 13 | 10 | 20252 |
| HIST | 4 | 13 | 34 | 20252 |
| IS | 1 | 13 | 3 | 20252 |
| MATH | 6 | 13 | 38 | 20252 |
| OHS | 2 | 13 | 2 | 20252 |
| PHYS | 3 | 13 | 40 | 20252 |
| TURK | 6 | 13 | 14 | 20252 |
| CHEM | 7 | 12 | 39 | 20252 |
| ME | 27 | 9 | 36 | 20252 |
| ES | 7 | 8 | 7 | 20252 |
| ECON | 3 | 6 | 38 | 20252 |
| EE | 23 | 5 | 14 | 20252 |
| METE | 24 | 5 | 27 | 20252 |
| CE | 26 | 4 | 51 | 20252 |
| CHE | 18 | 4 | 20 | 20252 |
| GEOE | 26 | 4 | 25 | 20252 |
| BIOL | 2 | 2 | 33 | 20252 |
| MINE | 18 | 2 | 16 | 20252 |
| AEE | 22 | 1 | 7 | 20252 |
| ENVE | 18 | 1 | 19 | 20252 |
| FDE | 17 | 1 | 22 | 20252 |
| IE | 21 | 1 | 19 | 20252 |
| PETE | 17 | 1 | 18 | 20252 |
| AE | 0 | 0 | 22 | 20252 |
| EEE | 0 | 0 | 24 | 20252 |

## Missing High-Impact Service Subjects

If any rows appear below, those curriculum subjects have no loaded offering rows in this scope.

| Subject | Curriculum Courses | Programs |
| --- | ---: | --- |
| - | 0 | All curriculum subjects have loaded offering coverage in this scope. |

## Next Data Actions

1. For the next planning cycle, scrape one fresh target-semester snapshot after SAIS updates offerings.
2. Load only that target semester with `scripts/load_offerings.py --semesters <TARGET> --clear-existing --prune-orphan-non-undergraduate-courses`.
3. Re-run this report with `--semesters <TARGET>` and then run the data quality audit.
