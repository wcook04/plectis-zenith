"""Serve the public web directory and optionally refresh aggregate operations in memory."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .export import build_operations

CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
                 ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp",
                 ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".ico": "image/x-icon",
                 ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
                 ".csv": "text/csv; charset=utf-8", ".woff2": "font/woff2"}


def make_server(host: str = "127.0.0.1", port: int = 8768, *, web_root: Path | str | None = None,
                source_root: Path | str | None = None) -> ThreadingHTTPServer:
    web = Path(web_root) if web_root is not None else Path(__file__).resolve().parent.parent / "web"
    if web.is_symlink():
        raise ValueError("Public web root must not be a symlink")
    web = web.resolve()

    class PublicHandler(BaseHTTPRequestHandler):
        server_version = "Observatory"
        sys_version = ""

        def log_message(self, format, *args):
            # URL text may contain private input; access logs are unnecessary here.
            pass

        def _send(self, status: int, body: bytes, content_type="application/json; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _missing(self):
            self._send(404, b'{"error":"Public resource unavailable"}\n')

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            try:
                path = unquote(urlsplit(self.path).path, errors="strict")
                pieces = path.split("/")
                if not path.startswith("/") or any(piece.startswith(".") for piece in pieces if piece) or "\\" in path or "%" in path or "\x00" in path:
                    self._missing()
                    return
                if path == "/data/operations.json" and source_root is not None:
                    body = json.dumps(build_operations(source_root), allow_nan=False, sort_keys=True).encode() + b"\n"
                    self._send(200, body)
                    return
                target = web.joinpath(*[p for p in pieces if p])
                # Even symlinks within web are denied, so future edits cannot
                # accidentally turn this server into a private file gateway.
                current = web
                for part in target.relative_to(web).parts:
                    current = current / part
                    if current.is_symlink():
                        self._missing()
                        return
                if target.is_dir():
                    target = target / "index.html"
                if target.is_symlink() or not target.resolve().is_relative_to(web) or not target.is_file() or target.suffix not in CONTENT_TYPES:
                    self._missing()
                    return
                self._send(200, target.read_bytes(), CONTENT_TYPES[target.suffix])
            except (OSError, ValueError, UnicodeError):
                self._missing()

    return ThreadingHTTPServer((host, port), PublicHandler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--source-root", type=Path, help="Optional source for in-memory aggregate refresh")
    args = parser.parse_args()
    try:
        server = make_server(args.host, args.port, source_root=args.source_root)
    except (OSError, ValueError):
        parser.exit(1, "Public preview server could not start.\n")
    print("Observatory preview server started.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
