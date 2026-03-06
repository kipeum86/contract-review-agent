# Resume Interrupted Pipeline

Resume a previously interrupted pipeline from its last completed step.

$ARGUMENTS

---

## Process

1. **Scan for pipeline states**: Search all `contract-review/matters/*/round_*/pipeline-state.json` files for incomplete pipelines (where `last_completed_step < final_step`).

2. **If no interrupted pipelines found**: Inform the user that no resumable pipelines exist.

3. **If one interrupted pipeline found**: Display the pipeline details:
   - Matter ID, round number, pipeline type (review/re-review/draft)
   - Last completed step and total steps
   - Timestamp of interruption
   - Ask the user to confirm resumption

4. **If multiple interrupted pipelines found**: List all of them and ask the user to select which one to resume.

5. **Resume**: Load all intermediate artifacts from `step_artifacts` in the pipeline state file. Continue execution from the next incomplete step. Update the pipeline state after each step completion.
