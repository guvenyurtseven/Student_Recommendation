#!/usr/bin/env python
"""Scrape prerequisite relations for one department and build a DAG.

Default usage:
    python scrape_prerequisite_graph.py --abbr CENG --semesters 20241 20242

The script reads exactly two course CSV files, such as CENG-20241.csv and
CENG-20242.csv, then scrapes prerequisite data from METU SAIS for the unique
undergraduate courses in those files.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
from collections import defaultdict, deque
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import scrape_metu_program_courses as sais


UNDERGRAD_MAX_COURSE_NUMBER = 499
COURSE_CODE_SUFFIX_WIDTH = 4
ENV_FILE = "env.local"

SUBMIT_BUTTON_FIELDS = {
    "SubmitCourseInfo",
    "SubmitPrerequisite",
    "SubmitReplacement",
    "SubmitBack",
    "SubmitThesisWork",
    "SubmitName",
}

DEFAULT_NUMERIC_DEPARTMENT_ABBRS = {
    "231": "CHEM",
    "234": "CHEM",
    "236": "MATH",
    "238": "BIOL",
    "240": "HIST",
    "246": "STAT",
    "257": "PHYS",
    "450": "FLE",
    "562": "CE",
    "563": "CHE",
    "564": "GEOE",
    "567": "EEE",
    "569": "ME",
    "571": "CENG",
    "572": "AE",
    "877": "OHS",
}


@dataclass
class CourseNode:
    id: str
    course_code: str
    course_number: int | None
    course_name: str
    department: str
    source: str
    offered_semesters: set[str] = field(default_factory=set)
    level: str = ""
    course_type: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "course_code": self.course_code,
            "course_number": self.course_number,
            "course_name": self.course_name,
            "department": self.department,
            "source": self.source,
            "offered_semesters": sorted(self.offered_semesters),
            "level": self.level,
            "type": self.course_type,
        }


@dataclass(frozen=True)
class PrerequisiteRow:
    course_code_numeric: str
    course_name: str
    set_no: str
    min_grade: str
    prereq_type: str
    position: str


@dataclass
class LoadedCourses:
    abbr: str
    csv_paths: list[Path]
    semester_numbers: list[str]
    department_value: str
    department_text: str
    nodes: dict[str, CourseNode]
    courses_by_semester: dict[str, list[str]]


class RadioValueParser(HTMLParser):
    def __init__(self, radio_name: str) -> None:
        super().__init__(convert_charrefs=True)
        self.radio_name = radio_name
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "input":
            return

        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if (
            attrs_dict.get("type", "").lower() == "radio"
            and attrs_dict.get("name") == self.radio_name
            and attrs_dict.get("value")
        ):
            self.values.append(attrs_dict["value"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a prerequisite DAG from exactly two METU course CSV files."
    )
    parser.add_argument(
        "--abbr",
        help="Department abbreviation used in filenames and output, for example CENG.",
    )
    parser.add_argument(
        "--semesters",
        nargs=2,
        metavar=("SEMESTER_1", "SEMESTER_2"),
        help="Two semester numbers, for example 20241 20242. Used with --abbr.",
    )
    parser.add_argument(
        "--csv",
        nargs=2,
        metavar=("CSV_1", "CSV_2"),
        help="Exactly two CSV files to read. Overrides --semesters filename creation.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where graph JSON and helper CSV files will be written.",
    )
    parser.add_argument(
        "--env-file",
        default=ENV_FILE,
        help="Credential file containing METU_USERNAME and METU_PASSWORD.",
    )
    return parser.parse_args()


def parse_semester_no_from_path(path: Path) -> str:
    match = re.search(r"-(\d{5})\.csv$", path.name, flags=re.IGNORECASE)
    if not match:
        raise RuntimeError(
            f"Could not infer semester number from {path.name}. Expected ABBR-20242.csv."
        )
    return match.group(1)


def parse_abbr_from_path(path: Path) -> str:
    match = re.match(r"([A-Za-z0-9]+)-\d{5}\.csv$", path.name)
    if not match:
        raise RuntimeError(f"Could not infer department abbreviation from {path.name}.")
    return match.group(1).upper()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        required = {
            "department",
            "semester",
            "course_code_numeric",
            "course_code",
            "course_number",
            "course_name",
            "level",
            "type",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"{path.name} is missing columns: {', '.join(sorted(missing))}")
        return list(reader)


def numeric_course_number(course_code_numeric: str) -> int | None:
    if not course_code_numeric.isdigit() or len(course_code_numeric) <= COURSE_CODE_SUFFIX_WIDTH:
        return None
    return int(course_code_numeric[-COURSE_CODE_SUFFIX_WIDTH:])


def numeric_department_value(course_code_numeric: str) -> str:
    return course_code_numeric[:-COURSE_CODE_SUFFIX_WIDTH]


def normalize_course_code(abbr: str, course_number: int | None, fallback: str) -> str:
    if course_number is None:
        return fallback
    return f"{abbr} {course_number}"


def load_two_csvs(csv_paths: list[Path], abbr: str | None) -> LoadedCourses:
    if len(csv_paths) != 2:
        raise RuntimeError("Exactly two CSV files are required.")

    for path in csv_paths:
        if not path.exists():
            raise RuntimeError(f"CSV file does not exist: {path}")

    inferred_abbrs = {parse_abbr_from_path(path) for path in csv_paths}
    if len(inferred_abbrs) != 1:
        raise RuntimeError(f"CSV files must belong to one department: {sorted(inferred_abbrs)}")

    csv_abbr = inferred_abbrs.pop()
    abbr = (abbr or csv_abbr).upper()
    if abbr != csv_abbr:
        raise RuntimeError(f"--abbr {abbr} does not match CSV filenames ({csv_abbr}).")

    semester_numbers = [parse_semester_no_from_path(path) for path in csv_paths]
    if len(set(semester_numbers)) != 2:
        raise RuntimeError(f"Two different semester files are required: {semester_numbers}")

    nodes: dict[str, CourseNode] = {}
    courses_by_semester: dict[str, list[str]] = {semester: [] for semester in semester_numbers}
    department_texts: set[str] = set()
    department_values: set[str] = set()

    for path, semester_no in zip(csv_paths, semester_numbers):
        for row in read_csv_rows(path):
            course_number = numeric_course_number(row["course_code_numeric"])
            if course_number is None or course_number > UNDERGRAD_MAX_COURSE_NUMBER:
                continue

            course_id = row["course_code_numeric"].strip()
            department_texts.add(row["department"].strip())
            department_values.add(numeric_department_value(course_id))

            if course_id not in nodes:
                nodes[course_id] = CourseNode(
                    id=course_id,
                    course_code=normalize_course_code(abbr, course_number, row["course_code"]),
                    course_number=course_number,
                    course_name=row["course_name"].strip(),
                    department=row["department"].strip(),
                    source="offered_course",
                    level=row["level"].strip(),
                    course_type=row["type"].strip(),
                )

            nodes[course_id].offered_semesters.add(semester_no)
            courses_by_semester[semester_no].append(course_id)

    if not nodes:
        raise RuntimeError("No undergraduate courses were found in the two CSV files.")
    if len(department_texts) != 1:
        raise RuntimeError(f"CSV files contain multiple departments: {sorted(department_texts)}")
    if len(department_values) != 1:
        raise RuntimeError(f"CSV files contain multiple numeric department codes: {sorted(department_values)}")

    return LoadedCourses(
        abbr=abbr,
        csv_paths=csv_paths,
        semester_numbers=semester_numbers,
        department_value=department_values.pop(),
        department_text=department_texts.pop(),
        nodes=nodes,
        courses_by_semester={
            semester: sorted(set(course_ids), key=lambda code: nodes[code].course_number or 0)
            for semester, course_ids in courses_by_semester.items()
        },
    )


def extract_radio_values(html: str, radio_name: str) -> set[str]:
    parser = RadioValueParser(radio_name)
    parser.feed(html)
    return set(parser.values)


def parse_prerequisite_rows(html: str) -> list[PrerequisiteRow]:
    rows: list[PrerequisiteRow] = []
    for table in sais.parse_tables(html):
        if not table or "Course Code" not in table[0] or "Set No" not in table[0]:
            continue

        header = table[0]
        index = {name: header.index(name) for name in header}
        for row in table[1:]:
            if len(row) < len(header):
                continue

            prereq_code = row[index["Course Code"]].strip()
            course_number = numeric_course_number(prereq_code)
            if course_number is None or course_number > UNDERGRAD_MAX_COURSE_NUMBER:
                continue

            rows.append(
                PrerequisiteRow(
                    course_code_numeric=prereq_code,
                    course_name=row[index.get("Name", "")].strip() if "Name" in index else "",
                    set_no=row[index.get("Set No", "")].strip() if "Set No" in index else "",
                    min_grade=row[index.get("Min Grade", "")].strip() if "Min Grade" in index else "",
                    prereq_type=row[index.get("Type", "")].strip() if "Type" in index else "",
                    position=row[index.get("Position", "")].strip() if "Position" in index else "",
                )
            )
    return rows


def choose_select_value(
    form: sais.FormState,
    select_name: str,
    wanted_value: str,
    label: str,
) -> str:
    options = form.selects.get(select_name, [])
    for value, _text in options:
        if value == wanted_value:
            return value
    raise RuntimeError(f"Could not find {label} value {wanted_value}.")


class PrerequisiteScraper:
    def __init__(self, username: str, password: str, loaded: LoadedCourses) -> None:
        self.loaded = loaded
        self.client = sais.MetuSaisClient(username, password)
        self.iframe_url = ""
        self.initial_form: sais.FormState | None = None

    def sign_in_and_open_program(self) -> None:
        self.client.sign_in()
        self.iframe_url, iframe_html = self.client.open_course_details_program()
        forms = sais.parse_forms(iframe_html)
        if not forms:
            raise RuntimeError("Department/semester form could not be found.")
        self.initial_form = forms[0]

    def open_semester_course_list(self, semester_no: str) -> tuple[str, str, sais.FormState]:
        if self.initial_form is None:
            raise RuntimeError("Program is not open yet.")

        department_value = choose_select_value(
            self.initial_form,
            "select_dept",
            self.loaded.department_value,
            "department",
        )
        semester_value = choose_select_value(
            self.initial_form,
            "select_semester",
            semester_no,
            "semester",
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
        forms = sais.parse_forms(result_html)
        if not forms:
            raise RuntimeError(f"Course list form could not be found for semester {semester_no}.")
        return response_url, result_html, forms[0]

    def scrape_course_prerequisites(
        self,
        result_url: str,
        result_form: sais.FormState,
        course_code_numeric: str,
    ) -> list[PrerequisiteRow]:
        payload = dict(result_form.inputs)
        for field_name in SUBMIT_BUTTON_FIELDS:
            payload.pop(field_name, None)

        payload["text_course_code"] = course_code_numeric
        payload["SubmitPrerequisite"] = "Prerequisite"

        prereq_url = urllib.parse.urljoin(result_url, result_form.action or "main.php")
        _, prereq_html = self.client.post_form(prereq_url, payload, referer=result_url)
        return parse_prerequisite_rows(prereq_html)

    def scrape(self) -> dict[str, list[PrerequisiteRow]]:
        self.sign_in_and_open_program()
        prerequisites_by_course: dict[str, list[PrerequisiteRow]] = {}
        scraped_courses: set[str] = set()

        for semester_no in self.loaded.semester_numbers:
            result_url, result_html, result_form = self.open_semester_course_list(semester_no)
            available_courses = extract_radio_values(result_html, "text_course_code")

            for course_id in self.loaded.courses_by_semester[semester_no]:
                if course_id in scraped_courses:
                    continue
                if course_id not in available_courses:
                    print(
                        f"Warning: {course_id} is in CSV but not in SAIS list for {semester_no}.",
                        file=sys.stderr,
                    )
                    continue

                prerequisites_by_course[course_id] = self.scrape_course_prerequisites(
                    result_url,
                    result_form,
                    course_id,
                )
                scraped_courses.add(course_id)

        for course_id in self.loaded.nodes:
            prerequisites_by_course.setdefault(course_id, [])

        return prerequisites_by_course


def display_code_for_numeric(
    code_numeric: str,
    target_department_value: str,
    target_abbr: str,
) -> str:
    course_number = numeric_course_number(code_numeric)
    if course_number is None:
        return code_numeric

    department_value = numeric_department_value(code_numeric)
    if department_value == target_department_value:
        abbr = target_abbr
    else:
        abbr = DEFAULT_NUMERIC_DEPARTMENT_ABBRS.get(department_value, department_value)
    return normalize_course_code(abbr, course_number, code_numeric)


def ensure_prereq_node(
    nodes: dict[str, CourseNode],
    prereq: PrerequisiteRow,
    loaded: LoadedCourses,
) -> None:
    if prereq.course_code_numeric in nodes:
        if not nodes[prereq.course_code_numeric].course_name and prereq.course_name:
            nodes[prereq.course_code_numeric].course_name = prereq.course_name
        return

    code_number = numeric_course_number(prereq.course_code_numeric)
    nodes[prereq.course_code_numeric] = CourseNode(
        id=prereq.course_code_numeric,
        course_code=display_code_for_numeric(
            prereq.course_code_numeric,
            loaded.department_value,
            loaded.abbr,
        ),
        course_number=code_number,
        course_name=prereq.course_name,
        department="external_or_not_offered_in_input_csv",
        source="external_prerequisite",
        level="",
        course_type=prereq.prereq_type,
    )


def build_graph(
    loaded: LoadedCourses,
    prerequisites_by_course: dict[str, list[PrerequisiteRow]],
) -> dict[str, Any]:
    nodes = dict(loaded.nodes)
    edge_keys: set[tuple[str, str, str, str]] = set()
    edges: list[dict[str, Any]] = []
    prerequisite_sets_by_course: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for course_id, prereq_rows in prerequisites_by_course.items():
        for prereq in prereq_rows:
            ensure_prereq_node(nodes, prereq, loaded)
            edge_key = (prereq.course_code_numeric, course_id, prereq.set_no, prereq.min_grade)
            if edge_key in edge_keys:
                continue
            edge_keys.add(edge_key)

            prerequisite_sets_by_course[course_id][prereq.set_no].append(prereq.course_code_numeric)
            edges.append(
                {
                    "from": prereq.course_code_numeric,
                    "to": course_id,
                    "from_course_code": nodes[prereq.course_code_numeric].course_code,
                    "to_course_code": nodes[course_id].course_code,
                    "set_no": prereq.set_no,
                    "min_grade": prereq.min_grade,
                    "type": prereq.prereq_type,
                    "position": prereq.position,
                }
            )

    edges.sort(key=lambda edge: (edge["to_course_code"], edge["set_no"], edge["from_course_code"]))

    prerequisites_simple: dict[str, list[str]] = defaultdict(list)
    dependents_simple: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        prerequisites_simple[edge["to"]].append(edge["from"])
        dependents_simple[edge["from"]].append(edge["to"])

    is_dag, topological_order, cycle_nodes = topological_sort(set(nodes), edges)
    if not is_dag:
        cycle_codes = [nodes[node_id].course_code for node_id in cycle_nodes]
        raise RuntimeError(f"Prerequisite graph contains a cycle: {cycle_codes}")

    generated_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return {
        "metadata": {
            "department_abbr": loaded.abbr,
            "department": loaded.department_text,
            "department_value": loaded.department_value,
            "semesters": loaded.semester_numbers,
            "csv_files": [path.name for path in loaded.csv_paths],
            "generated_at_utc": generated_at,
            "undergraduate_max_course_number": UNDERGRAD_MAX_COURSE_NUMBER,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "is_dag": True,
            "edge_direction": "prerequisite -> course",
        },
        "nodes": [nodes[node_id].to_json() for node_id in sorted(nodes, key=lambda key: nodes[key].course_code)],
        "edges": edges,
        "prerequisites_by_course": {
            course_id: sorted(set(prereqs), key=lambda key: nodes[key].course_code)
            for course_id, prereqs in prerequisites_simple.items()
        },
        "prerequisites_by_course_code": {
            nodes[course_id].course_code: [
                nodes[prereq_id].course_code
                for prereq_id in sorted(set(prereqs), key=lambda key: nodes[key].course_code)
            ]
            for course_id, prereqs in prerequisites_simple.items()
        },
        "dependents_by_course": {
            course_id: sorted(set(dependents), key=lambda key: nodes[key].course_code)
            for course_id, dependents in dependents_simple.items()
        },
        "dependents_by_course_code": {
            nodes[course_id].course_code: [
                nodes[dependent_id].course_code
                for dependent_id in sorted(set(dependents), key=lambda key: nodes[key].course_code)
            ]
            for course_id, dependents in dependents_simple.items()
        },
        "prerequisite_sets_by_course": {
            course_id: {
                set_no: sorted(set(prereqs), key=lambda key: nodes[key].course_code)
                for set_no, prereqs in set_map.items()
            }
            for course_id, set_map in prerequisite_sets_by_course.items()
        },
        "prerequisite_sets_by_course_code": {
            nodes[course_id].course_code: {
                set_no: [
                    nodes[prereq_id].course_code
                    for prereq_id in sorted(set(prereqs), key=lambda key: nodes[key].course_code)
                ]
                for set_no, prereqs in set_map.items()
            }
            for course_id, set_map in prerequisite_sets_by_course.items()
        },
        "topological_order": topological_order,
        "topological_order_course_code": [
            nodes[node_id].course_code for node_id in topological_order
        ],
    }


def topological_sort(node_ids: set[str], edges: list[dict[str, Any]]) -> tuple[bool, list[str], list[str]]:
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    indegree: dict[str, int] = {node_id: 0 for node_id in node_ids}

    for edge in edges:
        source = edge["from"]
        target = edge["to"]
        adjacency.setdefault(source, []).append(target)
        indegree.setdefault(source, 0)
        indegree[target] = indegree.get(target, 0) + 1

    queue = deque(sorted([node_id for node_id, degree in indegree.items() if degree == 0]))
    order: list[str] = []

    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for target in sorted(adjacency.get(node_id, [])):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if len(order) == len(indegree):
        return True, order, []

    cycle_nodes = sorted([node_id for node_id, degree in indegree.items() if degree > 0])
    return False, order, cycle_nodes


def write_outputs(graph: dict[str, Any], output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = graph["metadata"]
    abbr = metadata["department_abbr"]
    semester_part = "-".join(metadata["semesters"])
    json_path = output_dir / f"{abbr}-{semester_part}-prerequisite-dag.json"
    edges_path = output_dir / f"{abbr}-{semester_part}-prerequisite-edges.csv"
    nodes_path = output_dir / f"{abbr}-{semester_part}-prerequisite-nodes.csv"

    json_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    with edges_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        fieldnames = [
            "from",
            "from_course_code",
            "to",
            "to_course_code",
            "set_no",
            "min_grade",
            "type",
            "position",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(graph["edges"])

    with nodes_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        fieldnames = [
            "id",
            "course_code",
            "course_number",
            "course_name",
            "department",
            "source",
            "offered_semesters",
            "level",
            "type",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for node in graph["nodes"]:
            row = dict(node)
            row["offered_semesters"] = ";".join(row["offered_semesters"])
            writer.writerow(row)

    return json_path, edges_path, nodes_path


def resolve_csv_paths(args: argparse.Namespace, cwd: Path) -> tuple[str | None, list[Path]]:
    if args.csv:
        return args.abbr, [Path(item).resolve() for item in args.csv]

    if not args.abbr or not args.semesters:
        raise RuntimeError("Use either --csv CSV1 CSV2 or --abbr ABBR --semesters SEM1 SEM2.")

    abbr = args.abbr.upper()
    return abbr, [(cwd / f"{abbr}-{semester}.csv").resolve() for semester in args.semesters]


def main() -> int:
    args = parse_args()
    cwd = Path.cwd()
    sais.load_env_file(cwd / args.env_file)

    username = os.environ.get("METU_USERNAME")
    password = os.environ.get("METU_PASSWORD")
    if not username or not password:
        print(
            f"METU_USERNAME and METU_PASSWORD are required in {args.env_file} or environment variables.",
            file=sys.stderr,
        )
        return 2

    try:
        abbr, csv_paths = resolve_csv_paths(args, cwd)
        loaded = load_two_csvs(csv_paths, abbr)
        scraper = PrerequisiteScraper(username, password, loaded)
        prerequisites_by_course = scraper.scrape()
        graph = build_graph(loaded, prerequisites_by_course)
        json_path, edges_path, nodes_path = write_outputs(graph, Path(args.output_dir).resolve())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    metadata = graph["metadata"]
    print(
        f"Wrote DAG with {metadata['node_count']} nodes and {metadata['edge_count']} edges."
    )
    print(f"JSON: {json_path}")
    print(f"Edges CSV: {edges_path}")
    print(f"Nodes CSV: {nodes_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
