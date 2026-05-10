from __future__ import annotations

from enum import StrEnum


class Grade(StrEnum):
    AA = "AA"
    BA = "BA"
    BB = "BB"
    CB = "CB"
    CC = "CC"
    DC = "DC"
    DD = "DD"
    FD = "FD"
    FF = "FF"
    S = "S"
    U = "U"
    W = "W"
    NA = "NA"
    EX = "EX"


LETTER_GRADE_RANK: dict[Grade, int] = {
    Grade.FF: 0,
    Grade.NA: 0,
    Grade.FD: 1,
    Grade.DD: 2,
    Grade.DC: 3,
    Grade.CC: 4,
    Grade.CB: 5,
    Grade.BB: 6,
    Grade.BA: 7,
    Grade.AA: 8,
}

PASSING_LETTER_MINIMUM = Grade.DD
PASS_FAIL_RANK: dict[Grade, int] = {
    Grade.U: 0,
    Grade.S: 1,
    Grade.EX: 1,
}


def normalize_grade(value: str | Grade) -> Grade:
    """Return a supported grade enum from user/DB input.

    The function accepts compact grade values such as ``"AA"`` and also tolerates
    note-like text such as ``"W (withdraw)"`` by reading the first token.
    """

    if isinstance(value, Grade):
        return value
    if not isinstance(value, str):
        raise ValueError(f"Unsupported grade value: {value!r}")

    token = value.strip().upper().split(maxsplit=1)[0] if value.strip() else ""
    if not token:
        raise ValueError("Grade cannot be empty.")
    try:
        return Grade(token)
    except ValueError as exc:
        raise ValueError(f"Unsupported grade value: {value!r}") from exc


def is_supported_grade(value: str | Grade) -> bool:
    try:
        normalize_grade(value)
    except ValueError:
        return False
    return True


def is_letter_grade(value: str | Grade) -> bool:
    return normalize_grade(value) in LETTER_GRADE_RANK


def is_pass_fail_grade(value: str | Grade) -> bool:
    return normalize_grade(value) in PASS_FAIL_RANK


def is_withdrawal(value: str | Grade) -> bool:
    return normalize_grade(value) == Grade.W


def earns_credit(value: str | Grade) -> bool:
    """Return whether the grade counts as successful completion.

    `NA` is treated like `FF`, and `EX` is treated like `S`.
    """

    grade = normalize_grade(value)
    if grade in LETTER_GRADE_RANK:
        return LETTER_GRADE_RANK[grade] >= LETTER_GRADE_RANK[PASSING_LETTER_MINIMUM]
    if grade in {Grade.S, Grade.EX}:
        return True
    return False


def is_unsuccessful(value: str | Grade) -> bool:
    grade = normalize_grade(value)
    return grade in {Grade.FD, Grade.FF, Grade.NA, Grade.U, Grade.W}


def compare_letter_grades(left: str | Grade, right: str | Grade) -> int:
    """Compare two letter-family grades.

    Returns a positive number when ``left`` is higher than ``right``, zero when
    they are equivalent, and a negative number otherwise. `NA` is equivalent to
    `FF`.
    """

    left_grade = normalize_grade(left)
    right_grade = normalize_grade(right)
    if left_grade not in LETTER_GRADE_RANK or right_grade not in LETTER_GRADE_RANK:
        raise ValueError("Both grades must be letter-family grades.")
    return LETTER_GRADE_RANK[left_grade] - LETTER_GRADE_RANK[right_grade]


def satisfies_min_grade(earned: str | Grade, minimum: str | Grade) -> bool:
    """Return whether an earned grade satisfies a prerequisite minimum grade.

    Policy decisions:

    - `NA` behaves like `FF`.
    - `EX` behaves like `S`.
    - `W` never satisfies a prerequisite because the course was withdrawn.
    - Letter grades are compared by METU ordering.
    - `S`/`EX` satisfy normal pass-level letter minimums such as `DD`, but not
      stricter letter thresholds such as `CC`.
    - `U` does not earn credit, but it satisfies an explicit `U` minimum because
      SAIS uses `U` as a minimum on some S/U prerequisite rows.
    """

    earned_grade = normalize_grade(earned)
    minimum_grade = normalize_grade(minimum)

    if earned_grade == Grade.W:
        return False
    if minimum_grade == Grade.W:
        return False

    if minimum_grade in LETTER_GRADE_RANK:
        if earned_grade in LETTER_GRADE_RANK:
            return LETTER_GRADE_RANK[earned_grade] >= LETTER_GRADE_RANK[minimum_grade]
        if earned_grade in {Grade.S, Grade.EX}:
            return LETTER_GRADE_RANK[minimum_grade] <= LETTER_GRADE_RANK[PASSING_LETTER_MINIMUM]
        return False

    if minimum_grade in {Grade.S, Grade.EX}:
        return earns_credit(earned_grade)

    if minimum_grade == Grade.U:
        return earned_grade == Grade.U or earns_credit(earned_grade)

    return False
