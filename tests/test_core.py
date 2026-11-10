import json
import sqlite3
import threading
import time
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from cadbridge.core import Bridge


class FakeDocument:
    def __init__(self):
        self.marks = []

    def StartUndoMark(self):
        self.marks.append("start")

    def EndUndoMark(self):
        self.marks.append("end")


class FakeBackend:
    def __init__(self):
        self.executed = []
        self.doc = FakeDocument()
        self.adapter = SimpleNamespace(_get_document=lambda op: self.doc)
        self.threads = set()

    def validate(self, operation, arguments):
        if operation not in ("line", "fail"):
            raise ValueError("unknown operation")
        if arguments.get("invalid"):
            raise ValueError("invalid geometry")
        return arguments

    def bind(self, document_id):
        if document_id != "target":
            raise ValueError("unknown document")
        return self.doc

    def execute(self, document_id, operation, arguments):
        self.validate(operation, arguments)
        self.bind(document_id)
        self.threads.add(threading.get_ident())
        if operation == "fail":
            raise RuntimeError("vendor error")
        time.sleep(0.005)
        self.executed.append(arguments)
        return {"handle": str(len(self.executed))}


@pytest.fixture
def bridge(tmp_path):
    item = Bridge(FakeBackend(), lock=nullcontext, database=tmp_path / "requests.db")
    yield item
    item.close()


def execute(bridge, request_id="request-1", document_id="target", **arguments):
    return bridge.call(
        "execute", document_id=document_id, operation="line", arguments=arguments, request_id=request_id
    )


def test_duplicate_request_does_not_draw_twice(bridge):
    first = execute(bridge, x=1)
    second = execute(bridge, x=1)
    assert first["ok"] and second["replayed"]
    assert len(bridge.backend.executed) == 1


def test_request_id_cannot_mean_two_different_operations(bridge):
    execute(bridge, x=1)
    assert not execute(bridge, x=2)["ok"]
    assert len(bridge.backend.executed) == 1


def test_crashed_request_is_not_repeated(bridge):
    response = execute(bridge)
    with sqlite3.connect(bridge.database) as db:
        db.execute("UPDATE requests SET result=NULL WHERE id=?", (response["request_id"],))
    replay = execute(bridge)
    assert replay["outcome"] == "unknown"
    assert len(bridge.backend.executed) == 1


def test_wrong_document_never_falls_back(bridge):
    assert not execute(bridge, document_id="wrong")["ok"]
    assert bridge.backend.executed == []


def test_batch_prevalidates_before_any_mutation(bridge):
    result = bridge.call(
        "batch",
        document_id="target",
        operations=[
            {"operation": "line", "arguments": {}},
            {"operation": "line", "arguments": {"invalid": True}},
        ],
    )
    assert not result["ok"]
    assert bridge.backend.executed == []
    assert bridge.backend.doc.marks == []


def test_partial_batch_reports_completed_items_and_closes_group(bridge):
    result = bridge.call(
        "batch",
        document_id="target",
        operations=[
            {"operation": "line", "arguments": {}},
            {"operation": "fail", "arguments": {}},
            {"operation": "line", "arguments": {}},
        ],
    )["result"]
    assert not result["complete"]
    assert result["failure"]["index"] == 1
    assert len(result["completed"]) == len(bridge.backend.executed) == 1
    assert bridge.backend.doc.marks == ["start", "end"]
    assert not result["rollback"]


def test_single_worker_serializes_requests_and_keeps_one_thread(bridge):
    futures = [
        bridge.submit("execute", document_id="target", operation="line", arguments={"x": x})
        for x in range(10)
    ]
    assert all(f.result()["ok"] for f in futures)
    assert [item["x"] for item in bridge.backend.executed] == list(range(10))
    assert len(bridge.backend.threads) == 1


@pytest.mark.parametrize(
    "operations", [[], [{}] * 501, [{"operation": "line", "arguments": {}, "extra": True}]]
)
def test_malformed_batch_rejected(bridge, operations):
    assert not bridge.call("batch", document_id="target", operations=operations)["ok"]
    assert not bridge.backend.executed


def test_audit_persists_result(bridge):
    result = execute(bridge)
    with sqlite3.connect(bridge.database) as db:
        stored = json.loads(
            db.execute("SELECT result FROM requests WHERE id=?", (result["request_id"],)).fetchone()[0]
        )
    assert stored == result
