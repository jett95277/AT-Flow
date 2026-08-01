from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from ..models import now_iso


class WebConsoleDb:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def record_request(self, method: str, path: str, status_code: int) -> None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                """
                insert into request_history (created_at, method, path, status_code)
                values (?, ?, ?, ?)
                """,
                (now_iso(), method, path, status_code),
            )
            connection.commit()

    def _initialize(self) -> None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                """
                create table if not exists request_history (
                    id integer primary key,
                    created_at text not null,
                    method text not null,
                    path text not null,
                    status_code integer not null
                )
                """
            )
            connection.commit()
