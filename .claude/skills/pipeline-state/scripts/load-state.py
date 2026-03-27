#!/usr/bin/env python3
"""Pipeline state loader with artifact verification for safe resume."""

import json
import os
import sys


# Total steps per pipeline type
PIPELINE_STEPS = {
    'ingestion': 10,
    'review': 12,
    'rereview': 7,
    'drafting': 8,
}


def resolve_output_path(state_path: str, output_path: str) -> str:
    """Resolve a declared output path relative to the state file."""
    if os.path.isabs(output_path):
        return output_path
    base_dir = os.path.dirname(os.path.abspath(state_path)) or os.getcwd()
    return os.path.abspath(os.path.join(base_dir, output_path))


def verify_output_path(path: str) -> tuple[bool, str | None]:
    """Check whether an output path exists and is minimally usable."""
    if not os.path.exists(path):
        return False, "missing"

    if os.path.isdir(path):
        try:
            with os.scandir(path) as entries:
                for _entry in entries:
                    return True, None
        except OSError:
            return False, "unreadable_directory"
        return False, "empty_directory"

    try:
        size = os.path.getsize(path)
    except OSError:
        return False, "unreadable_file"

    if size == 0:
        return False, "empty_file"
    return True, None


def verify_step_artifacts(state_path: str, state: dict, last_completed: int) -> dict:
    """Verify that completed-step artifacts are still present on disk."""
    step_artifacts = state.get("step_artifacts", {})
    checks = []
    earliest_invalid_step = None
    verified_through_step = 0
    failed_checks = 0
    checked_steps = 0

    for step in range(1, last_completed + 1):
        step_key = f"step_{step}"
        step_info = step_artifacts.get(step_key)
        check = {
            "step": step,
            "step_key": step_key,
            "name": f"Step {step}",
            "output": None,
            "resolved_output": None,
            "verified": False,
            "reason": None,
        }

        if not step_info:
            check["reason"] = "missing_step_record"
            failed_checks += 1
            checked_steps += 1
        else:
            check["name"] = step_info.get("name", check["name"])
            output_path = step_info.get("output")
            check["output"] = output_path

            if step_info.get("status") != "completed":
                check["reason"] = "step_not_completed"
                failed_checks += 1
                checked_steps += 1
            elif not output_path:
                check["verified"] = True
                check["reason"] = "no_output_declared"
                verified_through_step = step
            else:
                resolved_output = resolve_output_path(state_path, output_path)
                check["resolved_output"] = resolved_output
                check["verified"], check["reason"] = verify_output_path(resolved_output)
                checked_steps += 1
                if not check["verified"]:
                    failed_checks += 1

        checks.append(check)

        if check["verified"] and earliest_invalid_step is None:
            verified_through_step = step
        elif not check["verified"] and earliest_invalid_step is None:
            earliest_invalid_step = step

    restart_recommended = checked_steps > 0 and failed_checks > (checked_steps / 2)
    return {
        "checked_steps": checked_steps,
        "failed_checks": failed_checks,
        "verified_through_step": verified_through_step,
        "earliest_invalid_step": earliest_invalid_step,
        "restart_recommended": restart_recommended,
        "checks": checks,
    }


def load_state(state_path: str) -> dict:
    """Load pipeline state and determine resume point.

    Returns:
        dict with:
          - exists: bool
          - state: full state object (if exists)
          - resume_from: next step to execute (if incomplete)
          - is_complete: bool
          - message: human-readable status
    """
    result = {
        "state_path": state_path,
        "exists": False,
        "state": None,
        "resume_from": None,
        "declared_resume_from": None,
        "verified_through_step": 0,
        "is_complete": False,
        "message": None,
        "artifact_verification": {
            "checked_steps": 0,
            "failed_checks": 0,
            "verified_through_step": 0,
            "earliest_invalid_step": None,
            "restart_recommended": False,
            "checks": [],
        },
    }

    if not os.path.exists(state_path):
        result["message"] = "No pipeline state found. Starting fresh."
        return result

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        result["message"] = f"Pipeline state file is corrupt: {e}"
        return result

    result["exists"] = True
    result["state"] = state

    pipeline = state.get("pipeline", "review")
    total_steps = PIPELINE_STEPS.get(pipeline, 12)
    last_completed = int(state.get("last_completed_step", 0) or 0)
    declared_resume_from = min(last_completed + 1, total_steps + 1)
    result["declared_resume_from"] = declared_resume_from

    verification = verify_step_artifacts(state_path, state, min(last_completed, total_steps))
    result["artifact_verification"] = verification
    result["verified_through_step"] = verification["verified_through_step"]

    earliest_invalid_step = verification["earliest_invalid_step"]
    if earliest_invalid_step is not None:
        invalid_check = verification["checks"][-1]
        result["resume_from"] = earliest_invalid_step
        result["message"] = (
            f"Pipeline '{pipeline}' recorded completion through Step {last_completed}, "
            f"but artifact verification failed for Step {earliest_invalid_step} "
            f"('{invalid_check['name']}': {invalid_check['reason']}). "
            f"Resume from Step {earliest_invalid_step}."
        )
        return result

    if last_completed >= total_steps:
        result["is_complete"] = True
        result["message"] = (
            f"Pipeline '{pipeline}' completed all {total_steps} steps. "
            f"Last updated: {state.get('updated_at', 'unknown')}"
        )
        return result

    resume_step = declared_resume_from
    result["resume_from"] = resume_step

    last_step_key = f"step_{last_completed}"
    last_step_info = state.get("step_artifacts", {}).get(last_step_key, {})
    last_step_name = last_step_info.get("name", f"Step {last_completed}")

    result["message"] = (
        f"Pipeline '{pipeline}' was interrupted after '{last_step_name}' "
        f"(Step {last_completed}/{total_steps}). "
        f"Resume from Step {resume_step}?"
    )

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: load-state.py <state_path>"}))
        sys.exit(1)

    state_path = sys.argv[1]
    result = load_state(state_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Exit code 2 = resumable (incomplete pipeline found)
    if result["exists"] and not result["is_complete"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
