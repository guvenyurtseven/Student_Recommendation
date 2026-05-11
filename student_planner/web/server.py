from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = Path(__file__).resolve().parent / "static"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "db" / "student_planner.sqlite"
MAX_JSON_BODY_BYTES = 9 * 1024 * 1024

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from student_planner.web.api import (  # noqa: E402
    recommendation_from_json_payload,
    recommendation_from_transcript_payload,
)


class PlannerRequestHandler(BaseHTTPRequestHandler):
    db_path: Path = DEFAULT_DB_PATH

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self.serve_static_file(STATIC_ROOT / "index.html")
            return
        if self.path.startswith("/static/"):
            relative = self.path.removeprefix("/static/").split("?", 1)[0]
            self.serve_static_file(STATIC_ROOT / relative)
            return
        if self.path == "/api/health":
            self.write_json({"ok": True, "service": "student-planner-web"})
            return
        self.write_error(HTTPStatus.NOT_FOUND, "Not found.")

    def do_POST(self) -> None:
        try:
            payload = self.read_json_body()
            if self.path == "/api/recommendations/from-json":
                response = recommendation_from_json_payload(payload, self.db_path)
            elif self.path == "/api/recommendations/from-transcript":
                response = recommendation_from_transcript_payload(payload, self.db_path)
            else:
                self.write_error(HTTPStatus.NOT_FOUND, "Not found.")
                return
            self.write_json(response)
        except ValueError as exc:
            self.write_error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:
            self.write_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Unexpected server error: {exc}")

    def read_json_body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("Missing Content-Length header.")
        length = int(raw_length)
        if length > MAX_JSON_BODY_BYTES:
            raise ValueError("Request body is too large.")
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Request JSON body must be an object.")
        return payload

    def serve_static_file(self, path: Path) -> None:
        resolved_root = STATIC_ROOT.resolve()
        resolved_path = path.resolve()
        if resolved_root not in resolved_path.parents and resolved_path != resolved_root:
            self.write_error(HTTPStatus.FORBIDDEN, "Forbidden.")
            return
        if not resolved_path.exists() or not resolved_path.is_file():
            self.write_error(HTTPStatus.NOT_FOUND, "Not found.")
            return
        content = resolved_path.read_bytes()
        mime_type = mimetypes.guess_type(resolved_path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime_type}; charset=utf-8" if mime_type.startswith("text/") else mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def write_error(self, status: HTTPStatus, message: str) -> None:
        self.write_json({"ok": False, "error": message}, status=status)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local METU student planner web prototype.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    PlannerRequestHandler.db_path = Path(args.db)
    server = ThreadingHTTPServer((args.host, args.port), PlannerRequestHandler)
    print(f"Serving METU Student Planner at http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
