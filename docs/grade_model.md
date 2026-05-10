# Grade Model

The grade model is implemented in:

```text
student_planner/domain/grades.py
tests/test_grades.py
```

It is intentionally pure domain logic. It does not depend on SQLite, scrapers, or
processed files.

## Supported Grades

```text
AA
BA
BB
CB
CC
DC
DD
FD
FF
S
U
W
NA
EX
```

Meanings used by the planner:

- `W`: withdraw. Never satisfies a prerequisite.
- `NA`: Not Allowed. Treated like `FF`.
- `EX`: exempt. Treated like `S`.

## Letter Ordering

```text
AA > BA > BB > CB > CC > DC > DD > FD > FF
```

`NA` has the same rank as `FF`.

The normal credit threshold for letter grades is `DD`.

## S/U and EX Policy

- `S` earns credit.
- `EX` earns credit and behaves like `S`.
- `U` does not earn credit.
- `U` still satisfies an explicit prerequisite minimum of `U`, because SAIS uses
  `U` as a minimum on some S/U prerequisite rows.

## Cross-Family Minimums

The planner needs a practical bridge between letter grades and S/U-style grades:

- `S` and `EX` satisfy normal pass-level letter minimums such as `DD`.
- `S` and `EX` do not satisfy stricter letter minimums such as `CC`.
- Passing letter grades satisfy an `S` minimum.
- Passing letter grades satisfy a `U` minimum.
- `FF`, `FD`, `NA`, and `W` do not satisfy an `S` minimum.
- `FF`, `FD`, `NA`, and `W` do not satisfy a `U` minimum, except `U` itself
  satisfies explicit `U`.

## Important Functions

```python
normalize_grade(value)
is_supported_grade(value)
is_letter_grade(value)
is_pass_fail_grade(value)
is_withdrawal(value)
earns_credit(value)
is_unsuccessful(value)
compare_letter_grades(left, right)
satisfies_min_grade(earned, minimum)
```

## Test Command

```powershell
python -m unittest discover -s tests -v
```

Current test coverage includes:

- all supported grade normalization
- lowercase and descriptive suffix input
- invalid grade rejection
- letter grade ordering
- `NA` as `FF`
- `EX` as `S`
- `W` withdrawal behavior
- explicit `U` minimum behavior
- cross-family prerequisite minimum behavior
