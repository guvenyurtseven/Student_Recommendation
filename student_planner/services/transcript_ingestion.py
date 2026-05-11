from __future__ import annotations

import re
from io import BytesIO
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from student_planner.domain.grades import is_supported_grade, normalize_grade
from student_planner.domain.planning import (
    CompletedCourseAttempt,
    InProgressCourse,
    PlanningGoal,
    StudentPlanningInput,
    normalize_display_course_code,
)

TERM_SUFFIX_BY_LABEL: dict[str, str] = {
    "fall": "1",
    "autumn": "1",
    "guz": "1",
    "guz donemi": "1",
    "spring": "2",
    "bahar": "2",
    "bahar donemi": "2",
    "summer": "3",
    "yaz": "3",
    "yaz donemi": "3",
}

PROGRAM_ABBR_BY_NAME: dict[str, str] = {
    "aerospace engineering": "AE",
    "chemical engineering": "CHE",
    "civil engineering": "CE",
    "computer engineering": "CENG",
    "electrical and electronics engineering": "EEE",
    "environmental engineering": "ENVE",
    "food engineering": "FDE",
    "geological engineering": "GEOE",
    "industrial engineering": "IE",
    "mechanical engineering": "ME",
    "metallurgical and materials engineering": "METE",
    "mining engineering": "MINE",
    "petroleum and natural gas engineering": "PETE",
}

GRADE_PATTERN = r"AA|BA|BB|CB|CC|DC|DD|FD|FF|NA|EX|S|U|W"
IN_PROGRESS_TOKENS = {"IP", "I", "INPROGRESS", "IN PROGRESS", "CONTINUING", "-"}

COURSE_START_RE = re.compile(r"^\s*[A-Z]{2,8}\s*\d{3,4}[A-Z]?\b", re.IGNORECASE)

METU_TRANSCRIPT_COURSE_LINE_RE = re.compile(
    rf"""
    ^\s*
    (?P<subject>[A-Z]{{2,8}})\s*(?P<number>\d{{3,4}}[A-Z]?)
    \b
    (?P<body>.*?)
    (?P<credits>\d+(?:[\.,]\d+)?)
    \s*(?:\*)?\s*
    (?P<grade>{GRADE_PATTERN}|IP|I|IN\s+PROGRESS|CONTINUING|-)
    \s*(?:\*)?\s*
    (?P<ects>\d+(?:[\.,]\d+)?)
    \s*(?:\*)?\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

DETAILED_COURSE_LINE_RE = re.compile(
    rf"""
    ^\s*
    (?P<subject>[A-Z]{{2,8}})\s*(?P<number>\d{{3,4}}[A-Z]?)
    \b
    (?P<body>.*?)
    (?P<credits>\d+(?:[\.,]\d+)?)
    \s+
    (?P<ects>\d+(?:[\.,]\d+)?)
    \s+
    (?P<grade>{GRADE_PATTERN}|IP|I|IN\s+PROGRESS|CONTINUING|-)
    (?=$|\s|\()
    """,
    re.IGNORECASE | re.VERBOSE,
)

COMPACT_COURSE_LINE_RE = re.compile(
    rf"""
    ^\s*
    (?P<subject>[A-Z]{{2,8}})\s*(?P<number>\d{{3,4}}[A-Z]?)
    \b
    .*
    \s+(?P<grade>{GRADE_PATTERN}|IP|I|IN\s+PROGRESS|CONTINUING|-)
    (?:\s|\(|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)

ACADEMIC_YEAR_TERM_PATTERNS = (
    re.compile(
        r"\b(?P<start>20\d{2})\s*[-/]\s*(?P<end>20\d{2})\s+"
        r"(?P<term>fall|autumn|spring|summer|guz|bahar|yaz)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<term>fall|autumn|spring|summer|guz|bahar|yaz)\s+"
        r"(?P<start>20\d{2})\s*[-/]\s*(?P<end>20\d{2})\b",
        re.IGNORECASE,
    ),
)

SEMESTER_NO_RE = re.compile(r"\b(?P<semester_no>20\d{3})\b")
ACADEMIC_STANDING_LINE_RE = re.compile(
    r"""
    \bCumGPA:\s*(?P<cgpa>\d+(?:[\.,]\d+)?)
    \s+GPA:\s*(?P<gpa>\d+(?:[\.,]\d+)?)
    \s+STAN:\s*(?P<standing>[A-Z ]+?)
    (?=\s+\d|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class TranscriptParseWarning:
    code: str
    message: str
    course_code: str | None = None


@dataclass(frozen=True)
class AcademicStandingRecord:
    semester_no: str | None
    cgpa: float
    gpa: float
    standing: str


@dataclass(frozen=True)
class TranscriptParseResult:
    completed_courses: tuple[CompletedCourseAttempt, ...]
    in_progress_courses: tuple[InProgressCourse, ...] = field(default_factory=tuple)
    warnings: tuple[TranscriptParseWarning, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "completed_courses", tuple(self.completed_courses))
        object.__setattr__(self, "in_progress_courses", tuple(self.in_progress_courses))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class TranscriptTextParser:
    """Extract planner-ready course attempts from transcript text.

    The parser intentionally returns only normalized course attempts and parse
    statistics. It does not keep raw transcript lines or full transcript text.
    """

    def parse(self, text: str) -> TranscriptParseResult:
        if not isinstance(text, str):
            raise TypeError("Transcript text must be a string.")
        if not text.strip():
            raise ValueError("Transcript text cannot be empty.")

        completed: list[CompletedCourseAttempt] = []
        in_progress: list[InProgressCourse] = []
        warnings: list[TranscriptParseWarning] = []
        academic_standings: list[AcademicStandingRecord] = []
        current_semester_no: str | None = None
        attempted_course_lines = 0
        ignored_nonempty_lines = 0

        lines = tuple(collapse_spaces(raw_line) for raw_line in text.splitlines())
        detected_program_name, detected_program_abbr = detect_program(lines)
        index = 0
        while index < len(lines):
            line = lines[index]
            if not line:
                index += 1
                continue

            detected_semester = detect_semester_no(line)
            if detected_semester:
                current_semester_no = detected_semester
                index += 1
                continue

            academic_standing = parse_academic_standing_line(line, current_semester_no)
            if academic_standing is not None:
                academic_standings.append(academic_standing)
                index += 1
                continue

            parsed_line, consumed_lines = parse_course_line_with_continuation(lines, index)
            if parsed_line is None:
                ignored_nonempty_lines += 1
                index += 1
                continue

            index += consumed_lines
            attempted_course_lines += 1
            course_code, grade_token, credits, ects = parsed_line
            semester_no = current_semester_no
            normalized_grade_token = normalize_in_progress_token(grade_token)

            if normalized_grade_token in IN_PROGRESS_TOKENS:
                if semester_no is None:
                    warnings.append(
                        TranscriptParseWarning(
                            code="in_progress_semester_unknown",
                            message="An in-progress course was found before any semester header.",
                            course_code=course_code,
                        )
                    )
                    semester_no = "unknown"
                in_progress.append(
                    InProgressCourse(
                        course_code=course_code,
                        semester_no=semester_no,
                        source="transcript_pdf",
                    )
                )
                continue

            if not is_supported_grade(normalized_grade_token):
                warnings.append(
                    TranscriptParseWarning(
                        code="unsupported_grade",
                        message="A course line had a grade that is not supported by the planner.",
                        course_code=course_code,
                    )
                )
                continue

            completed.append(
                CompletedCourseAttempt(
                    course_code=course_code,
                    grade=normalize_grade(normalized_grade_token),
                    completed_semester_no=semester_no,
                    attempt_order=len(completed) + 1,
                    source="transcript_pdf",
                    ects=ects,
                    credits=credits,
                )
            )

        if not completed and not in_progress:
            warnings.append(
                TranscriptParseWarning(
                    code="no_courses_extracted",
                    message="No course attempts could be extracted from the transcript text.",
                )
            )

        latest_academic_standing = academic_standings[-1] if academic_standings else None
        metadata: dict[str, Any] = {
            "source_format": "transcript_text",
            "line_count": len(text.splitlines()),
            "attempted_course_line_count": attempted_course_lines,
            "ignored_nonempty_line_count": ignored_nonempty_lines,
            "completed_course_count": len(completed),
            "in_progress_course_count": len(in_progress),
            "raw_transcript_retained": False,
            "detected_program_name": detected_program_name,
            "detected_program_abbr": detected_program_abbr,
            "academic_standing_record_count": len(academic_standings),
        }
        if latest_academic_standing is not None:
            metadata.update(
                {
                    "latest_standing_semester_no": latest_academic_standing.semester_no,
                    "latest_cgpa": latest_academic_standing.cgpa,
                    "latest_gpa": latest_academic_standing.gpa,
                    "latest_standing": latest_academic_standing.standing,
                }
            )

        return TranscriptParseResult(
            completed_courses=tuple(completed),
            in_progress_courses=tuple(in_progress),
            warnings=tuple(warnings),
            metadata=metadata,
        )


def build_planning_input_from_transcript_text(
    text: str,
    *,
    program_abbr: str | None = None,
    goal: PlanningGoal,
    elective_intents: Iterable[Any] = (),
    curriculum_version_label: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> StudentPlanningInput:
    parse_result = TranscriptTextParser().parse(text)
    resolved_program_abbr = program_abbr or parse_result.metadata.get("detected_program_abbr")
    if not resolved_program_abbr:
        raise ValueError("Program could not be detected from transcript text; provide program_abbr explicitly.")
    combined_metadata = dict(metadata or {})
    combined_metadata["input_source"] = "transcript_pdf"
    combined_metadata["transcript_parse"] = dict(parse_result.metadata)
    if parse_result.warnings:
        combined_metadata["transcript_parse_warnings"] = tuple(
            {
                "code": warning.code,
                "message": warning.message,
                "course_code": warning.course_code,
            }
            for warning in parse_result.warnings
        )
    return StudentPlanningInput(
        program_abbr=str(resolved_program_abbr),
        completed_courses=parse_result.completed_courses,
        in_progress_courses=parse_result.in_progress_courses,
        elective_intents=tuple(elective_intents),
        goal=goal,
        curriculum_version_label=curriculum_version_label,
        metadata=combined_metadata,
    )


def extract_text_from_pdf(path: str | Path) -> str:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Transcript PDF does not exist: {pdf_path}")
    if not pdf_path.is_file():
        raise ValueError(f"Transcript PDF path is not a file: {pdf_path}")

    with pdf_path.open("rb") as handle:
        return extract_text_from_pdf_stream(handle)


def extract_text_from_pdf_bytes(data: bytes) -> str:
    if not isinstance(data, bytes | bytearray):
        raise TypeError("PDF data must be bytes.")
    if not data:
        raise ValueError("PDF data cannot be empty.")
    return extract_text_from_pdf_stream(BytesIO(data))


def extract_text_from_pdf_stream(stream: Any) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF transcript extraction requires the optional `pypdf` package. "
            "Install it with `pip install pypdf`, or use --transcript-text for "
            "already-extracted text during local tests."
        ) from exc

    reader = PdfReader(stream)
    pages = tuple(page.extract_text() or "" for page in reader.pages)
    return "\n".join(pages)


def parse_course_line(line: str) -> tuple[str, str, float | None, float | None] | None:
    match = METU_TRANSCRIPT_COURSE_LINE_RE.search(line)
    if match:
        return (
            normalize_display_course_code(f"{match.group('subject')} {match.group('number')}"),
            match.group("grade"),
            parse_decimal(match.group("credits")),
            parse_decimal(match.group("ects")),
        )

    match = DETAILED_COURSE_LINE_RE.search(line)
    if match:
        return (
            normalize_display_course_code(f"{match.group('subject')} {match.group('number')}"),
            match.group("grade"),
            parse_decimal(match.group("credits")),
            parse_decimal(match.group("ects")),
        )

    match = COMPACT_COURSE_LINE_RE.search(line)
    if match:
        return (
            normalize_display_course_code(f"{match.group('subject')} {match.group('number')}"),
            match.group("grade"),
            None,
            None,
        )
    return None


def parse_academic_standing_line(line: str, semester_no: str | None) -> AcademicStandingRecord | None:
    match = ACADEMIC_STANDING_LINE_RE.search(line)
    if not match:
        return None
    return AcademicStandingRecord(
        semester_no=semester_no,
        cgpa=parse_decimal(match.group("cgpa")) or 0.0,
        gpa=parse_decimal(match.group("gpa")) or 0.0,
        standing=collapse_spaces(match.group("standing")).upper(),
    )


def detect_program(lines: tuple[str, ...]) -> tuple[str | None, str | None]:
    candidates: list[tuple[str, str]] = []
    normalized_lines = tuple(collapse_spaces(line) for line in lines if collapse_spaces(line))
    for index, line in enumerate(normalized_lines):
        direct = program_abbr_for_name(line)
        if direct:
            candidates.append((line, direct))

        lowered = line.lower()
        if "department of " in lowered:
            name = line[lowered.index("department of ") + len("department of "):]
            abbr = program_abbr_for_name(name)
            if abbr:
                candidates.append((name, abbr))

        if lowered in {"department/", "department", "program", "department/program"}:
            for lookahead in normalized_lines[index + 1:index + 4]:
                abbr = program_abbr_for_name(lookahead)
                if abbr:
                    candidates.append((lookahead, abbr))
                    break

    if not candidates:
        return None, None

    counts: dict[tuple[str, str], int] = {}
    for candidate in candidates:
        counts[candidate] = counts.get(candidate, 0) + 1
    (program_name, program_abbr), _count = max(
        counts.items(),
        key=lambda item: (item[1], -len(item[0][0])),
    )
    return program_name, program_abbr


def program_abbr_for_name(value: str) -> str | None:
    normalized = normalize_program_name(value)
    if normalized in PROGRAM_ABBR_BY_NAME:
        return PROGRAM_ABBR_BY_NAME[normalized]
    for program_name, abbr in PROGRAM_ABBR_BY_NAME.items():
        if program_name in normalized:
            return abbr
    return None


def normalize_program_name(value: str) -> str:
    return re.sub(r"[^a-z& ]+", " ", value.lower()).replace("&", "and").strip()


def parse_course_line_with_continuation(
    lines: tuple[str, ...],
    index: int,
    max_continuation_lines: int = 3,
) -> tuple[tuple[str, str, float | None, float | None] | None, int]:
    line = lines[index]
    parsed_line = parse_course_line(line)
    if parsed_line is not None:
        return parsed_line, 1
    if not looks_like_course_start(line):
        return None, 1

    joined = line
    for offset in range(1, max_continuation_lines + 1):
        next_index = index + offset
        if next_index >= len(lines):
            break
        next_line = lines[next_index]
        if not next_line:
            break
        if detect_semester_no(next_line) or looks_like_course_start(next_line):
            break
        joined = f"{joined} {next_line}"
        parsed_line = parse_course_line(joined)
        if parsed_line is not None:
            return parsed_line, offset + 1
    return None, 1


def looks_like_course_start(line: str) -> bool:
    return COURSE_START_RE.search(line) is not None


def detect_semester_no(line: str) -> str | None:
    normalized_line = normalize_term_text(line)
    for pattern in ACADEMIC_YEAR_TERM_PATTERNS:
        match = pattern.search(normalized_line)
        if not match:
            continue
        suffix = TERM_SUFFIX_BY_LABEL.get(match.group("term").lower())
        if suffix:
            return f"{match.group('start')}{suffix}"

    match = SEMESTER_NO_RE.search(line)
    if match:
        return match.group("semester_no")
    return None


def parse_decimal(value: str | None) -> float | None:
    if value is None:
        return None
    return float(value.replace(",", "."))


def collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_term_text(value: str) -> str:
    return (
        value.lower()
        .replace("güz", "guz")
        .replace("dönemi", "donemi")
        .replace("ı", "i")
    )


def normalize_in_progress_token(value: str) -> str:
    return collapse_spaces(value).upper().replace("IN PROGRESS", "INPROGRESS")
