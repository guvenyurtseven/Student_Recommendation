#!/usr/bin/env python
"""Scrape METU SAIS View Program Course Details into a CSV file.

Credentials are read from env.local first, or from environment variables if
they are already set.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path


SSO_SIGNIN_URL = "https://student.metu.edu.tr/sso/backend/request/user/signin"
PORTAL_GET_CONTENT_URL = (
    "https://student.metu.edu.tr/portal/backend/request/route/get_content"
)
PORTAL_CONTENT_URL = "https://student.metu.edu.tr/portal/content.php?pkg="
COURSE_DETAILS_APP_CODE = 64
DEPARTMENT_ABBR = "STAT"
TARGET_DEPARTMENT_PREFIX = "Statistics"
TARGET_DEPARTMENT_EXCLUDE_TERMS = ("(Kuzey", "TAU")
TARGET_SEMESTER_NO = "20242"
OUTPUT_CSV = f"{DEPARTMENT_ABBR}-{TARGET_SEMESTER_NO}.csv"
ENV_FILE = "env.local"


def normalize_text(value: str) -> str:
    value = unescape(value)
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


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[FormState] = []
        self._form: FormState | None = None
        self._select: SelectState | None = None
        self._option: OptionState | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}

        if tag.lower() == "form":
            self._form = FormState(
                action=attrs_dict.get("action", ""),
                method=attrs_dict.get("method", "GET").upper(),
            )
            return

        if self._form is None:
            return

        if tag.lower() == "input":
            name = attrs_dict.get("name")
            if name:
                self._form.inputs[name] = attrs_dict.get("value", "")
            return

        if tag.lower() == "select":
            name = attrs_dict.get("name")
            if name:
                self._select = SelectState(name=name)
            return

        if tag.lower() == "option" and self._select is not None:
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
            headers = dict(response.headers)
            token = headers.get("Token") or headers.get("token")
            if token:
                self._token = token
            return response.read().decode("utf-8", errors="replace")

    def post_form(self, url: str, payload: dict[str, str], referer: str | None = None) -> tuple[str, str]:
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


def parse_forms(html: str) -> list[FormState]:
    parser = FormParser()
    parser.feed(html)
    return parser.forms


def parse_tables(html: str) -> list[list[list[str]]]:
    parser = TableParser()
    parser.feed(html)
    return parser.tables


def choose_option(options: list[tuple[str, str]], predicate, label: str) -> tuple[str, str]:
    matches = [(value, text) for value, text in options if predicate(value, text)]
    if not matches:
        raise RuntimeError(f"Could not find {label}.")
    if len(matches) > 1:
        exact = [item for item in matches if "(" not in item[1]]
        if exact:
            return exact[0]
    return matches[0]


def extract_course_rows(
    result_html: str,
    department_text: str,
    semester_text: str,
    department_value: str,
) -> list[dict[str, str]]:
    tables = parse_tables(result_html)

    course_table = None
    for table in tables:
        if not table:
            continue
        header = table[0]
        if {"Code", "Name", "ECTS Credit", "Credit", "Level", "Type"}.issubset(header):
            course_table = table
            break

    if course_table is None:
        raise RuntimeError("Course table could not be found in result page.")

    header = course_table[0]
    column_index = {name: header.index(name) for name in header}
    scraped_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, str]] = []

    for row in course_table[1:]:
        if len(row) < len(header):
            continue

        numeric_code = row[column_index["Code"]]
        suffix = numeric_code[len(department_value) :] if numeric_code.startswith(department_value) else ""
        course_number = str(int(suffix)) if suffix.isdigit() else suffix
        course_code = f"{DEPARTMENT_ABBR} {course_number}" if course_number else numeric_code

        rows.append(
            {
                "department": department_text,
                "semester": semester_text,
                "course_code_numeric": numeric_code,
                "course_code": course_code,
                "course_number": course_number,
                "course_name": row[column_index["Name"]],
                "ects_credit": row[column_index["ECTS Credit"]],
                "credit": row[column_index["Credit"]],
                "level": row[column_index["Level"]],
                "type": row[column_index["Type"]],
                "scraped_at_utc": scraped_at,
            }
        )

    return rows


def scrape_courses(username: str, password: str) -> list[dict[str, str]]:
    client = MetuSaisClient(username, password)
    client.sign_in()
    iframe_url, iframe_html = client.open_course_details_program()

    forms = parse_forms(iframe_html)
    if not forms:
        raise RuntimeError("Department/semester form could not be found.")

    search_form = forms[0]
    department_value, department_text = choose_option(
        search_form.selects.get("select_dept", []),
        lambda value, text: text.startswith(TARGET_DEPARTMENT_PREFIX)
        and not any(term in text for term in TARGET_DEPARTMENT_EXCLUDE_TERMS),
        f"{DEPARTMENT_ABBR} department option",
    )
    semester_value, semester_text = choose_option(
        search_form.selects.get("select_semester", []),
        lambda value, text: value == TARGET_SEMESTER_NO,
        f"{TARGET_SEMESTER_NO} semester option",
    )

    submit_payload = dict(search_form.inputs)
    submit_payload.update(
        {
            "select_dept": department_value,
            "select_semester": semester_value,
            "submit_CourseList": "Submit",
        }
    )

    result_url = urllib.parse.urljoin(iframe_url, search_form.action or "main.php")
    _, result_html = client.post_form(result_url, submit_payload, referer=iframe_url)
    return extract_course_rows(result_html, department_text, semester_text, department_value)


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    if not rows:
        raise RuntimeError("No course rows were scraped.")

    fieldnames = list(rows[0].keys())
    with output_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    load_env_file(Path(__file__).with_name(ENV_FILE))

    username = os.environ.get("METU_USERNAME")
    password = os.environ.get("METU_PASSWORD")

    if not username or not password:
        print(
            f"METU_USERNAME and METU_PASSWORD are required in {ENV_FILE} or environment variables.",
            file=sys.stderr,
        )
        return 2

    output_path = Path(__file__).with_name(OUTPUT_CSV)
    rows = scrape_courses(username, password)
    write_csv(rows, output_path)
    print(f"Wrote {len(rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
