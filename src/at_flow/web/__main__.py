from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .app import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m at_flow.web", description="AT Flow web console backend")
    parser.add_argument("--root", default=".", help="AT workspace root")
    parser.add_argument("--host", default="127.0.0.1", help="bind host")
    parser.add_argument("--port", default=8000, type=int, help="bind port")
    args = parser.parse_args(argv)

    uvicorn.run(create_app(Path(args.root)), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
