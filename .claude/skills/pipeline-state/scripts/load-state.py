#!/usr/bin/env python3
"""
Pipeline state loader.
Reads pipeline-state.json and determines the resume point.
"""

import sys
import os
import json


# Total steps per pipeline type
PIPELINE_STEPS = {
    'ingestion': 10,
    'review': 12,
    'rereview': 7,
    'drafting': 8,
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
        'state_path': state_path,
        'exists': False,
        'state': None,
        'resume_from': None,
        'is_complete': False,
        'message': None,
    }

    if not os.path.exists(state_path):
        result['message'] = 'No pipeline state found. Starting fresh.'
        return result

    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        result['message'] = f'Pipeline state file is corrupt: {e}'
        return result

    result['exists'] = True
    result['state'] = state

    pipeline = state.get('pipeline', 'review')
    total_steps = PIPELINE_STEPS.get(pipeline, 12)
    last_completed = state.get('last_completed_step', 0)

    if last_completed >= total_steps:
        result['is_complete'] = True
        result['message'] = (
            f"Pipeline '{pipeline}' completed all {total_steps} steps. "
            f"Last updated: {state.get('updated_at', 'unknown')}"
        )
    else:
        resume_step = last_completed + 1
        result['resume_from'] = resume_step

        # Find the name of the last completed step
        last_step_key = f"step_{last_completed}"
        last_step_info = state.get('step_artifacts', {}).get(last_step_key, {})
        last_step_name = last_step_info.get('name', f'Step {last_completed}')

        result['message'] = (
            f"Pipeline '{pipeline}' was interrupted after '{last_step_name}' "
            f"(Step {last_completed}/{total_steps}). "
            f"Resume from Step {resume_step}?"
        )

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: load-state.py <state_path>'}))
        sys.exit(1)

    state_path = sys.argv[1]
    result = load_state(state_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Exit code 2 = resumable (incomplete pipeline found)
    if result['exists'] and not result['is_complete']:
        sys.exit(2)


if __name__ == '__main__':
    main()
