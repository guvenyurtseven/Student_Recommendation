# Curriculum Scrape Review Report

Status: automatically scraped, requires human review before production use.

Programs scraped: 13
Total requirement slots: 696
Sum of per-program unique course counts: 652

| Program | Requirements | Unique courses | Course option rows | Placeholder requirements |
| --- | ---: | ---: | ---: | ---: |
| CENG | 50 | 46 | 46 | 10 |
| ENVE | 53 | 50 | 50 | 9 |
| EEE | 54 | 47 | 47 | 13 |
| IE | 56 | 53 | 53 | 9 |
| FDE | 52 | 49 | 49 | 9 |
| AE | 55 | 50 | 50 | 11 |
| CE | 54 | 49 | 49 | 11 |
| GEOE | 55 | 52 | 52 | 9 |
| CHE | 52 | 50 | 50 | 8 |
| MINE | 53 | 52 | 52 | 7 |
| ME | 54 | 51 | 51 | 9 |
| METE | 54 | 51 | 51 | 9 |
| PETE | 54 | 52 | 52 | 8 |

## Required Manual Checks

- Confirm each curriculum is the latest applicable undergraduate curriculum.
- Confirm elective placeholders are semantically correct.
- Confirm course-choice groups such as HIST/TURK alternatives are represented correctly.
- Confirm service courses from other departments are present.
- Confirm no department-specific website has a newer curriculum than Catalog.

## Source

Primary source is METU Academic Catalog `program.php?fac_prog=<program_id>` pages.
