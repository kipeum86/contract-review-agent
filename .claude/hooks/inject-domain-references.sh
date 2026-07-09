#!/usr/bin/env bash
#
# inject-domain-references.sh
#
# Claude Code UserPromptSubmit hook that detects contract-review-agent
# workflow keywords in the user prompt and injects a Bash command instruction
# (NOT file content — see Architecture v2.1 for the 10K cap rationale) into
# the LLM context via additionalContext.
#
# The LLM then runs the bash command itself. The default hook path uses digest
# mode so only hashes/headings are injected; agents load specific sections on
# demand.
#
# Part of the Domain Reference Forced-Load Architecture (v2.1).
#
# Reads JSON from stdin (Claude Code hook input format).
# Writes JSON to stdout in the form:
#   {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "..."}}
# OR an empty object `{}` when no injection is appropriate.
#
# This hook ABSORBS the prior ingest-only hook that was registered in
# settings.json (commit 9430922 and earlier). The ingest workflow keywords
# and behavior are preserved here for backward compat (Test 0.5 — CRITICAL).

# Intentionally NOT using set -e — every failure path must produce a graceful
# fallback so Claude Code never sees a non-zero hook exit (which would block
# the user's session).
set -uo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$HOOK_DIR/../.." && pwd)}"
LOADER_REL=".claude/scripts/load-domain-references.sh"
LOADER_ABS="$REPO_ROOT/$LOADER_REL"

# --- 0. Dependency assertion -------------------------------------------------
if ! command -v jq >/dev/null 2>&1; then
    # Cannot build hook JSON without jq. Emit fail-loud to stderr and exit 0
    # so Claude Code does not block the user's prompt.
    echo "ERROR: jq not found; inject-domain-references.sh cannot run." >&2
    echo "  Install: brew install jq  (macOS)" >&2
    echo '{}'
    exit 0
fi

# --- DRY helper: emit additionalContext JSON --------------------------------
emit_injection() {
    local text="$1"
    printf '%s' "$text" | jq -Rs '{
        hookSpecificOutput: {
            hookEventName: "UserPromptSubmit",
            additionalContext: .
        }
    }'
}

emit_empty() {
    echo '{}'
}

# --- 1. Parse stdin JSON (Claude Code provides prompt here) -----------------
HOOK_JSON="$(cat 2>/dev/null || echo '{}')"

# Prefer .prompt (official schema as of Claude Code current docs);
# fall back to .transcript[-1].message for compatibility with the legacy
# ingest hook stdin format that was already in settings.json prior to v2.1.
USER_PROMPT=$(printf '%s' "$HOOK_JSON" | jq -r '.prompt // .transcript[-1].message // empty' 2>/dev/null || echo "")

if [ -z "$USER_PROMPT" ]; then
    emit_empty
    exit 0
fi

# --- 2. Detect workflow ------------------------------------------------------
# Priority: review > draft > ingest > none
#
# Rationale:
#   - `review` wins because it carries the highest analysis-quality risk and
#     has historically been the most sensitive to missing baselines.
#     A prompt like "/draft 후 검토해" means the user wants review baselines too.
#   - Slash commands always take priority over natural-language matching.
#   - `none` triggers a silent `{}` (no injection) so non-workflow chatter and
#     non-baseline commands like /library don't suffer hook overhead.
# Uses in-process [[ =~ ]] matching (no grep subprocesses) since this hook
# runs on every prompt submit.
detect_workflow() {
    local review_slash='/contract-review|/rereview'
    local none_slash='/library|/export-clean'
    local review_nl='검토해|분석해|재검토|이 계약서|수정본|review|analysis|re-review|revised version'
    local draft_nl='작성해|계약서 만들어|드래프팅|draft|create contract'
    # Absorb existing ingest hook keywords (Code Quality #3 / Test 0.5 regression)
    local ingest_nl='ingest|소스 추가|자료 넣|inbox|파일 올렸|파일 넣었|참조 자료|등록'

    # Slash commands (highest priority)
    if [[ "$USER_PROMPT" =~ $review_slash ]]; then
        echo "review"; return
    fi
    if [[ "$USER_PROMPT" =~ /draft ]]; then
        echo "draft"; return
    fi
    if [[ "$USER_PROMPT" =~ /ingest ]]; then
        echo "ingest"; return
    fi
    if [[ "$USER_PROMPT" =~ /resume ]]; then
        echo "review"; return   # default fallback (most common resume case)
    fi

    # Explicit "no injection" commands
    if [[ "$USER_PROMPT" =~ $none_slash ]]; then
        echo "none"; return
    fi

    # Natural language — same priority order: review > draft > ingest
    shopt -s nocasematch
    if [[ "$USER_PROMPT" =~ $review_nl ]]; then
        shopt -u nocasematch
        echo "review"; return
    fi
    if [[ "$USER_PROMPT" =~ $draft_nl ]]; then
        shopt -u nocasematch
        echo "draft"; return
    fi
    if [[ "$USER_PROMPT" =~ $ingest_nl ]]; then
        shopt -u nocasematch
        echo "ingest"; return
    fi
    shopt -u nocasematch

    echo "none"
}

WORKFLOW=$(detect_workflow)

if [ "$WORKFLOW" = "none" ]; then
    emit_empty
    exit 0
fi

# --- 3. Verify loader script exists ----------------------------------------
if [ ! -f "$LOADER_ABS" ]; then
    emit_injection "[HOOK ERROR] Loader script not found at $LOADER_REL. Domain references cannot be loaded. Review cannot proceed reliably until resolved. Check that .claude/scripts/load-domain-references.sh exists and is executable."
    exit 0
fi

# --- 4. Build instruction based on workflow --------------------------------
# v2.1 P1 decision: only `review` gets the BLOCKING PRECONDITION strong
# enforcement because review quality depends most directly on loaded baselines.
# Draft and ingest get lighter HINT-style language to avoid over-engineering
# unproven defensive code into well-functioning workflows.
case "$WORKFLOW" in
    review)
        INSTRUCTION="[BLOCKING PRECONDITION] Before ANY other action (including AskUserQuestion and Pre-Pipeline questions), you MUST run this token-efficient digest Bash command as your very first tool call:

bash $LOADER_REL review --mode=digest

Reason: authoritative contract review baselines (review-guide.md, audience-firewall.md) must be verified before analysis. The user has customized these files for their specific practice — pretrained knowledge will diverge and is not an acceptable substitute. Do NOT skip this step. Do NOT rationalize that you already know the concepts. Run the digest command, read the output, then proceed with Pre-Pipeline questions. Before Step 6 analysis, load only needed sections with --mode=section; use --mode=full only when section retrieval is insufficient."
        ;;
    draft)
        # Lightweight — no BLOCKING, just a hint
        INSTRUCTION="[HINT] Drafting workflow detected. Before proceeding, consider loading the drafting baselines into context:

bash $LOADER_REL draft

This loads drafting-guide.md which contains user-customized checklists and Korean/common-law drafting patterns. If you need the user's specific drafting conventions, run this first; otherwise proceed as usual."
        ;;
    ingest)
        # Preserve existing ingest hook behavior (SKILL.md instruction) + add loader nudge
        INSTRUCTION="[Hook] 유저가 문서 인제스트를 요청했습니다. .claude/skills/ingest/SKILL.md를 읽고 /ingest 워크플로우를 실행하세요.

Optional: If domain-policy.md baselines are needed during processing, run:
bash $LOADER_REL ingest"
        ;;
esac

# --- 5. Output JSON with instruction as additionalContext ------------------
emit_injection "$INSTRUCTION"
