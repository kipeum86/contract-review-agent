#!/usr/bin/env python3
"""Pipeline state persistence with lock-guarded atomic writes."""

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone

import fcntl


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


def save_state(state_path: str, pipeline: str, matter_id: str, round_num: int,
               step: int, step_name: str, status: str, output: str = None,
               review_mode: str = None) -> dict:
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
                state = {
                    "pipeline": pipeline,
                    "matter_id": matter_id,
                    "round": round_num,
                    "last_completed_step": 0,
                    "review_mode": review_mode,
                    "step_artifacts": {},
                    "started_at": now,
                    "updated_at": now,
                }

            step_key = f"step_{step}"
            state.setdefault("step_artifacts", {})
            state["step_artifacts"][step_key] = {
                "name": step_name,
                "status": status,
                "output": output,
                "completed_at": now if status == "completed" else None,
            }

            if status == "completed":
                state["last_completed_step"] = max(state.get("last_completed_step", 0), step)

            state["updated_at"] = now
            if review_mode:
                state["review_mode"] = review_mode

            atomic_write_json(state_path, state)

        return {
            "success": True,
            "state_path": state_path,
            "lock_path": lock_path,
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
