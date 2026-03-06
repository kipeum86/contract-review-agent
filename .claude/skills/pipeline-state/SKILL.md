# pipeline-state Skill

Manage pipeline state persistence for resume support and round-level diffs.

## Capabilities

1. **Save State** (`scripts/save-state.py`)
   - Writes/updates `pipeline-state.json` after each step completion
   - Usage: `python3 save-state.py '<json_params>'`
   - Parameters: `state_path`, `pipeline`, `matter_id`, `round_num`, `step`, `step_name`, `status`, `output`, `review_mode`

2. **Load State** (`scripts/load-state.py`)
   - Reads state and determines resume point
   - Usage: `python3 load-state.py <state_path>`
   - Exit code 2 = resumable pipeline found

3. **Round Diff** (`scripts/diff-rounds.py`)
   - Compares clause records between two negotiation rounds
   - Classifies: unchanged, modified, added, removed
   - Usage: `python3 diff-rounds.py <current_clauses_dir> <prior_clauses_dir> <output.json>`

## When to Use

- After every pipeline step completion: save state
- Before starting any pipeline: check for existing state (resume detection)
- WF4 Step 3: diff between negotiation rounds

## Pipeline State Schema

```json
{
  "pipeline": "review",
  "matter_id": "deal-2026-001",
  "round": 1,
  "last_completed_step": 7,
  "review_mode": "moderate",
  "step_artifacts": {
    "step_1": {
      "name": "Target document normalization",
      "status": "completed",
      "output": "working/normalized/clean.md",
      "completed_at": "2026-03-06T10:00:00Z"
    }
  },
  "started_at": "2026-03-06T10:00:00Z",
  "updated_at": "2026-03-06T10:45:00Z"
}
```

## Resume Protocol

1. On any pipeline command, first check for `pipeline-state.json` in the round folder
2. If found with `last_completed_step < final_step`, prompt the user to resume
3. On confirmation, load intermediate artifacts from `step_artifacts` and continue
4. Step counts per pipeline: ingestion=10, review=12, rereview=7, drafting=8

## State Save Timing

Save state **after** each step completes successfully, **before** moving to the next step. State save failure is non-blocking — log a warning and proceed.
