# Course Identity Review

Generated at UTC: `2026-05-08T06:04:11+00:00`

This report is a manual review queue for course identity issues that should be resolved before student-facing recommendations.

## Summary

- Numeric subject-code courses: 35
- NCC prerequisite edges: 55
- Unresolved prerequisite courses: 26
- Courses with empty title: 1
- Course numbers above 999: 4

## Recommended Review Decisions

1. Decide whether numeric subject-code courses are Ankara aliases, NCC alternatives, or independent courses.
2. Add approved aliases to `course_aliases` or a manual correction file before UI work.
3. Keep NCC alternatives in the raw graph, but label or filter them in student-facing recommendations.
4. Resolve unresolved courses by checking old course codes, department pages, and SAIS availability.
5. Fill missing titles only from an authoritative source.

## Numeric Subject-Code Courses

### Subject `219`

| Display | Numeric | Title |
| --- | --- | --- |
| `219 103` | `2190103` | MOLECULAR AND CELLULAR BIOLOGY I |
| `219 104` | `2190104` | MOLECULAR AND CELLULAR BIOLOGY II |

### Subject `355`

| Display | Numeric | Title |
| --- | --- | --- |
| `355 111` | `3550111` | INTRODUCTION TO COMPUTER ENG. CONCEPTS |
| `355 140` | `3550140` | C PROGRAMMING |
| `355 213` | `3550213` | DATA STRUCTURES |
| `355 230` | `3550230` | INTRODUCTION TO C PROGRAMMING |
| `355 240` | `3550240` | PROGRAMMING WITH PYTHON FOR ENGINEERS |
| `355 301` | `3550301` | ALGORITHMS AND DATA STRUCTURES |
| `355 310` | `3550310` | ALGORITHMS AND DATA STRUCTURES WITH PYTHON |
| `355 350` | `3550350` | SOFTWARE ENGINEERING |

### Subject `357`

| Display | Numeric | Title |
| --- | --- | --- |
| `357 100` | `3570100` | PRECALCULUS |
| `357 119` | `3570119` | CALCULUS WITH ANALYTIC GEOMETRY |
| `357 120` | `3570120` | CALCULUS FOR FUNCTIONS OF SEVERAL VARIABLES |
| `357 219` | `3570219` | INTRODUCTION TO DIFFERENTIAL EQUATIONS |

### Subject `358`

| Display | Numeric | Title |
| --- | --- | --- |
| `358 105` | `3580105` | GENERAL PHYSICS I |

### Subject `359`

| Display | Numeric | Title |
| --- | --- | --- |
| `359 101` | `3590101` | DEVELOPMENT OF READING AND WRITING SKILLS I |
| `359 102` | `3590102` | DEVELOPMENT OF READING AND WRITING SKILLS II |

### Subject `360`

| Display | Numeric | Title |
| --- | --- | --- |
| `360 111` | `3600111` | GENERAL CHEMISTRY I |

### Subject `362`

| Display | Numeric | Title |
| --- | --- | --- |
| `362 201` | `3620201` | PRINCIPLES OF KEMAL ATATÜRK I |

### Subject `364`

| Display | Numeric | Title |
| --- | --- | --- |
| `364 221` | `3640221` | ENGINEERING MECHANICS I |
| `364 224` | `3640224` | MECHANICS OF MATERIALS |

### Subject `365`

| Display | Numeric | Title |
| --- | --- | --- |
| `365 205` | `3650205` | STATICS |
| `365 206` | `3650206` | STRENGTH OF MATERIALS |
| `365 208` | `3650208` | DYNAMICS |

### Subject `374`

| Display | Numeric | Title |
| --- | --- | --- |
| `374 110` | `3740110` | INTRODUCTION TO PETROLEUM ENGINEERING |
| `374 211` | `3740211` | INTRODUCTION TO FLUID MECHANICS |
| `374 216` | `3740216` | RESERVOIR ROCK AND FLUID PROPERTIES |
| `374 218` | `3740218` | RESERVOIR FLUID PROPERTIES |
| `374 220` | `3740220` | RESERVOIR ROCK PROPERTIES |
| `374 321` | `3740321` | DRILLING ENGINEERING I |
| `374 331` | `3740331` | PETROLEUM PRODUCTION ENGINEERING I |

### Subject `384`

| Display | Numeric | Title |
| --- | --- | --- |
| `384 261` | `3840261` | STATICS |
| `384 264` | `3840264` | MECHANICS OF MATERIALS |

### Subject `389`

| Display | Numeric | Title |
| --- | --- | --- |
| `389 140` | `3890140` | PROGRAMMING |

### Subject `430`

| Display | Numeric | Title |
| --- | --- | --- |
| `430 210` | `4300210` | PROGRAMMING LANGUAGES I |

## NCC Prerequisite Edges

| Prerequisite | Course | Set | Min Grade | Type |
| --- | --- | ---: | --- | --- |
| `355 140` | `355 213` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `389 140` | `355 213` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `355 230` | `355 301` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `355 240` | `355 310` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `355 213` | `355 350` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `355 301` | `355 350` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `355 310` | `355 350` | 4 | DD | Undergraduate NCC / Lisans KKK |
| `357 100` | `357 119` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `357 119` | `357 120` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `357 120` | `357 219` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `359 101` | `359 102` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `357 119` | `364 221` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `364 221` | `364 224` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `365 205` | `364 224` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `357 119` | `365 205` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `358 105` | `365 205` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `365 205` | `365 206` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `365 205` | `365 208` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `374 110` | `374 220` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `364 224` | `374 321` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `374 211` | `374 321` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `365 206` | `374 321` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `374 211` | `374 321` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `374 211` | `374 321` | 3 | DD | Undergraduate NCC / Lisans KKK |
| `384 264` | `374 321` | 3 | DD | Undergraduate NCC / Lisans KKK |
| `374 218` | `374 331` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `374 220` | `374 331` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `374 216` | `374 331` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `357 119` | `384 261` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `358 105` | `384 261` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `384 261` | `384 264` | 1 | DD | Undergraduate NCC / Lisans KKK |
| `365 205` | `384 264` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `355 111` | `CENG 242` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `355 213` | `CENG 242` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `355 350` | `CENG 491` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `360 111` | `CHEM 112` | 6 | DD | Undergraduate NCC / Lisans KKK |
| `357 120` | `CHEM 257` | 5 | DD | Undergraduate NCC / Lisans KKK |
| `359 101` | `ENG 102` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `359 101` | `ENG 211` | 3 | DD | Undergraduate NCC / Lisans KKK |
| `359 102` | `ENG 211` | 3 | DD | Undergraduate NCC / Lisans KKK |
| `364 221` | `ES 224` | 4 | DD | Undergraduate NCC / Lisans KKK |
| `357 119` | `ES 303` | 5 | DD | Undergraduate NCC / Lisans KKK |
| `362 201` | `HIST 2202` | 2 | U | Undergraduate NCC / Lisans KKK |
| `357 119` | `MATH 120` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `357 120` | `MATH 219` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `365 208` | `ME 301` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `365 206` | `ME 303` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `365 206` | `ME 307` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `374 321` | `PETE 322` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `374 331` | `PETE 332` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `357 219` | `PETE 343` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `374 218` | `PETE 343` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `374 220` | `PETE 343` | 2 | DD | Undergraduate NCC / Lisans KKK |
| `357 219` | `PETE 343` | 3 | DD | Undergraduate NCC / Lisans KKK |
| `374 216` | `PETE 343` | 3 | DD | Undergraduate NCC / Lisans KKK |

## Unresolved Prerequisite Courses

Source: `data\processed\prerequisites`

| Course | Numeric | Programs | Reason |
| --- | --- | --- | --- |
| `374 216` | `3740216` | PETE | not_found_in_searched_offerings |
| `AE 122` | `5720122` | AE | not_found_in_searched_offerings |
| `AE 241` | `5720241` | AE | not_found_in_searched_offerings |
| `AEE 202` | `5720202` | AE | not_found_in_searched_offerings |
| `AEE 266` | `5720266` | AE | not_found_in_searched_offerings |
| `AEE 301` | `5720301` | AE | not_found_in_searched_offerings |
| `AEE 302` | `5720302` | AE | not_found_in_searched_offerings |
| `AEE 338` | `5720338` | AE | not_found_in_searched_offerings |
| `AEE 345` | `5720345` | AE | not_found_in_searched_offerings |
| `AEE 346` | `5720346` | AE | not_found_in_searched_offerings |
| `AEE 364` | `5720364` | AE | not_found_in_searched_offerings |
| `AEE 371` | `5720371` | AE | not_found_in_searched_offerings |
| `AEE 385` | `5720385` | AE | not_found_in_searched_offerings |
| `CENG 229` | `5710229` | CENG, IE | not_found_in_searched_offerings |
| `CENG 230` | `5710230` | CENG, IE, METE | not_found_in_searched_offerings |
| `CHEM 109` | `2340109` | CHE, ENVE, FDE, GEOE, METE, MINE, PETE | not_found_in_searched_offerings |
| `CHEM 110` | `2340110` | CHE, ENVE, FDE | not_found_in_searched_offerings |
| `IE 262` | `5680262` | IE | not_found_in_searched_offerings |
| `MATH 151` | `2360151` | AE, CE, CENG, CHE, EEE, ENVE, FDE, GEOE, IE, ME, METE, MINE, PETE | not_found_in_searched_offerings |
| `MATH 152` | `2360152` | CE, CHE, FDE, IE, PETE | not_found_in_searched_offerings |
| `MATH 155` | `2360155` | ENVE, FDE, GEOE, METE, MINE, PETE | not_found_in_searched_offerings |
| `MATH 156` | `2360156` | CHE, FDE, IE | not_found_in_searched_offerings |
| `MATH 157` | `2360157` | CE, ENVE, FDE, GEOE, METE, MINE, PETE | not_found_in_searched_offerings |
| `MATH 158` | `2360158` | CE, IE, PETE | not_found_in_searched_offerings |
| `MATH 253` | `2360253` | FDE | not_found_in_searched_offerings |
| `MATH 257` | `2360257` | CHE, FDE | not_found_in_searched_offerings |

## Courses With Empty Title

| Course | Numeric |
| --- | --- |
| `HIST 2202` | `2402202` |

## Course Numbers Above 999

These are not automatically wrong. METU has undergraduate service courses such as HIST 2201.

| Course | Numeric | Title |
| --- | --- | --- |
| `HIST 2201` | `2402201` | PRINCIPLES OF KEMAL ATATÜRK I |
| `HIST 2202` | `2402202` |  |
| `HIST 2205` | `2402205` | HISTORY OF THE TURKISH REVOLUTION I |
| `HIST 2206` | `2402206` | HISTORY OF THE TURKISH REVOLUTION II |
