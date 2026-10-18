from typing import Any
from uuid import uuid4

import pytest

import transcributed.worker.main as worker_main


class FakeConnection:
    def __init__(self, fail_first_query: bool) -> None:
        self.closed = False
        self.fail_first_query = fail_first_query
        self.queries = 0

    def execute(self, *args: Any, **kwargs: Any) -> FakeConnection:
        self.queries += 1
        if self.fail_first_query and self.queries == 1:
            raise RuntimeError("connection lost")
        return self

    def fetchone(self) -> tuple[str]:
        return ("cancelled",)

    def close(self) -> None:
        self.closed = True


def test_cancellation_check_reconnects_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connections: list[FakeConnection] = []

    def connect(*args: Any, **kwargs: Any) -> FakeConnection:
        assert kwargs["connect_timeout"] == 5
        connection = FakeConnection(fail_first_query=not connections)
        connections.append(connection)
        return connection

    monkeypatch.setattr(worker_main.psycopg, "connect", connect)

    check = worker_main.CancellationCheck(uuid4(), "postgresql://localhost/test")

    assert check() is False
    assert connections[0].closed is True

    assert check() is True
    assert len(connections) == 2
