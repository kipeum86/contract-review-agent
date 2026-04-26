# pipeline-state Skill

Manage pipeline state persistence for resume support and round-level diffs.

## Capabilities

1. **Save State** (`scripts/save-state.py`)
   - Writes/updates `pipeline-state.json` after each step completion
   - Usage: `python3 save-state.py '<json_params>'`
   - Parameters: `state_path`, `pipeline`, `matter_id`, `round_num`, `step`, `step_name`, `status`, `output`, `review_mode`
   - Optional v2 parameters: `session_id`, `validation`, `metrics`, `error`
   - Reads v1 state and writes back v2-compatible state without changing the file name

2. **Load State** (`scripts/load-state.py`)
   - Reads state and determines resume point
   - Migrates v1 state in memory for resume decisions
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
  "schema_version": 2,
  "pipeline": "review",
  "matter_id": "deal-2026-001",
  "round": 1,
  "session_id": "review-deal-2026-001-round-1-20260306T100000Z",
  "last_completed_step": 7,
  "review_mode": "moderate",
  "step_artifacts": {
    "step_1": {
      "name": "Target document normalization",
      "status": "completed",
      "output": "working/normalized/clean.md",
      "completed_at": "2026-03-06T10:00:00Z",
      "validation": {
        "artifact_exists": true
      }
    }
  },
  "metrics": {
    "reference_full_load_count": 0,
    "reference_tokens_estimated": 1200,
    "retrieval_tokens_estimated": 900,
    "hydrated_candidate_count": 3
  },
  "started_at": "2026-03-06T10:00:00Z",
  "updated_at": "2026-03-06T10:45:00Z"
}
```

## Resume Protocol

1. On any pipeline command, first check for `pipeline-state.json` in the round folder
2. If found with `last_completed_step < final_step`, prompt the user to resume
3. **Before resuming, verify artifact existence:**
   - For each step in `step_artifacts` where `step_num ≤ last_completed_step`, check that the `output` file path exists on disk
   - Find the earliest step whose artifact file is missing — this becomes the **effective resume point**, not `last_completed_step + 1`
   - Log: `"Resuming from Step {actual_step}: artifact for declared Step {missing_step} not found at {path}"`
   - If more than half of declared artifacts are missing, warn the user and ask whether to restart from Step 1 rather than resuming
4. On confirmation, load verified intermediate artifacts and continue from the effective resume point
5. Step counts per pipeline: ingestion=10, review=12, rereview=7, drafting=8

## State Save Timing

Save state **after** each step completes successfully, **before** moving to the next step. State save failure is non-blocking — log a warning and proceed.

For failed steps, save `status: "failed"` with `error` and any available `validation` summary before halting. Use the same `session_id` for `pipeline-state.json`, reference loader traces, and matter-level `working/traces/<session_id>/loaded.json`.
