from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from student_planner.domain.models import Program, RequirementType
from student_planner.sources.base import SourceSnapshot


CATALOG_PROGRAM_URL = "https://catalog.metu.edu.tr/program.php?fac_prog={program_id}"
PARSER_VERSION = "metu_catalog_curriculum_v1"

YEAR_LABEL_TO_NUMBER = {
    "FIRST YEAR": 1,
    "SECOND YEAR": 2,
    "THIRD YEAR": 3,
    "FOURTH YEAR": 4,
    "FIFTH YEAR": 5,
}

SEMESTER_LABEL_TO_NUMBER = {
    "First Semester": 1,
    "Second Semester": 2,
    "Third Semester": 3,
    "Fourth Semester": 4,
    "Fifth Semester": 5,
    "Sixth Semester": 6,
    "Seventh Semester": 7,
    "Eighth Semester": 8,
    "Ninth Semester": 9,
    "Tenth Semester": 10,
}


@dataclass
class CatalogRequirement:
    requirement_id: str
    requirement_type: str
    label: str
    year: int | None
    semester_index: int | None
    semester_label: str
    option_min_count: int = 1
    options: list[dict[str, Any]] = field(default_factory=list)
    metu_credit: str = ""
    contact_hours: str = ""
    lab_hours: str = ""
    ects: str = ""


class CellParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        self._current_href = attrs_dict.get("href", "")
        self._current_link_text = []

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._current_href is not None:
            self._current_link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        self.links.append((self._current_href, normalize_text("".join(self._current_link_text))))
        self._current_href = None
        self._current_link_text = []


def normalize_text(value: str) -> str:
    value = unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def strip_tags(html: str) -> str:
    return normalize_text(re.sub(r"<[^>]+>", " ", html))


def decode_catalog_bytes(payload: bytes) -> str:
    # Catalog pages declare iso8859-9 and Turkish characters decode correctly with it.
    for encoding in ("iso-8859-9", "utf-8"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def fetch_program_snapshot(program: Program, raw_root: Path) -> SourceSnapshot:
    url = CATALOG_PROGRAM_URL.format(program_id=program.catalog_program_id)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()

    now = dt.datetime.now(dt.timezone.utc)
    content_hash = hashlib.sha256(payload).hexdigest()
    snapshot_dir = raw_root / "catalog" / program.abbr / now.strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    content_path = snapshot_dir / "program.html"
    content_path.write_bytes(payload)

    metadata_path = snapshot_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "source_name": "METU Academic Catalog",
                "source_url": url,
                "retrieved_at_utc": now.isoformat(timespec="seconds"),
                "content_sha256": content_hash,
                "parser_version": PARSER_VERSION,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return SourceSnapshot(
        source_name="METU Academic Catalog",
        source_url=url,
        retrieved_at_utc=now.isoformat(timespec="seconds"),
        content_path=str(content_path),
        content_sha256=content_hash,
    )


def parse_program_curriculum(snapshot: SourceSnapshot, program: Program) -> dict[str, Any]:
    html = decode_catalog_bytes(Path(snapshot.content_path).read_bytes())
    curriculum_html = extract_curriculum_section(html)
    requirements = parse_curriculum_requirements(curriculum_html)

    return {
        "program": {
            "abbr": program.abbr,
            "catalog_program_id": program.catalog_program_id,
            "name_en": program.name_en,
            "name_tr": program.name_tr,
            "faculty": program.faculty,
        },
        "curriculum": {
            "version_label": "latest",
            "is_latest": True,
            "review_status": "scraped",
            "parser_version": PARSER_VERSION,
        },
        "source": {
            "source_name": snapshot.source_name,
            "source_url": snapshot.source_url,
            "retrieved_at_utc": snapshot.retrieved_at_utc,
            "content_path": snapshot.content_path,
            "content_sha256": snapshot.content_sha256,
        },
        "requirements": [requirement.__dict__ for requirement in requirements],
        "summary": summarize_requirements(requirements),
    }


def extract_curriculum_section(html: str) -> str:
    start_match = re.search(r"Undergraduate\s+Curriculum", html, flags=re.IGNORECASE)
    if not start_match:
        raise RuntimeError("Undergraduate Curriculum section was not found.")

    tail = html[start_match.start() :]
    end_match = re.search(r"Program\s+Total\s*:", tail, flags=re.IGNORECASE)
    if end_match:
        table_end = tail.find("</table>", end_match.end())
        if table_end != -1:
            return tail[: table_end + len("</table>")]
        return tail[: end_match.end()]
    return tail


def parse_curriculum_requirements(curriculum_html: str) -> list[CatalogRequirement]:
    requirements: list[CatalogRequirement] = []
    previous_end = 0
    current_year: int | None = None
    requirement_counter = 1

    for table_match in re.finditer(r"<table\b.*?</table>", curriculum_html, flags=re.IGNORECASE | re.DOTALL):
        context = strip_tags(curriculum_html[previous_end : table_match.start()])
        current_year = infer_year(context, current_year)
        semester_label = infer_semester_label(context)
        semester_index = SEMESTER_LABEL_TO_NUMBER.get(semester_label, None)
        table_html = table_match.group(0)

        parsed_table, requirement_counter = parse_curriculum_table(
            table_html=table_html,
            year=current_year,
            semester_index=semester_index,
            semester_label=semester_label,
            requirement_counter=requirement_counter,
        )
        requirements.extend(parsed_table)
        previous_end = table_match.end()

    return requirements


def infer_year(context: str, previous_year: int | None) -> int | None:
    found = previous_year
    for label, number in YEAR_LABEL_TO_NUMBER.items():
        if label in context.upper():
            found = number
    return found


def infer_semester_label(context: str) -> str:
    for label in SEMESTER_LABEL_TO_NUMBER:
        if label in context:
            return label
    return ""


def parse_curriculum_table(
    table_html: str,
    year: int | None,
    semester_index: int | None,
    semester_label: str,
    requirement_counter: int,
) -> tuple[list[CatalogRequirement], int]:
    requirements: list[CatalogRequirement] = []
    active_choice: CatalogRequirement | None = None

    for row_html in re.findall(r"<tr\b.*?</tr>", table_html, flags=re.IGNORECASE | re.DOTALL):
        cells = parse_row_cells(row_html)
        if not cells:
            continue

        row_text = normalize_text(" ".join(cell["text"] for cell in cells))
        if is_noise_row(row_text):
            if active_choice and ("border-top" in row_html or "Semester Total:" in row_text):
                active_choice = None
            continue

        choice_count = parse_choice_count(row_text)
        if choice_count is not None:
            active_choice = CatalogRequirement(
                requirement_id=f"REQ-{requirement_counter:04d}",
                requirement_type=RequirementType.COURSE_CHOICE.value,
                label=row_text,
                year=year,
                semester_index=semester_index,
                semester_label=semester_label,
                option_min_count=choice_count,
            )
            requirement_counter += 1
            requirements.append(active_choice)
            continue

        course_option = parse_course_option(cells)
        if course_option:
            if active_choice is not None:
                active_choice.options.append(course_option)
                continue

            requirement = CatalogRequirement(
                requirement_id=f"REQ-{requirement_counter:04d}",
                requirement_type=classify_course_requirement(
                    course_option["course_code"],
                    course_option["course_title"],
                ),
                label=course_option["course_code"],
                year=year,
                semester_index=semester_index,
                semester_label=semester_label,
                option_min_count=1,
                options=[course_option],
                metu_credit=course_option["metu_credit"],
                contact_hours=course_option["contact_hours"],
                lab_hours=course_option["lab_hours"],
                ects=course_option["ects"],
            )
            requirement_counter += 1
            requirements.append(requirement)
            continue

        placeholder = parse_placeholder_requirement(cells, row_text)
        if placeholder:
            requirement = CatalogRequirement(
                requirement_id=f"REQ-{requirement_counter:04d}",
                requirement_type=placeholder["requirement_type"],
                label=placeholder["label"],
                year=year,
                semester_index=semester_index,
                semester_label=semester_label,
                option_min_count=1,
                options=[],
                metu_credit=placeholder["metu_credit"],
                contact_hours=placeholder["contact_hours"],
                lab_hours=placeholder["lab_hours"],
                ects=placeholder["ects"],
            )
            requirement_counter += 1
            requirements.append(requirement)

    return requirements, requirement_counter


def parse_row_cells(row_html: str) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for cell_html in re.findall(r"<t[dh]\b.*?</t[dh]>", row_html, flags=re.IGNORECASE | re.DOTALL):
        parser = CellParser()
        parser.feed(cell_html)
        cells.append(
            {
                "html": cell_html,
                "text": normalize_text("".join(parser.text_parts)),
                "links": parser.links,
            }
        )
    return cells


def is_noise_row(row_text: str) -> bool:
    if not row_text:
        return True
    lowered = row_text.lower()
    return (
        "course code course name metu credit" in lowered
        or "semester total:" in lowered
        or "program total:" in lowered
    )


def parse_choice_count(row_text: str) -> int | None:
    match = re.search(r"Any\s+(\d+)\s+of\s+the\s+following\s+set", row_text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def parse_course_option(cells: list[dict[str, Any]]) -> dict[str, str] | None:
    if len(cells) < 6 or not cells[0]["links"]:
        return None

    href, display_code = cells[0]["links"][0]
    code_match = re.search(r"course_code=(\d+)", href)
    numeric_code = code_match.group(1) if code_match else ""

    return {
        "course_code": normalize_course_display(display_code),
        "numeric_code": numeric_code,
        "course_title": cells[1]["text"],
        "metu_credit": cells[2]["text"],
        "contact_hours": cells[3]["text"],
        "lab_hours": cells[4]["text"],
        "ects": cells[5]["text"],
    }


def parse_placeholder_requirement(cells: list[dict[str, Any]], row_text: str) -> dict[str, str] | None:
    if len(cells) < 2:
        return None

    label = cells[1]["text"] if len(cells) > 1 else row_text
    if not label:
        return None

    requirement_type = classify_placeholder_requirement(label)
    if requirement_type is None:
        return None

    return {
        "requirement_type": requirement_type,
        "label": label,
        "metu_credit": cells[2]["text"] if len(cells) > 2 else "",
        "contact_hours": cells[3]["text"] if len(cells) > 3 else "",
        "lab_hours": cells[4]["text"] if len(cells) > 4 else "",
        "ects": cells[5]["text"] if len(cells) > 5 else "",
    }


def normalize_course_display(value: str) -> str:
    value = normalize_text(value)
    match = re.match(r"^([A-Z]+)(\d+[A-Z]?)$", value)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return value


def classify_course_requirement(course_code: str, course_title: str) -> str:
    if "SUMMER PRACTICE" in course_title.upper():
        return RequirementType.SUMMER_PRACTICE.value
    return RequirementType.REQUIRED_COURSE.value


def classify_placeholder_requirement(label: str) -> str | None:
    upper = label.upper()
    if "NONTECHNICAL ELECTIVE" in upper or "NON-TECHNICAL ELECTIVE" in upper:
        return RequirementType.NONTECHNICAL_ELECTIVE_POOL.value
    if "TECHNICAL ELECTIVE" in upper:
        return RequirementType.TECHNICAL_ELECTIVE_POOL.value
    if "RESTRICTED ELECTIVE" in upper:
        return RequirementType.RESTRICTED_ELECTIVE_POOL.value
    if "FREE ELECTIVE" in upper:
        return RequirementType.FREE_ELECTIVE_POOL.value
    if "ELECTIVE" in upper:
        return RequirementType.OTHER.value
    return None


def summarize_requirements(requirements: list[CatalogRequirement]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    course_options = 0
    placeholder_requirements = 0
    for requirement in requirements:
        counts[requirement.requirement_type] = counts.get(requirement.requirement_type, 0) + 1
        course_options += len(requirement.options)
        if not requirement.options:
            placeholder_requirements += 1

    unique_courses = sorted(
        {
            option["course_code"]
            for requirement in requirements
            for option in requirement.options
            if option.get("course_code")
        }
    )
    return {
        "requirement_count": len(requirements),
        "course_option_count": course_options,
        "unique_course_count": len(unique_courses),
        "placeholder_requirement_count": placeholder_requirements,
        "counts_by_type": counts,
    }


def write_curriculum_outputs(curriculum: dict[str, Any], processed_root: Path) -> tuple[Path, Path]:
    abbr = curriculum["program"]["abbr"]
    output_dir = processed_root / "curricula"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{abbr}-latest.curriculum.json"
    csv_path = output_dir / f"{abbr}-latest.curriculum_requirements.csv"
    json_path.write_text(json.dumps(curriculum, ensure_ascii=False, indent=2), encoding="utf-8")

    fieldnames = [
        "program_abbr",
        "catalog_program_id",
        "requirement_id",
        "requirement_type",
        "label",
        "year",
        "semester_index",
        "semester_label",
        "option_min_count",
        "option_index",
        "course_code",
        "numeric_code",
        "course_title",
        "metu_credit",
        "contact_hours",
        "lab_hours",
        "ects",
        "source_url",
        "review_status",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for requirement in curriculum["requirements"]:
            options = requirement["options"] or [None]
            for option_index, option in enumerate(options, start=1):
                writer.writerow(
                    {
                        "program_abbr": curriculum["program"]["abbr"],
                        "catalog_program_id": curriculum["program"]["catalog_program_id"],
                        "requirement_id": requirement["requirement_id"],
                        "requirement_type": requirement["requirement_type"],
                        "label": requirement["label"],
                        "year": requirement["year"],
                        "semester_index": requirement["semester_index"],
                        "semester_label": requirement["semester_label"],
                        "option_min_count": requirement["option_min_count"],
                        "option_index": option_index if option else "",
                        "course_code": option["course_code"] if option else "",
                        "numeric_code": option["numeric_code"] if option else "",
                        "course_title": option["course_title"] if option else "",
                        "metu_credit": option["metu_credit"] if option else requirement["metu_credit"],
                        "contact_hours": option["contact_hours"] if option else requirement["contact_hours"],
                        "lab_hours": option["lab_hours"] if option else requirement["lab_hours"],
                        "ects": option["ects"] if option else requirement["ects"],
                        "source_url": curriculum["source"]["source_url"],
                        "review_status": curriculum["curriculum"]["review_status"],
                    }
                )

    return json_path, csv_path
