from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
from collections import deque
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import scrape_metu_program_courses as sais


COURSE_CODE_SUFFIX_WIDTH = 4
ENV_FILE = "env.local"
DEFAULT_OUTPUT_DIR = "data/processed/prerequisites"

SUBMIT_BUTTON_FIELDS = {
    "SubmitCourseInfo",
    "SubmitPrerequisite",
    "SubmitReplacement",
    "SubmitBack",
    "SubmitThesisWork",
    "SubmitName",
}

NUMERIC_DEPARTMENT_ABBRS = {
    "230": "PHYS",
    "231": "CHEM",
    "234": "CHEM",
    "236": "MATH",
    "238": "BIOL",
    "240": "HIST",
    "246": "STAT",
    "257": "PHYS",
    "312": "BA",
    "450": "FLE",
    "560": "ENVE",
    "562": "CE",
    "563": "CHE",
    "564": "GEOE",
    "565": "MINE",
    "566": "PETE",
    "567": "EE",
    "568": "IE",
    "569": "ME",
    "570": "METE",
    "571": "CENG",
    "572": "AE",
    "573": "FDE",
    "639": "ENG",
    "642": "TURK",
    "877": "OHS",
    "901": "IS",
}


@dataclass
class CourseListContext:
    result_url: str
    result_form: sais.FormState
    available_courses: set[str]


@dataclass(frozen=True)
class PrerequisiteRecord:
    course_code_numeric: str
    course_code: str
    course_name: str
    set_no: str
    min_grade: str
    prereq_type: str
    position: str


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
        description="Build recursive prerequisite closure from processed curriculum JSON files."
    )
    parser.add_argument(
        "--programs",
        nargs="*",
        help="Program abbreviations to process. Defaults to all curriculum JSON files.",
    )
    parser.add_argument(
        "--curricula-dir",
        default="data/processed/curricula",
        help="Directory containing *-latest.curriculum.json files.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where closure JSON/CSV outputs will be written.",
    )
    parser.add_argument(
        "--env-file",
        default=ENV_FILE,
        help="Credential file containing METU_USERNAME and METU_PASSWORD.",
    )
    parser.add_argument(
        "--semesters",
        nargs="*",
        help="SAIS semester numbers to search. Defaults to all semesters listed by SAIS.",
    )
    parser.add_argument(
        "--max-courses",
        type=int,
        help="Debug limit for number of queued courses to scrape.",
    )
    return parser.parse_args()


def normalize_text(value: str) -> str:
    value = unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def numeric_course_number(course_code_numeric: str) -> int | None:
    if not course_code_numeric.isdigit() or len(course_code_numeric) <= COURSE_CODE_SUFFIX_WIDTH:
        return None
    return int(course_code_numeric[-COURSE_CODE_SUFFIX_WIDTH:])


def numeric_department_value(course_code_numeric: str) -> str:
    return course_code_numeric[:-COURSE_CODE_SUFFIX_WIDTH]


def is_5xx_or_above_graduate_code(course_code_numeric: str) -> bool:
    number = numeric_course_number(course_code_numeric)
    if number is None:
        return True
    # METU service courses such as HIST2201 are undergraduate and must stay.
    # The graduate exclusion intended here is the usual 5xx/6xx/7xx/8xx/9xx block.
    return 500 <= number <= 999


def display_code_for_numeric(course_code_numeric: str) -> str:
    number = numeric_course_number(course_code_numeric)
    department_value = numeric_department_value(course_code_numeric)
    abbr = NUMERIC_DEPARTMENT_ABBRS.get(department_value, department_value)
    return f"{abbr} {number}" if number is not None else course_code_numeric


def extract_radio_values(html: str, radio_name: str) -> set[str]:
    parser = RadioValueParser(radio_name)
    parser.feed(html)
    return set(parser.values)


def parse_prerequisite_rows(
    html: str,
    numeric_to_display: dict[str, str],
) -> list[PrerequisiteRecord]:
    records: list[PrerequisiteRecord] = []
    for table in sais.parse_tables(html):
        if not table or "Course Code" not in table[0] or "Set No" not in table[0]:
            continue

        header = table[0]
        index = {name: header.index(name) for name in header}
        for row in table[1:]:
            if len(row) < len(header):
                continue
            numeric_code = row[index["Course Code"]].strip()
            if is_5xx_or_above_graduate_code(numeric_code):
                continue
            records.append(
                PrerequisiteRecord(
                    course_code_numeric=numeric_code,
                    course_code=numeric_to_display.get(
                        numeric_code,
                        display_code_for_numeric(numeric_code),
                    ),
                    course_name=row[index["Name"]].strip() if "Name" in index else "",
                    set_no=row[index["Set No"]].strip() if "Set No" in index else "",
                    min_grade=row[index["Min Grade"]].strip() if "Min Grade" in index else "",
                    prereq_type=row[index["Type"]].strip() if "Type" in index else "",
                    position=row[index["Position"]].strip() if "Position" in index else "",
                )
            )
    return records


def load_curriculum_files(curricula_dir: Path, wanted_programs: set[str] | None) -> list[dict[str, Any]]:
    curricula: list[dict[str, Any]] = []
    for path in sorted(curricula_dir.glob("*-latest.curriculum.json")):
        program_abbr = path.name.split("-", 1)[0].upper()
        if wanted_programs is not None and program_abbr not in wanted_programs:
            continue
        curricula.append(json.loads(path.read_text(encoding="utf-8")))

    if not curricula:
        raise RuntimeError("No matching curriculum JSON files found.")
    return curricula


def seed_nodes_from_curricula(curricula: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    for curriculum in curricula:
        program_abbr = curriculum["program"]["abbr"]
        for requirement in curriculum["requirements"]:
            for option in requirement["options"]:
                numeric_code = option.get("numeric_code")
                if not numeric_code or is_5xx_or_above_graduate_code(numeric_code):
                    continue
                node = nodes.setdefault(
                    numeric_code,
                    {
                        "id": numeric_code,
                        "course_code": option["course_code"],
                        "course_number": numeric_course_number(numeric_code),
                        "course_name": option.get("course_title", ""),
                        "sources": set(),
                        "curriculum_programs": set(),
                        "requirement_types": set(),
                        "scrape_status": "pending",
                        "found_semester": "",
                    },
                )
                node["sources"].add("curriculum")
                node["curriculum_programs"].add(program_abbr)
                node["requirement_types"].add(requirement["requirement_type"])
                if not node["course_name"] and option.get("course_title"):
                    node["course_name"] = option["course_title"]
    return nodes


class SaisPrerequisiteLookup:
    def __init__(
        self,
        username: str,
        password: str,
        numeric_to_display: dict[str, str],
        preferred_semesters: list[str] | None = None,
    ) -> None:
        self.client = sais.MetuSaisClient(username, password)
        self.numeric_to_display = numeric_to_display
        self.preferred_semesters = preferred_semesters
        self.iframe_url = ""
        self.initial_form: sais.FormState | None = None
        self.semester_values: list[str] = []
        self.department_values: set[str] = set()
        self.course_list_cache: dict[tuple[str, str], CourseListContext | None] = {}

    def open(self) -> None:
        self.client.sign_in()
        self.iframe_url, iframe_html = self.client.open_course_details_program()
        forms = sais.parse_forms(iframe_html)
        if not forms:
            raise RuntimeError("Department/semester form could not be found.")
        self.initial_form = forms[0]
        self.department_values = {
            value for value, _text in self.initial_form.selects.get("select_dept", [])
        }
        all_semesters = [
            value for value, _text in self.initial_form.selects.get("select_semester", [])
        ]
        if self.preferred_semesters:
            preferred = set(self.preferred_semesters)
            self.semester_values = [value for value in all_semesters if value in preferred]
        else:
            self.semester_values = all_semesters
        if not self.semester_values:
            raise RuntimeError("No SAIS semesters are available to search.")

    def get_course_list(self, department_value: str, semester_value: str) -> CourseListContext | None:
        cache_key = (department_value, semester_value)
        if cache_key in self.course_list_cache:
            return self.course_list_cache[cache_key]
        if self.initial_form is None:
            raise RuntimeError("SAIS program is not open.")

        if department_value not in self.department_values:
            self.course_list_cache[cache_key] = None
            return None

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
            self.course_list_cache[cache_key] = None
            return None

        context = CourseListContext(
            result_url=response_url,
            result_form=forms[0],
            available_courses=extract_radio_values(result_html, "text_course_code"),
        )
        self.course_list_cache[cache_key] = context
        return context

    def find_course(self, course_code_numeric: str) -> tuple[str, CourseListContext] | None:
        department_value = numeric_department_value(course_code_numeric)
        if department_value not in self.department_values:
            return None

        for semester_value in self.semester_values:
            context = self.get_course_list(department_value, semester_value)
            if context and course_code_numeric in context.available_courses:
                return semester_value, context
        return None

    def scrape_prerequisites(self, course_code_numeric: str) -> tuple[list[PrerequisiteRecord], str, str]:
        found = self.find_course(course_code_numeric)
        if not found:
            return [], "", "not_found_in_searched_offerings"

        semester_value, context = found
        payload = dict(context.result_form.inputs)
        for field_name in SUBMIT_BUTTON_FIELDS:
            payload.pop(field_name, None)
        payload["text_course_code"] = course_code_numeric
        payload["SubmitPrerequisite"] = "Prerequisite"

        prereq_url = urllib.parse.urljoin(context.result_url, context.result_form.action or "main.php")
        _, html = self.client.post_form(prereq_url, payload, referer=context.result_url)
        return parse_prerequisite_rows(html, self.numeric_to_display), semester_value, "scraped"


def build_closure(
    curricula: list[dict[str, Any]],
    username: str,
    password: str,
    preferred_semesters: list[str] | None = None,
    max_courses: int | None = None,
) -> dict[str, Any]:
    nodes = seed_nodes_from_curricula(curricula)
    numeric_to_display = {
        node_id: node["course_code"]
        for node_id, node in nodes.items()
    }

    lookup = SaisPrerequisiteLookup(
        username=username,
        password=password,
        numeric_to_display=numeric_to_display,
        preferred_semesters=preferred_semesters,
    )
    lookup.open()

    queue: deque[str] = deque(sorted(nodes))
    queued: set[str] = set(queue)
    scraped: set[str] = set()
    unresolved: list[dict[str, str]] = []
    edge_keys: set[tuple[str, str, str, str]] = set()
    edges: list[dict[str, str]] = []
    scraped_count = 0

    while queue:
        course_id = queue.popleft()
        if course_id in scraped:
            continue
        if max_courses is not None and scraped_count >= max_courses:
            break

        records, found_semester, status = lookup.scrape_prerequisites(course_id)
        scraped.add(course_id)
        scraped_count += 1
        nodes[course_id]["scrape_status"] = status
        nodes[course_id]["found_semester"] = found_semester

        if status != "scraped":
            unresolved.append(
                {
                    "course_code_numeric": course_id,
                    "course_code": nodes[course_id]["course_code"],
                    "reason": status,
                }
            )
            continue

        for record in records:
            prereq_id = record.course_code_numeric
            prereq_node = nodes.setdefault(
                prereq_id,
                {
                    "id": prereq_id,
                    "course_code": record.course_code,
                    "course_number": numeric_course_number(prereq_id),
                    "course_name": record.course_name,
                    "sources": set(),
                    "curriculum_programs": set(),
                    "requirement_types": set(),
                    "scrape_status": "pending",
                    "found_semester": "",
                },
            )
            prereq_node["sources"].add("prerequisite_closure")
            if not prereq_node["course_name"] and record.course_name:
                prereq_node["course_name"] = record.course_name
            numeric_to_display.setdefault(prereq_id, prereq_node["course_code"])

            edge_key = (prereq_id, course_id, record.set_no, record.min_grade)
            if edge_key not in edge_keys:
                edge_keys.add(edge_key)
                edges.append(
                    {
                        "from": prereq_id,
                        "from_course_code": prereq_node["course_code"],
                        "to": course_id,
                        "to_course_code": nodes[course_id]["course_code"],
                        "set_no": record.set_no,
                        "min_grade": record.min_grade,
                        "type": record.prereq_type,
                        "position": record.position,
                    }
                )

            if (
                prereq_id not in scraped
                and prereq_id not in queued
                and not is_5xx_or_above_graduate_code(prereq_id)
            ):
                queue.append(prereq_id)
                queued.add(prereq_id)

    return make_graph(curricula, nodes, edges, unresolved, lookup.semester_values)


def make_graph(
    curricula: list[dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, str]],
    unresolved: list[dict[str, str]],
    searched_semesters: list[str],
) -> dict[str, Any]:
    edges.sort(key=lambda edge: (edge["to_course_code"], edge["set_no"], edge["from_course_code"]))
    node_payloads = []
    for node_id in sorted(nodes, key=lambda key: nodes[key]["course_code"]):
        node = nodes[node_id]
        node_payloads.append(
            {
                "id": node["id"],
                "course_code": node["course_code"],
                "course_number": node["course_number"],
                "course_name": node["course_name"],
                "sources": sorted(node["sources"]),
                "curriculum_programs": sorted(node["curriculum_programs"]),
                "requirement_types": sorted(node["requirement_types"]),
                "scrape_status": node["scrape_status"],
                "found_semester": node["found_semester"],
            }
        )

    node_ids = set(nodes)
    is_dag, topological_order = topological_sort(node_ids, edges)
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    program_abbrs = sorted({curriculum["program"]["abbr"] for curriculum in curricula})

    return {
        "metadata": {
            "programs": program_abbrs,
            "generated_at_utc": generated_at,
            "searched_semesters": searched_semesters,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "unresolved_count": len(unresolved),
            "is_dag": is_dag,
            "edge_direction": "prerequisite -> course",
        },
        "nodes": node_payloads,
        "edges": edges,
        "unresolved": unresolved,
        "topological_order": topological_order,
        "topological_order_course_code": [
            nodes[node_id]["course_code"] for node_id in topological_order
        ],
    }


def topological_sort(node_ids: set[str], edges: list[dict[str, str]]) -> tuple[bool, list[str]]:
    indegree = {node_id: 0 for node_id in node_ids}
    adjacency = {node_id: [] for node_id in node_ids}
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

    return len(order) == len(indegree), order


def output_stem(programs: list[str]) -> str:
    if len(programs) == 1:
        return f"{programs[0]}-latest-prerequisite-closure"
    return "engineering-latest-prerequisite-closure"


def write_outputs(graph: dict[str, Any], output_dir: Path) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = output_stem(graph["metadata"]["programs"])
    json_path = output_dir / f"{stem}.json"
    nodes_path = output_dir / f"{stem}-nodes.csv"
    edges_path = output_dir / f"{stem}-edges.csv"
    unresolved_path = output_dir / f"{stem}-unresolved.csv"

    json_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    with nodes_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        fieldnames = [
            "id",
            "course_code",
            "course_number",
            "course_name",
            "sources",
            "curriculum_programs",
            "requirement_types",
            "scrape_status",
            "found_semester",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for node in graph["nodes"]:
            row = dict(node)
            row["sources"] = ";".join(row["sources"])
            row["curriculum_programs"] = ";".join(row["curriculum_programs"])
            row["requirement_types"] = ";".join(row["requirement_types"])
            writer.writerow(row)

    with edges_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
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

    with unresolved_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        fieldnames = ["course_code_numeric", "course_code", "reason"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(graph["unresolved"])

    return json_path, nodes_path, edges_path, unresolved_path


def main() -> int:
    args = parse_args()
    sais.load_env_file(Path(args.env_file))
    username = os.environ.get("METU_USERNAME")
    password = os.environ.get("METU_PASSWORD")
    if not username or not password:
        print(
            f"METU_USERNAME and METU_PASSWORD are required in {args.env_file} or environment variables.",
            file=sys.stderr,
        )
        return 2

    wanted_programs = {abbr.upper() for abbr in args.programs} if args.programs else None
    try:
        curricula = load_curriculum_files(Path(args.curricula_dir), wanted_programs)
        graph = build_closure(
            curricula=curricula,
            username=username,
            password=password,
            preferred_semesters=args.semesters,
            max_courses=args.max_courses,
        )
        json_path, nodes_path, edges_path, unresolved_path = write_outputs(
            graph,
            Path(args.output_dir),
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    metadata = graph["metadata"]
    print(
        f"Wrote prerequisite closure for {', '.join(metadata['programs'])}: "
        f"{metadata['node_count']} nodes, {metadata['edge_count']} edges, "
        f"{metadata['unresolved_count']} unresolved."
    )
    print(f"JSON: {json_path.resolve()}")
    print(f"Nodes CSV: {nodes_path.resolve()}")
    print(f"Edges CSV: {edges_path.resolve()}")
    print(f"Unresolved CSV: {unresolved_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
