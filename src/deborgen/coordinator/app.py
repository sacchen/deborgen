from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
from datetime import UTC, datetime
from typing import Any, Literal, cast

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

JobStatus = Literal["queued", "running", "succeeded", "failed"]


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def parse_job_pk(job_id: str) -> int:
    if not job_id.startswith("job_"):
        raise HTTPException(status_code=404, detail="job not found")
    suffix = job_id.removeprefix("job_")
    if not suffix.isdigit():
        raise HTTPException(status_code=404, detail="job not found")
    return int(suffix)


class Job(BaseModel):
    id: str
    status: JobStatus
    command: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    assigned_node_id: str | None = None
    timeout_seconds: int = 3600
    attempts: int = 0
    max_attempts: int = 1
    exit_code: int | None = None
    failure_reason: str | None = None
    artifact_urls: list[str] = Field(default_factory=list)


class JobCreateRequest(BaseModel):
    command: str
    timeout_seconds: int = 3600
    max_attempts: int = 1


class JobAssignment(BaseModel):
    job: Job
    lease_token: str


class JobFinishRequest(BaseModel):
    node_id: str
    lease_token: str
    exit_code: int
    failure_reason: str | None = None


class JobLogsRequest(BaseModel):
    node_id: str
    lease_token: str
    text: str


class JobListResponse(BaseModel):
    jobs: list[Job]


class JobLogsResponse(BaseModel):
    text: str


class Node(BaseModel):
    node_id: str
    name: str | None = None
    labels: dict[str, str | int | float | bool] = Field(default_factory=dict)
    last_seen_at: datetime


class NodeHeartbeatRequest(BaseModel):
    name: str | None = None
    labels: dict[str, str | int | float | bool] = Field(default_factory=dict)


class SqliteJobStore:
    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    command TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    assigned_node_id TEXT,
                    timeout_seconds INTEGER NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 1,
                    exit_code INTEGER,
                    failure_reason TEXT,
                    artifact_urls TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS leases (
                    job_id INTEGER PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    lease_token TEXT NOT NULL,
                    lease_expires_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    name TEXT,
                    labels_json TEXT NOT NULL DEFAULT '{}',
                    last_seen_at TEXT NOT NULL
                )
                """
            )

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        artifact_urls_raw = cast(str, row["artifact_urls"])
        artifact_urls = cast(list[str], json.loads(artifact_urls_raw))
        return Job(
            id=f"job_{cast(int, row['id'])}",
            status=cast(JobStatus, row["status"]),
            command=cast(str, row["command"]),
            created_at=parse_iso(cast(str, row["created_at"])) or utcnow(),
            started_at=parse_iso(cast(str | None, row["started_at"])),
            finished_at=parse_iso(cast(str | None, row["finished_at"])),
            assigned_node_id=cast(str | None, row["assigned_node_id"]),
            timeout_seconds=cast(int, row["timeout_seconds"]),
            attempts=cast(int, row["attempts"]),
            max_attempts=cast(int, row["max_attempts"]),
            exit_code=cast(int | None, row["exit_code"]),
            failure_reason=cast(str | None, row["failure_reason"]),
            artifact_urls=artifact_urls,
        )

    def _row_to_node(self, row: sqlite3.Row) -> Node:
        labels_raw = cast(str, row["labels_json"])
        labels_any = cast(dict[str, Any], json.loads(labels_raw))
        labels = cast(dict[str, str | int | float | bool], labels_any)
        return Node(
            node_id=cast(str, row["node_id"]),
            name=cast(str | None, row["name"]),
            labels=labels,
            last_seen_at=parse_iso(cast(str, row["last_seen_at"])) or utcnow(),
        )

    def _get_job_row(self, job_pk: int) -> sqlite3.Row | None:
        return self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_pk,)).fetchone()

    def create_job(self, request: JobCreateRequest) -> Job:
        now = to_iso(utcnow())
        assert now is not None
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO jobs(status, command, created_at, timeout_seconds, max_attempts, artifact_urls)
                VALUES ('queued', ?, ?, ?, ?, '[]')
                """,
                (request.command, now, request.timeout_seconds, request.max_attempts),
            )
            row = self._get_job_row(cast(int, cursor.lastrowid))
            if row is None:
                raise HTTPException(status_code=500, detail="failed to create job")
            return self._row_to_job(row)

    def list_jobs(self, status_filter: JobStatus | None, limit: int | None) -> list[Job]:
        query = "SELECT * FROM jobs"
        params: list[Any] = []
        if status_filter is not None:
            query += " WHERE status = ?"
            params.append(status_filter)
        query += " ORDER BY id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
            return [self._row_to_job(row) for row in rows]

    def get_job(self, job_id: str) -> Job:
        job_pk = parse_job_pk(job_id)
        with self._lock:
            row = self._get_job_row(job_pk)
            if row is None:
                raise HTTPException(status_code=404, detail="job not found")
            return self._row_to_job(row)

    def claim_next_job(self, node_id: str) -> JobAssignment | None:
        now = to_iso(utcnow())
        assert now is not None
        with self._lock, self._conn:
            queued = self._conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'queued' AND attempts < max_attempts
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()
            if queued is None:
                return None

            job_pk = cast(int, queued["id"])
            updated = self._conn.execute(
                """
                UPDATE jobs
                SET status = 'running', assigned_node_id = ?, started_at = ?, attempts = attempts + 1
                WHERE id = ? AND status = 'queued' AND attempts < max_attempts
                """,
                (node_id, now, job_pk),
            )
            if updated.rowcount != 1:
                return None

            lease_token = secrets.token_urlsafe(24)
            self._conn.execute(
                """
                INSERT INTO leases(job_id, node_id, lease_token, lease_expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    node_id = excluded.node_id,
                    lease_token = excluded.lease_token,
                    lease_expires_at = excluded.lease_expires_at
                """,
                (job_pk, node_id, lease_token, now),
            )

            row = self._get_job_row(job_pk)
            if row is None:
                raise HTTPException(status_code=500, detail="claimed job missing")
            return JobAssignment(job=self._row_to_job(row), lease_token=lease_token)

    def finish_job(self, job_id: str, request: JobFinishRequest) -> Job:
        job_pk = parse_job_pk(job_id)
        now = to_iso(utcnow())
        assert now is not None
        with self._lock, self._conn:
            row = self._get_job_row(job_pk)
            if row is None:
                raise HTTPException(status_code=404, detail="job not found")
            if cast(str, row["status"]) != "running":
                raise HTTPException(status_code=409, detail="job is not running")

            lease = self._conn.execute(
                "SELECT node_id, lease_token FROM leases WHERE job_id = ?",
                (job_pk,),
            ).fetchone()
            if lease is None:
                raise HTTPException(status_code=409, detail="job has no active lease")

            lease_node_id = cast(str, lease["node_id"])
            lease_token = cast(str, lease["lease_token"])
            if lease_node_id != request.node_id or lease_token != request.lease_token:
                raise HTTPException(status_code=409, detail="job is owned by a different worker")

            next_status: JobStatus = "succeeded" if request.exit_code == 0 else "failed"
            self._conn.execute(
                """
                UPDATE jobs
                SET status = ?, exit_code = ?, failure_reason = ?, finished_at = ?
                WHERE id = ?
                """,
                (next_status, request.exit_code, request.failure_reason, now, job_pk),
            )
            self._conn.execute("DELETE FROM leases WHERE job_id = ?", (job_pk,))

            updated_row = self._get_job_row(job_pk)
            if updated_row is None:
                raise HTTPException(status_code=500, detail="updated job missing")
            return self._row_to_job(updated_row)

    def append_logs(self, job_id: str, request: JobLogsRequest) -> None:
        job_pk = parse_job_pk(job_id)
        now = to_iso(utcnow())
        assert now is not None
        with self._lock, self._conn:
            row = self._get_job_row(job_pk)
            if row is None:
                raise HTTPException(status_code=404, detail="job not found")
            lease = self._conn.execute(
                "SELECT node_id, lease_token FROM leases WHERE job_id = ?",
                (job_pk,),
            ).fetchone()
            if lease is None:
                raise HTTPException(status_code=409, detail="job has no active lease")
            lease_node_id = cast(str, lease["node_id"])
            lease_token = cast(str, lease["lease_token"])
            if lease_node_id != request.node_id or lease_token != request.lease_token:
                raise HTTPException(status_code=409, detail="job is owned by a different worker")

            self._conn.execute(
                "INSERT INTO logs(job_id, text, created_at) VALUES (?, ?, ?)",
                (job_pk, request.text, now),
            )

    def read_logs(self, job_id: str) -> JobLogsResponse:
        job_pk = parse_job_pk(job_id)
        with self._lock:
            row = self._get_job_row(job_pk)
            if row is None:
                raise HTTPException(status_code=404, detail="job not found")
            logs = self._conn.execute(
                "SELECT text FROM logs WHERE job_id = ? ORDER BY id ASC",
                (job_pk,),
            ).fetchall()
            text = "".join(cast(str, record["text"]) for record in logs)
            return JobLogsResponse(text=text)

    def heartbeat_node(self, node_id: str, request: NodeHeartbeatRequest) -> Node:
        now = to_iso(utcnow())
        assert now is not None
        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT * FROM nodes WHERE node_id = ?",
                (node_id,),
            ).fetchone()
            if existing is None:
                labels_json = json.dumps(request.labels)
                self._conn.execute(
                    """
                    INSERT INTO nodes(node_id, name, labels_json, last_seen_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (node_id, request.name, labels_json, now),
                )
            else:
                existing_labels_any = cast(dict[str, Any], json.loads(cast(str, existing["labels_json"])))
                existing_labels = cast(dict[str, str | int | float | bool], existing_labels_any)
                labels = request.labels if request.labels else existing_labels
                name = request.name if request.name is not None else cast(str | None, existing["name"])
                self._conn.execute(
                    """
                    UPDATE nodes
                    SET name = ?, labels_json = ?, last_seen_at = ?
                    WHERE node_id = ?
                    """,
                    (name, json.dumps(labels), now, node_id),
                )

            row = self._conn.execute(
                "SELECT * FROM nodes WHERE node_id = ?",
                (node_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=500, detail="failed to persist node heartbeat")
            return self._row_to_node(row)


auth_scheme = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> None:
    expected = os.getenv("DEBORGEN_TOKEN")
    if not expected:
        return
    if not credentials or credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid auth token",
        )


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="deborgen")
    resolved_db_path = db_path or os.getenv("DEBORGEN_DB_PATH", "deborgen.db")
    store = SqliteJobStore(db_path=resolved_db_path)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/jobs", response_model=Job, status_code=201)
    def create_job(request: JobCreateRequest, _: None = Depends(require_auth)) -> Job:
        return store.create_job(request)

    @app.get("/jobs", response_model=JobListResponse)
    def list_jobs(
        status_filter: JobStatus | None = Query(default=None, alias="status"),
        limit: int | None = Query(default=None, ge=1, le=1000),
        _: None = Depends(require_auth),
    ) -> JobListResponse:
        return JobListResponse(jobs=store.list_jobs(status_filter=status_filter, limit=limit))

    @app.get("/jobs/next", response_model=JobAssignment)
    def next_job(node_id: str, _: None = Depends(require_auth)) -> JobAssignment | Response:
        assignment = store.claim_next_job(node_id=node_id)
        if assignment is None:
            return Response(status_code=204)
        return assignment

    @app.get("/jobs/{job_id}", response_model=Job)
    def get_job(job_id: str, _: None = Depends(require_auth)) -> Job:
        return store.get_job(job_id)

    @app.post("/jobs/{job_id}/finish", response_model=Job)
    def finish_job(job_id: str, request: JobFinishRequest, _: None = Depends(require_auth)) -> Job:
        return store.finish_job(job_id=job_id, request=request)

    @app.post("/nodes/{node_id}/heartbeat", response_model=Node)
    def node_heartbeat(
        node_id: str,
        request: NodeHeartbeatRequest,
        _: None = Depends(require_auth),
    ) -> Node:
        return store.heartbeat_node(node_id=node_id, request=request)

    @app.post("/jobs/{job_id}/logs")
    def append_logs(
        job_id: str,
        request: JobLogsRequest,
        _: None = Depends(require_auth),
    ) -> dict[str, str]:
        store.append_logs(job_id=job_id, request=request)
        return {"status": "ok"}

    @app.get("/jobs/{job_id}/logs", response_model=JobLogsResponse)
    def read_logs(job_id: str, _: None = Depends(require_auth)) -> JobLogsResponse:
        return store.read_logs(job_id=job_id)

    return app


app = create_app()
