from __future__ import annotations

import json
from pathlib import Path

from student_planner.domain.models import Program


def load_engineering_programs(path: Path) -> list[Program]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    programs: list[Program] = []
    for item in payload["programs"]:
        programs.append(
            Program(
                abbr=item["abbr"],
                catalog_program_id=item["catalog_program_id"],
                name_en=item["name_en"],
                name_tr=item["name_tr"],
                faculty=item["faculty"],
                is_active_undergraduate=item.get("is_active_undergraduate", True),
            )
        )
    return programs

