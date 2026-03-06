#!/usr/bin/env python3
"""
Pipeline state persistence.
Writes and updates pipeline-state.json for resume support.
"""

import sys
import os
import json
from datetime import datetime, timezone


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

    # Load existing state or create new
    if os.path.exists(state_path):
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
    else:
        state = {
            'pipeline': pipeline,
            'matter_id': matter_id,
            'round': round_num,
            'last_completed_step': 0,
            'review_mode': review_mode,
            'step_artifacts': {},
            'started_at': now,
            'updated_at': now,
        }

    # Update step status
    step_key = f"step_{step}"
    state['step_artifacts'][step_key] = {
        'name': step_name,
        'status': status,
        'output': output,
        'completed_at': now if status == 'completed' else None,
    }

    if status == 'completed':
        state['last_completed_step'] = max(state.get('last_completed_step', 0), step)

    state['updated_at'] = now
    if review_mode:
        state['review_mode'] = review_mode

    # Write state file
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    return {
        'success': True,
        'state_path': state_path,
        'last_completed_step': state['last_completed_step'],
        'step': step,
        'status': status,
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: save-state.py <params_json>'}))
        sys.exit(1)

    params = json.loads(sys.argv[1])
    result = save_state(**params)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
