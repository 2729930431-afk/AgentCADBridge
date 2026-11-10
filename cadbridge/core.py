"""Shared scheduling, idempotency, audit and batch semantics."""

import hashlib
import json
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from .locking import cad_lock, state_dir


class Bridge:
    def __init__(self, backend=None, lock=cad_lock, database=None):
        self.backend = backend
        self.lock = lock
        self.database = database or state_dir() / "requests.sqlite3"
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="CADBridge-STA")

    def submit(self, method: str, **params):
        return self.worker.submit(self._run, method, params)

    def call(self, method: str, **params):
        return self.submit(method, **params).result()

    def close(self):
        self.worker.shutdown(wait=True)

    def _run(self, method, params):
        request_id = params.pop("request_id", "") or str(uuid.uuid4())
        fingerprint = hashlib.sha256(
            json.dumps([method, params], sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
        ).hexdigest()
        with self.lock(), sqlite3.connect(self.database) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, fingerprint TEXT, method TEXT, started REAL, result TEXT)"
            )
            row = db.execute("SELECT fingerprint, result FROM requests WHERE id=?", (request_id,)).fetchone()
            if row:
                if row[0] != fingerprint:
                    return {
                        "ok": False,
                        "request_id": request_id,
                        "error": "request_id already used with different arguments",
                    }
                if row[1]:
                    return {**json.loads(row[1]), "replayed": True}
                return {
                    "ok": False,
                    "request_id": request_id,
                    "outcome": "unknown",
                    "error": "Previous execution did not complete; inspect CAD. It will not be repeated automatically",
                }
            db.execute(
                "INSERT INTO requests VALUES (?,?,?,?,NULL)", (request_id, fingerprint, method, time.time())
            )
            db.commit()  # Mark execution before touching CAD, including crash scenarios.
            try:
                if self.backend is None:
                    from .backends.com import COMBackend

                    self.backend = COMBackend()
                if method == "connect":
                    result = self.backend.connect(**params)
                elif method == "documents":
                    result = self.backend.documents(**params)
                elif method == "catalog":
                    result = self.backend.catalog(**params)
                elif method == "execute":
                    result = self.backend.execute(**params)
                elif method == "batch":
                    result = self._batch(**params)
                elif method == "preview":
                    from .preview import create_preview

                    result = create_preview(self.backend, **params)
                elif method == "capabilities":
                    from .backends.com import PROFILES

                    result = {
                        "version": "0.1.0",
                        "backend": "compatible-com",
                        "profiles": PROFILES,
                        "connected": bool(self.backend.adapter),
                        "operations": self.backend.catalog() if self.backend.adapter else [],
                        "preview": {
                            "snapshot": "shared COM Document.Export(DXF)",
                            "renderer": "shared ezdxf/Matplotlib Agg",
                            "formats": ["png", "svg"],
                            "requires_active_document": False,
                            "ui_fallback": False,
                            "profile_support": "checked by attempting export; other CAD profiles need live validation",
                        },
                        "concurrency": "one STA worker and cross-process OS file lock; external CAD users are not locked",
                        "batch": "prevalidated, stops on first failure; undo group, no automatic rollback",
                        "limitations": [
                            "Windows COM only",
                            "ZWCAD 2026 is the initial live test target; other profiles unverified",
                            "No mechanical BOM/ZRX/printing workflow in v0.1",
                            "No raw code/LISP execution",
                            "Command-based undo/redo need state verification",
                        ],
                    }
                else:
                    raise ValueError(f"Unknown bridge method: {method}")
                response = {"ok": True, "request_id": request_id, "result": result}
            except Exception as error:
                response = {
                    "ok": False,
                    "request_id": request_id,
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "verification_required": True,
                }
            db.execute(
                "UPDATE requests SET result=? WHERE id=?",
                (json.dumps(response, ensure_ascii=False, default=str), request_id),
            )
            db.commit()
            return response

    def _batch(self, document_id: str, operations: list[dict]):
        if not 1 <= len(operations) <= 500:
            raise ValueError("Batch must contain 1..500 operations")
        # Validate the complete batch before creating the first object.
        for item in operations:
            if set(item) != {"operation", "arguments"}:
                raise ValueError("Each batch item requires exactly operation and arguments")
            if item["operation"] in ("undo", "redo", "export_to_excel"):
                raise ValueError("Undo/redo and exports run separately from drawing batches")
            self.backend.validate(item["operation"], item["arguments"])
        doc = self.backend.bind(document_id)
        self.backend.adapter._get_document("batch")
        completed = []
        failure = None
        doc.StartUndoMark()
        self.backend.batch_running = True
        try:
            for index, item in enumerate(operations):
                try:
                    result = self.backend.execute(document_id, **item)
                    completed.append({"index": index, "operation": item["operation"], "result": result})
                except Exception as error:
                    failure = {"index": index, "operation": item["operation"], "error": str(error)}
                    break
        finally:
            self.backend.batch_running = False
            doc.EndUndoMark()
        return {
            "complete": failure is None,
            "completed": completed,
            "failure": failure,
            "rollback": False,
            "verification_required": failure is not None,
        }
