from __future__ import annotations

import csv
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CURRICULA_DIR = ROOT / "data" / "processed" / "curricula"
PREREQ_DIR = ROOT / "data" / "processed" / "prerequisites"
OUTPUT_PATH = Path(__file__).resolve().parent / "graph-data.json"

SEMESTER_ORDER = [
    "First Semester",
    "Second Semester",
    "Third Semester",
    "Fourth Semester",
    "Fifth Semester",
    "Sixth Semester",
    "Seventh Semester",
    "Eighth Semester",
    "Ninth Semester",
    "Tenth Semester",
]

COMPONENT_COLORS = [
    "#2563eb",
    "#059669",
    "#dc2626",
    "#7c3aed",
    "#d97706",
    "#0891b2",
    "#be123c",
    "#4f46e5",
    "#16a34a",
    "#c2410c",
    "#0f766e",
    "#9333ea",
]


def main() -> int:
    programs: dict[str, Any] = {}
    for curriculum_path in sorted(CURRICULA_DIR.glob("*-latest.curriculum.json")):
        program = build_program_payload(curriculum_path)
        programs[program["abbr"]] = program

    payload = {
        "generated_from": {
            "curricula_dir": str(CURRICULA_DIR.relative_to(ROOT)),
            "prerequisites_dir": str(PREREQ_DIR.relative_to(ROOT)),
        },
        "programs": programs,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


def build_program_payload(curriculum_path: Path) -> dict[str, Any]:
    curriculum = json.loads(curriculum_path.read_text(encoding="utf-8"))
    abbr = curriculum["program"]["abbr"]
    nodes = collect_curriculum_nodes(curriculum)
    node_ids = set(nodes)
    edges = collect_curriculum_edges(abbr, node_ids)
    components = assign_components(node_ids, edges)

    for node in nodes.values():
        component_id = components["node_to_component"].get(node["id"])
        node["component_id"] = component_id
        node["color"] = components["component_colors"].get(component_id, "#64748b")
        node["is_isolated"] = component_id in components["isolated_components"]

    for edge in edges:
        component_id = components["node_to_component"].get(edge["from"])
        edge["component_id"] = component_id
        edge["color"] = components["component_colors"].get(component_id, "#64748b")

    semesters = build_semesters(nodes)
    return {
        "abbr": abbr,
        "name_en": curriculum["program"]["name_en"],
        "source_url": curriculum["source"]["source_url"],
        "node_count": len(nodes),
        "edge_count": len(edges),
        "component_count": len(components["component_colors"]),
        "semesters": semesters,
        "nodes": sorted(nodes.values(), key=lambda item: (item["semester_index"], item["sort_order"], item["course_code"])),
        "edges": edges,
    }


def collect_curriculum_nodes(curriculum: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    for sort_order, requirement in enumerate(curriculum["requirements"], start=1):
        for option_index, option in enumerate(requirement.get("options", []), start=1):
            numeric_code = option.get("numeric_code")
            if not numeric_code:
                continue
            existing = nodes.get(numeric_code)
            node = {
                "id": numeric_code,
                "course_code": option.get("course_code", ""),
                "course_title": option.get("course_title", ""),
                "requirement_type": requirement.get("requirement_type", ""),
                "requirement_id": requirement.get("requirement_id", ""),
                "year": requirement.get("year"),
                "semester_index": requirement.get("semester_index") or 99,
                "semester_label": requirement.get("semester_label") or "Unplaced",
                "option_min_count": requirement.get("option_min_count"),
                "option_index": option_index,
                "metu_credit": option.get("metu_credit", ""),
                "ects": option.get("ects", ""),
                "sort_order": sort_order,
            }
            if existing is None or node["sort_order"] < existing["sort_order"]:
                nodes[numeric_code] = node
    return nodes


def collect_curriculum_edges(program_abbr: str, node_ids: set[str]) -> list[dict[str, Any]]:
    edge_path = PREREQ_DIR / f"{program_abbr}-latest-prerequisite-closure-edges.csv"
    if not edge_path.exists():
        return []

    edges = []
    seen = set()
    with edge_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            source = row["from"]
            target = row["to"]
            if source not in node_ids or target not in node_ids:
                continue
            key = (source, target, row.get("set_no", ""), row.get("min_grade", ""))
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "from": source,
                    "from_course_code": row.get("from_course_code", ""),
                    "to": target,
                    "to_course_code": row.get("to_course_code", ""),
                    "set_no": row.get("set_no", ""),
                    "min_grade": row.get("min_grade", ""),
                    "type": row.get("type", ""),
                    "position": row.get("position", ""),
                }
            )
    return sorted(edges, key=lambda item: (item["to_course_code"], item["set_no"], item["from_course_code"]))


def assign_components(node_ids: set[str], edges: list[dict[str, Any]]) -> dict[str, Any]:
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for edge in edges:
        adjacency[edge["from"]].add(edge["to"])
        adjacency[edge["to"]].add(edge["from"])

    node_to_component: dict[str, int] = {}
    component_nodes: dict[int, list[str]] = {}
    component_id = 0
    for node_id in sorted(node_ids):
        if node_id in node_to_component:
            continue
        queue: deque[str] = deque([node_id])
        node_to_component[node_id] = component_id
        current_nodes: list[str] = []
        while queue:
            current = queue.popleft()
            current_nodes.append(current)
            for neighbor in sorted(adjacency[current]):
                if neighbor not in node_to_component:
                    node_to_component[neighbor] = component_id
                    queue.append(neighbor)
        component_nodes[component_id] = current_nodes
        component_id += 1

    connected_components = [
        item
        for item in component_nodes.items()
        if len(item[1]) > 1 or any(adjacency[node_id] for node_id in item[1])
    ]
    isolated_components = {
        item[0]
        for item in component_nodes.items()
        if item not in connected_components
    }

    component_colors: dict[int, str] = {}
    for color_index, (component, _nodes) in enumerate(
        sorted(connected_components, key=lambda item: (-len(item[1]), item[0]))
    ):
        component_colors[component] = COMPONENT_COLORS[color_index % len(COMPONENT_COLORS)]

    for component in isolated_components:
        component_colors[component] = deterministic_isolated_color(component)

    return {
        "node_to_component": node_to_component,
        "component_colors": component_colors,
        "isolated_components": isolated_components,
    }


def deterministic_isolated_color(component_id: int) -> str:
    hue = (component_id * 47) % 360
    return f"hsl({hue}, 42%, 52%)"


def build_semesters(nodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    by_semester: dict[int, list[dict[str, Any]]] = defaultdict(list)
    labels: dict[int, str] = {}
    for node in nodes.values():
        semester_index = int(node["semester_index"] or 99)
        by_semester[semester_index].append(node)
        labels[semester_index] = node["semester_label"] or label_for_semester(semester_index)

    semesters = []
    for semester_index in sorted(by_semester):
        label = labels.get(semester_index) or label_for_semester(semester_index)
        semesters.append(
            {
                "semester_index": semester_index,
                "label": label,
                "nodes": sorted(
                    [node["id"] for node in by_semester[semester_index]],
                    key=lambda node_id: (nodes[node_id]["sort_order"], nodes[node_id]["course_code"]),
                ),
            }
        )
    return semesters


def label_for_semester(semester_index: int) -> str:
    if 1 <= semester_index <= len(SEMESTER_ORDER):
        return SEMESTER_ORDER[semester_index - 1]
    return "Unplaced"


if __name__ == "__main__":
    raise SystemExit(main())
