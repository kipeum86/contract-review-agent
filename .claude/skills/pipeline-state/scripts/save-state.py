#!/usr/bin/env python3
"""Pipeline state persistence with lock-guarded atomic writes."""

import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone

import fcntl


SCHEMA_VERSION = 2


def ensure_parent_dir(path: str) -> str:
    """Create and return the parent directory for a path."""
    parent_dir = os.path.dirname(os.path.abspath(path)) or os.getcwd()
    os.makedirs(parent_dir, exist_ok=True)
    return parent_dir


@contextmanager
def state_file_lock(state_path: str):
    """Serialize readers/writers with a sidecar lock file."""
    parent_dir = ensure_parent_dir(state_path)
    lock_path = os.path.join(parent_dir, f".{os.path.basename(state_path)}.lock")

    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield lock_path
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def atomic_write_json(path: str, payload: dict) -> None:
    """Write JSON to a temp file and atomically replace the destination."""
    parent_dir = ensure_parent_dir(path)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=parent_dir,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def sanitize_session_part(value: object) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "unknown")).strip("-")
    return cleaned or "unknown"


def generate_session_id(pipeline: str, matter_id: str, round_num: int) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parts = [
        sanitize_session_part(pipeline),
        sanitize_session_part(matter_id),
        f"round-{int(round_num or 1)}",
        timestamp,
        str(os.getpid()),
    ]
    return "-".join(parts)


def migrate_state(state: dict, pipeline: str, matter_id: str, round_num: int,
                  review_mode: str = None, session_id: str = None,
                  now: str = None) -> dict:
    """Return a v2 state object while preserving all known v1 fields."""
    now = now or datetime.now(timezone.utc).isoformat()
    migrated = dict(state or {})

    migrated["schema_version"] = SCHEMA_VERSION
    migrated["pipeline"] = migrated.get("pipeline") or pipeline
    migrated["matter_id"] = migrated.get("matter_id") or matter_id
    migrated["round"] = int(migrated.get("round") or round_num or 1)
    migrated["last_completed_step"] = int(migrated.get("last_completed_step", 0) or 0)
    migrated["review_mode"] = review_mode or migrated.get("review_mode")
    migrated["step_artifacts"] = (
        migrated.get("step_artifacts")
        if isinstance(migrated.get("step_artifacts"), dict)
        else {}
    )
    migrated["metrics"] = (
        migrated.get("metrics")
        if isinstance(migrated.get("metrics"), dict)
        else {}
    )
    migrated["session_id"] = (
        session_id
        or migrated.get("session_id")
        or generate_session_id(migrated["pipeline"], migrated["matter_id"], migrated["round"])
    )
    migrated["started_at"] = migrated.get("started_at") or now
    migrated["updated_at"] = migrated.get("updated_at") or now

    return migrated


def save_state(state_path: str, pipeline: str, matter_id: str, round_num: int,
               step: int, step_name: str, status: str, output: str = None,
               review_mode: str = None, session_id: str = None,
               validation: dict = None, metrics: dict = None,
               error: str = None) -> dict:
    """Save or update pipeline state.

    Args:
        state_path: path to pipeline-state.json
        pipeline: pipeline type (ingestion, review, rereview, drafting)
        matter_id: matter identifier
        round_num: round number
        step: step number just completed
        step_name: human-readable step name
        status: step status (completed, failed, in_progress)
        output: output artifact path
        review_mode: review mode setting (for review pipelines)
        session_id: explicit workflow/session identifier
        validation: optional validation summary for this step
        metrics: optional metrics to merge into top-level metrics
        error: failure reason when status is failed

    Returns:
        dict with save result
    """
    now = datetime.now(timezone.utc).isoformat()

    try:
        with state_file_lock(state_path) as lock_path:
            if os.path.exists(state_path):
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
            else:
                state = {}

            state = migrate_state(
                state,
                pipeline=pipeline,
                matter_id=matter_id,
                round_num=round_num,
                review_mode=review_mode,
                session_id=session_id,
                now=now,
            )

            step_key = f"step_{step}"
            state.setdefault("step_artifacts", {})
            step_record = {
                "name": step_name,
                "status": status,
                "output": output,
                "completed_at": now if status == "completed" else None,
            }
            if status == "failed":
                step_record["failed_at"] = now
            if validation is not None:
                step_record["validation"] = validation
            if error:
                step_record["error"] = error

            state["step_artifacts"][step_key] = step_record

            if status == "completed":
                state["last_completed_step"] = max(state.get("last_completed_step", 0), step)

            state["updated_at"] = now
            if review_mode:
                state["review_mode"] = review_mode
            if metrics:
                state.setdefault("metrics", {})
                state["metrics"].update(metrics)

            atomic_write_json(state_path, state)

        return {
            "success": True,
            "state_path": state_path,
            "lock_path": lock_path,
            "schema_version": state["schema_version"],
            "session_id": state["session_id"],
            "last_completed_step": state["last_completed_step"],
            "step": step,
            "status": status,
        }
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        return {
            "success": False,
            "state_path": state_path,
            "step": step,
            "status": status,
            "error": str(exc),
        }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: save-state.py <params_json>"}))
        sys.exit(1)

    params = json.loads(sys.argv[1])
    result = save_state(**params)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result.get("success", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
