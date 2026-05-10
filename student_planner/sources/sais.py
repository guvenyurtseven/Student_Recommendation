from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
import unicodedata
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

from student_planner.domain.models import Program
from student_planner.sources.base import SourceSnapshot


SSO_SIGNIN_URL = "https://student.metu.edu.tr/sso/backend/request/user/signin"
PORTAL_GET_CONTENT_URL = "https://student.metu.edu.tr/portal/backend/request/route/get_content"
PORTAL_CONTENT_URL = "https://student.metu.edu.tr/portal/content.php?pkg="
COURSE_DETAILS_APP_CODE = 64
PARSER_VERSION = "metu_sais_offerings_v1"


@dataclass
class SelectState:
    name: str
    options: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class OptionState:
    value: str
    text_parts: list[str] = field(default_factory=list)


@dataclass
class FormState:
    action: str = ""
    method: str = "GET"
    inputs: dict[str, str] = field(default_factory=dict)
    selects: dict[str, list[tuple[str, str]]] = field(default_factory=dict)


@dataclass(frozen=True)
class SaisCourseOffering:
    program_abbr: str
    department_value: str
    department_text: str
    semester_no: str
    semester_text: str
    numeric_code: str
    display_code: str
    course_number: int | None
    course_name: str
    ects_credit: str
    credit: str
    level: str
    course_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_abbr": self.program_abbr,
            "department_value": self.department_value,
            "department_text": self.department_text,
            "semester_no": self.semester_no,
            "semester_text": self.semester_text,
            "numeric_code": self.numeric_code,
            "display_code": self.display_code,
            "course_number": self.course_number,
            "course_name": self.course_name,
            "ects_credit": self.ects_credit,
            "credit": self.credit,
            "level": self.level,
            "type": self.course_type,
        }


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[FormState] = []
        self._form: FormState | None = None
        self._select: SelectState | None = None
        self._option: OptionState | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}

        if tag == "form":
            self._form = FormState(
                action=attrs_dict.get("action", ""),
                method=attrs_dict.get("method", "GET").upper(),
            )
            return

        if self._form is None:
            return

        if tag == "input":
            name = attrs_dict.get("name")
            if name:
                self._form.inputs[name] = attrs_dict.get("value", "")
            return

        if tag == "select":
            name = attrs_dict.get("name")
            if name:
                self._select = SelectState(name=name)
            return

        if tag == "option" and self._select is not None:
            self._option = OptionState(value=attrs_dict.get("value", ""))

    def handle_data(self, data: str) -> None:
        if self._option is not None:
            self._option.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "option" and self._select is not None and self._option is not None:
            self._select.options.append(
                (self._option.value, normalize_text("".join(self._option.text_parts)))
            )
            self._option = None
            return

        if tag == "select" and self._form is not None and self._select is not None:
            self._form.selects[self._select.name] = self._select.options
            self._select = None
            return

        if tag == "form" and self._form is not None:
            self.forms.append(self._form)
            self._form = None


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._row is not None and self._cell_parts is not None:
            self._row.append(normalize_text("".join(self._cell_parts)))
            self._cell_parts = None
        elif tag == "tr" and self._table is not None and self._row is not None:
            if any(cell for cell in self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


class MetuSaisClient:
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar())
        )
        self._token: str | None = None

    def post_json(self, url: str, payload: dict[str, object], session: bool = False) -> str:
        headers = {
            "Content-Type": "application/json;charset=utf-8",
            "X-Requested-With": "XMLHttpRequest",
            "Locale": "en",
            "User-Agent": "Mozilla/5.0",
        }
        if session:
            if not self._token:
                raise RuntimeError("Session token is missing.")
            headers["Token"] = self._token

        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with self._opener.open(request, timeout=60) as response:
            token = response.headers.get("Token") or response.headers.get("token")
            if token:
                self._token = token
            return response.read().decode("utf-8", errors="replace")

    def post_form(
        self,
        url: str,
        payload: dict[str, str],
        referer: str | None = None,
    ) -> tuple[str, str]:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0",
        }
        if referer:
            headers["Referer"] = referer

        request = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with self._opener.open(request, timeout=60) as response:
            return response.url, response.read().decode("utf-8", errors="replace")

    def get(self, url: str) -> tuple[str, str]:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with self._opener.open(request, timeout=60) as response:
            return response.url, response.read().decode("utf-8", errors="replace")

    def sign_in(self) -> None:
        self.post_json(
            SSO_SIGNIN_URL,
            {"username": self.username, "password": self.password},
            session=False,
        )
        if not self._token:
            raise RuntimeError("Sign-in failed: METU SAIS did not return a token.")

    def open_course_details_program(self) -> tuple[str, str]:
        content_response = self.post_json(
            PORTAL_GET_CONTENT_URL,
            {"app": COURSE_DETAILS_APP_CODE, "additionalInfo": False},
            session=True,
        )
        package = json.loads(content_response)["pkg"]
        _, auto_login_html = self.get(PORTAL_CONTENT_URL + urllib.parse.quote(package))

        forms = parse_forms(auto_login_html)
        if not forms:
            raise RuntimeError("Autologin form could not be found.")

        autologin_form = forms[0]
        iframe_url, iframe_html = self.post_form(
            autologin_form.action,
            autologin_form.inputs,
        )
        return iframe_url, iframe_html


class SaisCourseDetailsSession:
    def __init__(self, client: MetuSaisClient) -> None:
        self.client = client
        self.iframe_url = ""
        self.initial_form: FormState | None = None

    @classmethod
    def from_credentials(cls, username: str, password: str) -> SaisCourseDetailsSession:
        return cls(MetuSaisClient(username, password))

    def open(self) -> None:
        self.client.sign_in()
        self.iframe_url, iframe_html = self.client.open_course_details_program()
        forms = parse_forms(iframe_html)
        if not forms:
            raise RuntimeError("Department/semester form could not be found.")
        self.initial_form = forms[0]

    def fetch_offerings(
        self,
        program: Program,
        semester_no: str,
        raw_root: Path,
    ) -> dict[str, Any]:
        if self.initial_form is None:
            self.open()

        assert self.initial_form is not None
        department_value, department_text = choose_department_option(self.initial_form, program)
        semester_value, semester_text = choose_option(
            self.initial_form.selects.get("select_semester", []),
            lambda value, _text: value == semester_no,
            f"{semester_no} semester option",
        )
        payload = dict(self.initial_form.inputs)
        payload.update(
            {
                "select_dept": department_value,
                "select_semester": semester_value,
                "submit_CourseList": "Submit",
            }
        )

        result_url = urllib.parse.urljoin(self.iframe_url, self.initial_form.action or "main.php")
        response_url, result_html = self.client.post_form(result_url, payload, referer=self.iframe_url)
        snapshot = write_raw_offering_snapshot(
            raw_root=raw_root,
            program=program,
            semester_no=semester_no,
            source_url=response_url,
            html=result_html,
        )
        offerings = extract_course_offerings(
            result_html=result_html,
            program=program,
            department_value=department_value,
            department_text=department_text,
            semester_no=semester_no,
            semester_text=semester_text,
        )
        return build_offerings_payload(
            program=program,
            semester_no=semester_no,
            semester_text=semester_text,
            snapshot=snapshot,
            offerings=offerings,
        )


def normalize_text(value: str) -> str:
    value = unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")
        if not separator:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key.strip(), value)


def parse_forms(html: str) -> list[FormState]:
    parser = FormParser()
    parser.feed(html)
    return parser.forms


def parse_tables(html: str) -> list[list[list[str]]]:
    parser = TableParser()
    parser.feed(html)
    return parser.tables


def choose_option(
    options: list[tuple[str, str]],
    predicate: Any,
    label: str,
) -> tuple[str, str]:
    matches = [(value, text) for value, text in options if predicate(value, text)]
    if not matches:
        raise RuntimeError(f"Could not find {label}.")
    return matches[0]


def choose_department_option(form: FormState, program: Program) -> tuple[str, str]:
    options = form.selects.get("select_dept", [])
    exact_value = [
        (value, text)
        for value, text in options
        if value == program.catalog_program_id
    ]
    if exact_value:
        return exact_value[0]

    normalized_name = normalize_text(program.name_en).lower()
    by_name = [
        (value, text)
        for value, text in options
        if normalize_text(text).lower().startswith(normalized_name)
    ]
    if by_name:
        return by_name[0]

    raise RuntimeError(f"Could not find SAIS department option for {program.abbr}.")


def extract_course_offerings(
    result_html: str,
    program: Program,
    department_value: str,
    department_text: str,
    semester_no: str,
    semester_text: str,
) -> list[SaisCourseOffering]:
    course_table = find_course_table(result_html)
    if course_table is None:
        raise RuntimeError("Course table could not be found in SAIS result page.")

    header = course_table[0]
    column_index = {name: header.index(name) for name in header}
    rows: list[SaisCourseOffering] = []

    for row in course_table[1:]:
        if len(row) < len(header):
            continue

        numeric_code = row[column_index["Code"]].strip()
        course_number = parse_numeric_course_number(numeric_code)
        display_code = display_code_for_offering(program.abbr, course_number, numeric_code)
        rows.append(
            SaisCourseOffering(
                program_abbr=program.abbr,
                department_value=department_value,
                department_text=department_text,
                semester_no=semester_no,
                semester_text=semester_text,
                numeric_code=numeric_code,
                display_code=display_code,
                course_number=course_number,
                course_name=row[column_index["Name"]].strip(),
                ects_credit=row[column_index["ECTS Credit"]].strip(),
                credit=row[column_index["Credit"]].strip(),
                level=row[column_index["Level"]].strip(),
                course_type=row[column_index["Type"]].strip(),
            )
        )

    return rows


def find_course_table(html: str) -> list[list[str]] | None:
    for table in parse_tables(html):
        if not table:
            continue
        header = table[0]
        if {"Code", "Name", "ECTS Credit", "Credit", "Level", "Type"}.issubset(header):
            return table
    return None


def parse_numeric_course_number(numeric_code: str) -> int | None:
    if not numeric_code.isdigit() or len(numeric_code) <= 4:
        return None
    suffix = numeric_code[-4:]
    return int(suffix) if suffix.isdigit() else None


def display_code_for_offering(
    program_abbr: str,
    course_number: int | None,
    fallback: str,
) -> str:
    if course_number is None:
        return fallback
    return f"{program_abbr.upper()} {course_number}"


def write_raw_offering_snapshot(
    raw_root: Path,
    program: Program,
    semester_no: str,
    source_url: str,
    html: str,
) -> SourceSnapshot:
    now = dt.datetime.now(dt.timezone.utc)
    payload = html.encode("utf-8")
    content_hash = hashlib.sha256(payload).hexdigest()
    snapshot_dir = (
        raw_root
        / "sais"
        / "offerings"
        / semester_no
        / program.abbr
        / now.strftime("%Y%m%dT%H%M%SZ")
    )
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    content_path = snapshot_dir / "program.html"
    content_path.write_bytes(payload)

    metadata_path = snapshot_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "source_name": "METU SAIS Course Details",
                "source_url": source_url,
                "retrieved_at_utc": now.isoformat(timespec="seconds"),
                "content_sha256": content_hash,
                "parser_version": PARSER_VERSION,
                "program_abbr": program.abbr,
                "semester_no": semester_no,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return SourceSnapshot(
        source_name="METU SAIS Course Details",
        source_url=source_url,
        retrieved_at_utc=now.isoformat(timespec="seconds"),
        content_path=str(content_path),
        content_sha256=content_hash,
    )


def build_offerings_payload(
    program: Program,
    semester_no: str,
    semester_text: str,
    snapshot: SourceSnapshot,
    offerings: list[SaisCourseOffering],
) -> dict[str, Any]:
    return {
        "program": {
            "abbr": program.abbr,
            "catalog_program_id": program.catalog_program_id,
            "name_en": program.name_en,
            "name_tr": program.name_tr,
            "faculty": program.faculty,
        },
        "semester": {
            "semester_no": semester_no,
            "semester_text": semester_text,
        },
        "source": {
            "source_name": snapshot.source_name,
            "source_url": snapshot.source_url,
            "retrieved_at_utc": snapshot.retrieved_at_utc,
            "content_path": snapshot.content_path,
            "content_sha256": snapshot.content_sha256,
            "parser_version": PARSER_VERSION,
        },
        "offerings": [offering.to_dict() for offering in offerings],
        "summary": {
            "offering_count": len(offerings),
            "undergraduate_count": sum(1 for offering in offerings if is_undergraduate(offering)),
        },
    }


def is_undergraduate(offering: SaisCourseOffering) -> bool:
    level_text = normalize_ascii(offering.level.lower())
    if "undergraduate" in level_text:
        return True
    if "lisansustu" in level_text or "graduate" in level_text:
        return False
    if "lisans" in level_text:
        return True
    return offering.course_number is not None and offering.course_number <= 499


def normalize_ascii(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def write_offerings_output(payload: dict[str, Any], processed_root: Path) -> Path:
    semester_no = payload["semester"]["semester_no"]
    program_abbr = payload["program"]["abbr"]
    output_dir = processed_root / "offerings" / semester_no
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{program_abbr}.offerings.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
