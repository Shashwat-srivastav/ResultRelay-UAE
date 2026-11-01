"""Persistence layer.

The event store is the source of truth. The UI reads projections of it; nothing in the UI is
required for correctness.

SQLite + SQLAlchemy Core-style declarative models. Parameterised statements throughout (the
ORM does not interpolate values into SQL strings).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DB_PATH = Path(os.environ.get("RESULTRELAY_DB", Path(__file__).resolve().parents[1] / "resultrelay.db"))


class Base(DeclarativeBase):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CaseRow(Base):
    __tablename__ = "cases"
    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), index=True)
    configuration: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(256))
    jurisdiction: Mapped[str] = mapped_column(String(32), index=True)
    facility_type: Mapped[str] = mapped_column(String(128))
    case_scope: Mapped[str] = mapped_column(String(32), index=True)
    current_state: Mapped[str] = mapped_column(String(64), index=True)
    current_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    patient_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String(40), default=_now)
    updated_at: Mapped[str] = mapped_column(String(40), default=_now)
    payload: Mapped[str] = mapped_column(Text, default="{}")


class RevisionRow(Base):
    __tablename__ = "result_revisions"
    revision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24))
    supersedes_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_name: Mapped[str] = mapped_column(String(128))
    critical_flag_source: Mapped[str] = mapped_column(String(128))
    finalized_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")


class EventRow(Base):
    __tablename__ = "events"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    at: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(48), index=True)
    actor: Mapped[str] = mapped_column(String(48))
    source_layer: Mapped[str] = mapped_column(String(24), index=True)  # LAB | NETWORK | HUMAN | POLICY | SYSTEM
    summary: Mapped[str] = mapped_column(String(512))
    payload: Mapped[str] = mapped_column(Text, default="{}")


class AttemptRow(Base):
    __tablename__ = "communication_attempts"
    attempt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    channel: Mapped[str] = mapped_column(String(64))
    result_revision_id: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    failed: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome: Mapped[str] = mapped_column(String(24))
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(40))
    payload: Mapped[str] = mapped_column(Text, default="{}")


class ReceiptRow(Base):
    __tablename__ = "delivery_receipts"
    receipt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    attempt_id: Mapped[str] = mapped_column(String(64), index=True)
    result_revision_id: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32))  # TRANSPORT | RECONCILIATION
    at: Mapped[str] = mapped_column(String(40))
    payload: Mapped[str] = mapped_column(Text, default="{}")


class AcknowledgmentRow(Base):
    __tablename__ = "acknowledgments"
    ack_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    result_revision_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(48))
    actor: Mapped[str] = mapped_column(String(96))
    channel: Mapped[str] = mapped_column(String(48))
    identity_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    at: Mapped[str] = mapped_column(String(40))
    payload: Mapped[str] = mapped_column(Text, default="{}")


class AssessmentRow(Base):
    __tablename__ = "agent_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    step: Mapped[int] = mapped_column(Integer)
    agent_id: Mapped[str] = mapped_column(String(48), index=True)
    assessment_status: Mapped[str] = mapped_column(String(32))
    recommended_action: Mapped[str] = mapped_column(String(48))
    confidence: Mapped[float] = mapped_column(Float)
    requires_human_review: Mapped[bool] = mapped_column(Boolean)
    payload: Mapped[str] = mapped_column(Text)


class CitationRow(Base):
    __tablename__ = "source_citations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    step: Mapped[int] = mapped_column(Integer)
    agent_id: Mapped[str] = mapped_column(String(48))
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    section: Mapped[str] = mapped_column(String(64))
    page: Mapped[int] = mapped_column(Integer)
    claim_type: Mapped[str] = mapped_column(String(48))
    consumed_by_decision: Mapped[bool] = mapped_column(Boolean, default=False)


class TransitionRow(Base):
    __tablename__ = "state_transitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    step: Mapped[int] = mapped_column(Integer)
    prior_state: Mapped[str] = mapped_column(String(64))
    resulting_state: Mapped[str] = mapped_column(String(64))
    trigger_event: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))  # APPLIED | BLOCKED | NO_RULE
    actor: Mapped[str] = mapped_column(String(48))
    reason: Mapped[str] = mapped_column(Text)
    invariant: Mapped[str | None] = mapped_column(String(48), nullable=True)
    policy_refs: Mapped[str] = mapped_column(String(256), default="")
    at: Mapped[str] = mapped_column(String(40))


class EscalationRow(Base):
    __tablename__ = "escalation_requests"
    escalation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(48))
    reason: Mapped[str] = mapped_column(Text)
    triggered_by: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    at: Mapped[str] = mapped_column(String(40))
    payload: Mapped[str] = mapped_column(Text, default="{}")


class AuditRow(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    at: Mapped[str] = mapped_column(String(40))
    event: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text, default="{}")
    #: Policy-corpus hash in force when the entry was written (empty for pre-A8 rows).
    kb_index_sha256: Mapped[str] = mapped_column(String(64), default="", server_default="")


class EvaluationRunRow(Base):
    __tablename__ = "evaluation_runs"
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[str] = mapped_column(String(40))
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scenario_count: Mapped[int] = mapped_column(Integer, default=0)
    configurations: Mapped[str] = mapped_column(String(256), default="")
    summary: Mapped[str] = mapped_column(Text, default="{}")


class RunRow(Base):
    """A run's durable cursor.

    The runtime lives in memory for progressive stepping, but the cursor must survive eviction
    and restart, otherwise a case can be stepped to an arbitrary point and then abandoned with
    no way back (red-team finding H-7). The runtime is rebuilt from the scenario by replaying
    ``cursor`` steps, which is sound because the engine is deterministic.
    """

    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), index=True)
    configuration: Mapped[str] = mapped_column(String(32), index=True)
    case_id: Mapped[str] = mapped_column(String(96), index=True)
    cursor: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(40), default=_now)
    updated_at: Mapped[str] = mapped_column(String(40), default=_now)


_engine = None
_Session: sessionmaker | None = None


def get_engine(db_path: Path | str | None = None):
    global _engine, _Session
    if _engine is None or db_path is not None:
        path = Path(db_path or DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{path}",
            future=True,
            # A demo server must never hang on a held lock: fail or wait a bounded time instead
            # (red-team finding H-7: default pooling with no timeout wedged every DB-backed route).
            connect_args={"timeout": 5.0, "check_same_thread": False},
            pool_size=10,
            max_overflow=10,
            pool_timeout=5.0,
            pool_pre_ping=True,
        )

        @event.listens_for(_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001 - SQLAlchemy hook signature
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
        Base.metadata.create_all(_engine)
        _Session = sessionmaker(bind=_engine, future=True, expire_on_commit=False)
    return _engine


def session() -> Session:
    if _Session is None:
        get_engine()
    assert _Session is not None
    return _Session()


def reset_engine() -> None:
    """Forget the current engine and session factory (used by tests to rebind the DB path)."""
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Session = None


def reset_database(db_path: Path | str | None = None) -> None:
    """Drop and recreate for a clean demonstration run. Never used in the API."""
    path = Path(db_path or DB_PATH)
    if path.exists():
        path.unlink()
    global _engine, _Session
    _engine = None
    _Session = None
    get_engine(path)


def rows_to_dicts(rows: list[Any], exclude: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        d = {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in exclude}
        for key in ("payload", "summary"):
            if key in d and isinstance(d[key], str) and d[key].startswith("{"):
                try:
                    d[key] = json.loads(d[key])
                except json.JSONDecodeError:
                    pass
        out.append(d)
    return out


def list_cases(session_: Session | None = None, run_id: str | None = None) -> list[dict[str, Any]]:
    s = session_ or session()
    stmt = select(CaseRow).order_by(CaseRow.updated_at.desc())
    if run_id:
        stmt = stmt.where(CaseRow.run_id == run_id)
    return rows_to_dicts(list(s.scalars(stmt)), exclude=("payload",))


def get_case(case_id: str, session_: Session | None = None) -> dict[str, Any] | None:
    s = session_ or session()
    row = s.get(CaseRow, case_id)
    if row is None:
        return None
    d = rows_to_dicts([row])[0]
    d["payload"] = json.loads(row.payload or "{}")
    return d
