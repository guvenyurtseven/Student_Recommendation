# Data Quality Report

Generated at UTC: `2026-05-10T19:45:09+00:00`
Status: `PASS_WITH_WARNINGS`

## Summary

- Fatal findings: 0
- Warnings: 23
- Info items: 2

## Database Table Counts

| Table | Rows |
| --- | ---: |
| `course_aliases` | 0 |
| `courses` | 408 |
| `curriculum_requirements` | 696 |
| `curriculum_versions` | 13 |
| `manual_correction_log` | 0 |
| `offerings` | 31 |
| `prerequisite_edges` | 504 |
| `programs` | 14 |
| `requirement_options` | 652 |
| `source_documents` | 17 |
| `student_completed_courses` | 0 |
| `student_profiles` | 0 |

## Program Coverage

Active undergraduate programs: 13

`AE`, `CE`, `CENG`, `CHE`, `EEE`, `ENVE`, `FDE`, `GEOE`, `IE`, `ME`, `METE`, `MINE`, `PETE`

## Course Quality Metrics

```json
{
  "courses_with_null_numeric_code": 0,
  "courses_with_empty_title": 1,
  "courses_level_not_undergraduate": 0,
  "display_code_without_space": 0,
  "numeric_subject_code_courses": 35,
  "course_number_5xx_999": 1,
  "course_number_over_999": 4
}
```

## Prerequisite Quality Metrics

```json
{
  "edge_count": 504,
  "self_edges": 0,
  "edges_missing_set_no": 0,
  "edges_missing_min_grade": 0,
  "edges_missing_type": 0,
  "edges_missing_position": 0
}
```

## Review Summary

```json
{
  "curriculum_versions": {
    "scraped": 13
  },
  "curriculum_requirements": {
    "scraped": 696
  }
}
```

## Curriculum Files

| Program | Requirements | Options | Placeholders | Unique Courses |
| --- | ---: | ---: | ---: | ---: |
| AE | 55 | 50 | 11 | 50 |
| CE | 54 | 49 | 11 | 49 |
| CENG | 50 | 46 | 10 | 46 |
| CHE | 52 | 50 | 8 | 50 |
| EEE | 54 | 47 | 13 | 47 |
| ENVE | 53 | 50 | 9 | 50 |
| FDE | 52 | 49 | 9 | 49 |
| GEOE | 55 | 52 | 9 | 52 |
| IE | 56 | 53 | 9 | 53 |
| ME | 54 | 51 | 9 | 51 |
| METE | 54 | 51 | 9 | 51 |
| MINE | 53 | 52 | 7 | 52 |
| PETE | 54 | 52 | 8 | 52 |

## Per-Program Prerequisite Graphs

| Program | Nodes | Edges | Unresolved | DAG |
| --- | ---: | ---: | ---: | --- |
| AE | 67 | 47 | 13 | True |
| CE | 63 | 50 | 4 | True |
| CENG | 77 | 93 | 3 | True |
| CHE | 75 | 133 | 6 | True |
| EEE | 58 | 73 | 1 | True |
| ENVE | 74 | 84 | 5 | True |
| FDE | 80 | 126 | 9 | True |
| GEOE | 72 | 78 | 4 | True |
| IE | 74 | 65 | 7 | True |
| ME | 68 | 69 | 1 | True |
| METE | 69 | 64 | 5 | True |
| MINE | 72 | 72 | 4 | True |
| PETE | 88 | 113 | 7 | True |

## Fatal Findings

None.

## Warnings

1. **review**: curriculum_versions still contains automatically scraped records.
   - scraped: 13
2. **review**: curriculum_requirements still contains automatically scraped records.
   - scraped: 696
3. **courses**: Some courses have empty English titles.
   - HIST 2202 (2402202)
4. **course_identity**: Some courses have numeric subject display codes.
   - 219 103 (2190103): MOLECULAR AND CELLULAR BIOLOGY I
   - 219 104 (2190104): MOLECULAR AND CELLULAR BIOLOGY II
   - 355 111 (3550111): INTRODUCTION TO COMPUTER ENG. CONCEPTS
   - 355 140 (3550140): C PROGRAMMING
   - 355 213 (3550213): DATA STRUCTURES
   - 355 230 (3550230): INTRODUCTION TO C PROGRAMMING
   - 355 240 (3550240): PROGRAMMING WITH PYTHON FOR ENGINEERS
   - 355 301 (3550301): ALGORITHMS AND DATA STRUCTURES
   - 355 310 (3550310): ALGORITHMS AND DATA STRUCTURES WITH PYTHON
   - 355 350 (3550350): SOFTWARE ENGINEERING
   - 357 100 (3570100): PRECALCULUS
   - 357 119 (3570119): CALCULUS WITH ANALYTIC GEOMETRY
   - 357 120 (3570120): CALCULUS FOR FUNCTIONS OF SEVERAL VARIABLES
   - 357 219 (3570219): INTRODUCTION TO DIFFERENTIAL EQUATIONS
   - 358 105 (3580105): GENERAL PHYSICS I
   - 359 101 (3590101): DEVELOPMENT OF READING AND WRITING SKILLS I
   - 359 102 (3590102): DEVELOPMENT OF READING AND WRITING SKILLS II
   - 360 111 (3600111): GENERAL CHEMISTRY I
   - 362 201 (3620201): PRINCIPLES OF KEMAL ATATÜRK I
   - 364 221 (3640221): ENGINEERING MECHANICS I
   - 364 224 (3640224): MECHANICS OF MATERIALS
   - 365 205 (3650205): STATICS
   - 365 206 (3650206): STRENGTH OF MATERIALS
   - 365 208 (3650208): DYNAMICS
   - 374 110 (3740110): INTRODUCTION TO PETROLEUM ENGINEERING
   - 374 211 (3740211): INTRODUCTION TO FLUID MECHANICS
   - 374 216 (3740216): RESERVOIR ROCK AND FLUID PROPERTIES
   - 374 218 (3740218): RESERVOIR FLUID PROPERTIES
   - 374 220 (3740220): RESERVOIR ROCK PROPERTIES
   - 374 321 (3740321): DRILLING ENGINEERING I
   - 374 331 (3740331): PETROLEUM PRODUCTION ENGINEERING I
   - 384 261 (3840261): STATICS
   - 384 264 (3840264): MECHANICS OF MATERIALS
   - 389 140 (3890140): PROGRAMMING
   - 430 210 (4300210): PROGRAMMING LANGUAGES I
5. **courses**: 5xx-999 course numbers are present in undergraduate course table.
6. **course_identity**: NCC prerequisite alternatives are present and need product semantics.
   - 355 140 -> 355 213 (set 1, min DD)
   - 389 140 -> 355 213 (set 2, min DD)
   - 355 230 -> 355 301 (set 1, min DD)
   - 355 240 -> 355 310 (set 1, min DD)
   - 355 213 -> 355 350 (set 1, min DD)
   - 355 301 -> 355 350 (set 2, min DD)
   - 355 310 -> 355 350 (set 4, min DD)
   - 357 100 -> 357 119 (set 1, min DD)
   - 357 119 -> 357 120 (set 1, min DD)
   - 357 120 -> 357 219 (set 1, min DD)
   - 359 101 -> 359 102 (set 1, min DD)
   - 357 119 -> 364 221 (set 1, min DD)
   - 364 221 -> 364 224 (set 1, min DD)
   - 365 205 -> 364 224 (set 2, min DD)
   - 357 119 -> 365 205 (set 1, min DD)
   - 358 105 -> 365 205 (set 1, min DD)
   - 365 205 -> 365 206 (set 1, min DD)
   - 365 205 -> 365 208 (set 1, min DD)
   - 374 110 -> 374 220 (set 1, min DD)
   - 364 224 -> 374 321 (set 1, min DD)
   - 374 211 -> 374 321 (set 1, min DD)
   - 365 206 -> 374 321 (set 2, min DD)
   - 374 211 -> 374 321 (set 2, min DD)
   - 374 211 -> 374 321 (set 3, min DD)
   - 384 264 -> 374 321 (set 3, min DD)
   - 374 218 -> 374 331 (set 1, min DD)
   - 374 220 -> 374 331 (set 1, min DD)
   - 374 216 -> 374 331 (set 2, min DD)
   - 357 119 -> 384 261 (set 1, min DD)
   - 358 105 -> 384 261 (set 1, min DD)
   - 384 261 -> 384 264 (set 1, min DD)
   - 365 205 -> 384 264 (set 2, min DD)
   - 355 111 -> CENG 242 (set 2, min DD)
   - 355 213 -> CENG 242 (set 2, min DD)
   - 355 350 -> CENG 491 (set 2, min DD)
   - 360 111 -> CHEM 112 (set 6, min DD)
   - 357 120 -> CHEM 257 (set 5, min DD)
   - 359 101 -> ENG 102 (set 2, min DD)
   - 359 101 -> ENG 211 (set 3, min DD)
   - 359 102 -> ENG 211 (set 3, min DD)
   - 364 221 -> ES 224 (set 4, min DD)
   - 357 119 -> ES 303 (set 5, min DD)
   - 362 201 -> HIST 2202 (set 2, min U)
   - 357 119 -> MATH 120 (set 2, min DD)
   - 357 120 -> MATH 219 (set 2, min DD)
   - 365 208 -> ME 301 (set 2, min DD)
   - 365 206 -> ME 303 (set 2, min DD)
   - 365 206 -> ME 307 (set 2, min DD)
   - 374 321 -> PETE 322 (set 2, min DD)
   - 374 331 -> PETE 332 (set 2, min DD)
   - 357 219 -> PETE 343 (set 2, min DD)
   - 374 218 -> PETE 343 (set 2, min DD)
   - 374 220 -> PETE 343 (set 2, min DD)
   - 357 219 -> PETE 343 (set 3, min DD)
   - 374 216 -> PETE 343 (set 3, min DD)
7. **student_profiles**: student_profiles is empty.
   - This is expected before the corresponding product phase, but not ready for recommendations.
8. **student_completed_courses**: student_completed_courses is empty.
   - This is expected before the corresponding product phase, but not ready for recommendations.
9. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\engineering-latest-prerequisite-closure.json numeric_display_nodes=35
10. **prerequisites**: Engineering prerequisite closure has unresolved courses.
   - AEE 202 (5720202): not_found_in_searched_offerings
   - AEE 266 (5720266): not_found_in_searched_offerings
   - AEE 301 (5720301): not_found_in_searched_offerings
   - AEE 302 (5720302): not_found_in_searched_offerings
   - AEE 338 (5720338): not_found_in_searched_offerings
   - AEE 345 (5720345): not_found_in_searched_offerings
   - AEE 346 (5720346): not_found_in_searched_offerings
   - AEE 364 (5720364): not_found_in_searched_offerings
   - AEE 371 (5720371): not_found_in_searched_offerings
   - AEE 385 (5720385): not_found_in_searched_offerings
   - CHEM 109 (2340109): not_found_in_searched_offerings
   - CHEM 110 (2340110): not_found_in_searched_offerings
   - MATH 151 (2360151): not_found_in_searched_offerings
   - MATH 152 (2360152): not_found_in_searched_offerings
   - MATH 158 (2360158): not_found_in_searched_offerings
   - MATH 155 (2360155): not_found_in_searched_offerings
   - MATH 157 (2360157): not_found_in_searched_offerings
   - 374 216 (3740216): not_found_in_searched_offerings
   - MATH 156 (2360156): not_found_in_searched_offerings
   - IE 262 (5680262): not_found_in_searched_offerings
   - CENG 230 (5710230): not_found_in_searched_offerings
   - CENG 229 (5710229): not_found_in_searched_offerings
   - MATH 253 (2360253): not_found_in_searched_offerings
   - MATH 257 (2360257): not_found_in_searched_offerings
   - AE 122 (5720122): not_found_in_searched_offerings
   - AE 241 (5720241): not_found_in_searched_offerings
11. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\AE-latest-prerequisite-closure.json numeric_display_nodes=7
12. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\CE-latest-prerequisite-closure.json numeric_display_nodes=6
13. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\CENG-latest-prerequisite-closure.json numeric_display_nodes=16
14. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\CHE-latest-prerequisite-closure.json numeric_display_nodes=7
15. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\EEE-latest-prerequisite-closure.json numeric_display_nodes=6
16. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\ENVE-latest-prerequisite-closure.json numeric_display_nodes=9
17. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\FDE-latest-prerequisite-closure.json numeric_display_nodes=9
18. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\GEOE-latest-prerequisite-closure.json numeric_display_nodes=10
19. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\IE-latest-prerequisite-closure.json numeric_display_nodes=7
20. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\ME-latest-prerequisite-closure.json numeric_display_nodes=10
21. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\METE-latest-prerequisite-closure.json numeric_display_nodes=7
22. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\MINE-latest-prerequisite-closure.json numeric_display_nodes=10
23. **course_identity**: Prerequisite graph contains numeric display course codes.
   - data\processed\prerequisites\PETE-latest-prerequisite-closure.json numeric_display_nodes=23

## Info

1. **courses**: Course numbers above 999 are present. These may be valid undergraduate service courses.
   - HIST 2201 (2402201): PRINCIPLES OF KEMAL ATATÜRK I
   - HIST 2202 (2402202): 
   - HIST 2205 (2402205): HISTORY OF THE TURKISH REVOLUTION I
   - HIST 2206 (2402206): HISTORY OF THE TURKISH REVOLUTION II
2. **raw_catalog**: Multiple raw catalog snapshots are present for some programs.
   - AE: 2
   - CE: 2
   - CENG: 4
   - CHE: 2
   - EEE: 2
   - ENVE: 2
   - FDE: 2
   - GEOE: 2
   - IE: 2
   - ME: 2
   - METE: 2
   - MINE: 2
   - PETE: 2

## Recommended Next Actions

1. Fix all fatal findings before trusting generated data.
2. Treat warnings as review queue items before production recommendation logic.
3. Keep offering coverage visible; partial offering data must not be treated as complete.
4. Resolve course identity warnings before showing graph nodes directly to students.
