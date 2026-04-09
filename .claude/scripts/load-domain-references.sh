#!/usr/bin/env bash
#
# load-domain-references.sh
#
# Loads domain reference files (review-guide.md, audience-firewall.md, etc.)
# into the LLM context via Bash tool stdout. Writes a forensic trace JSON
# to contract-review/library/runs/sessions/{session_id}/loaded.json.
#
# Part of the Domain Reference Forced-Load Architecture (v2.1).
# See: docs/ko/domain-reference-forced-load.md (when migrated from output/)
#
# Usage:
#   bash .claude/scripts/load-domain-references.sh <workflow>
#
# Workflows:
#   review  → review-guide.md + audience-firewall.md
#   draft   → drafting-guide.md
#   ingest  → domain-policy.md
#
# Environment variables (optional):
#   LOADER_SOURCE       Source label written to trace ("hook" | "agent-prepipe" |
#                       "agent-step5.5" | "root-dispatch" | "chunk-N" | "bash")
#   CLAUDE_PROJECT_DIR  Override repo root detection (otherwise auto-derived)
#
# Exit codes:
#   0  success
#   1  bad usage / unknown workflow
#   2  required reference file missing or filesystem error
#   3  required dependency missing (jq, sha256 tool)

# Intentionally NOT using `set -e` — we need controlled fallbacks for sub-commands.
set -uo pipefail

# --- 0. Dependency assertion -------------------------------------------------
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq not found; load-domain-references.sh requires jq." >&2
    echo "  Install: brew install jq  (macOS)  or  apt-get install jq  (Linux)" >&2
    exit 3
fi

# --- 1. Parse + validate workflow arg ----------------------------------------
if [ "$#" -lt 1 ]; then
    echo "ERROR: usage: load-domain-references.sh <workflow>" >&2
    echo "  Valid workflows: review | draft | ingest" >&2
    exit 1
fi
WORKFLOW="$1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
REFS_DIR="$REPO_ROOT/.claude/skills/review-domain-knowledge/references"

# --- 2. Resolve workflow → files ---------------------------------------------
declare -a FILES
case "$WORKFLOW" in
    review)
        FILES=("review-guide.md" "audience-firewall.md")
        ;;
    draft)
        FILES=("drafting-guide.md")
        ;;
    ingest)
        FILES=("domain-policy.md")
        ;;
    *)
        echo "ERROR: unknown workflow '$WORKFLOW'" >&2
        echo "  Valid: review | draft | ingest" >&2
        exit 1
        ;;
esac

# --- 3. Self-generated session ID (no env var dependency) --------------------
# We deliberately do NOT rely on $CONTRACT_REVIEW_SESSION_ID or any Claude Code
# session identifier — those do not propagate reliably across sub-agent dispatch.
# Each invocation creates its own timestamped + PID + random session dir.
# AGENT.md Step 1.5 uses `ls -t` to discover the most recent loaded.json.
SESSION_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$-${RANDOM:-0}"
TRACE_DIR="$REPO_ROOT/contract-review/library/runs/sessions/$SESSION_ID"
mkdir -p "$TRACE_DIR" || {
    echo "ERROR: failed to create trace dir $TRACE_DIR" >&2
    exit 2
}

# --- 4. Verify all reference files exist before emitting any output ---------
for f in "${FILES[@]}"; do
    filepath="$REFS_DIR/$f"
    if [ ! -f "$filepath" ]; then
        echo "ERROR: required reference file missing: $filepath" >&2
        echo "  This is a critical failure. Review cannot proceed." >&2
        exit 2
    fi
done

# --- Helper: compute sha256 short with explicit fallback chain --------------
compute_sha256_short() {
    local file="$1"
    local sha=""
    if command -v shasum >/dev/null 2>&1; then
        sha=$(shasum -a 256 "$file" 2>/dev/null | cut -c1-8 || echo "")
    fi
    if [ -z "$sha" ] && command -v sha256sum >/dev/null 2>&1; then
        sha=$(sha256sum "$file" 2>/dev/null | cut -c1-8 || echo "")
    fi
    if [ -z "$sha" ] && command -v openssl >/dev/null 2>&1; then
        sha=$(openssl dgst -sha256 "$file" 2>/dev/null | awk '{print $NF}' | cut -c1-8 || echo "")
    fi
    if [ -z "$sha" ]; then
        sha="unknown"
    fi
    echo "$sha"
}

# --- 5. Emit stdout block (cat files with markers) ---------------------------
cat <<'EOF'
<!-- BEGIN AUTO-INJECTED DOMAIN REFERENCES -->

**AUTHORITATIVE DOMAIN REFERENCES — LOADED VIA BASH**

The following reference files are the authoritative source of judgment
criteria, risk baselines, and firewall rules. They have been loaded via
the Bash tool. Use them directly during analysis; do not substitute
pretrained knowledge — the user has customized these files for their
specific practice.

---

EOF

echo "Workflow: $WORKFLOW"
echo ""

# Build trace JSON entries while catting the files
TRACE_ENTRIES=""
for f in "${FILES[@]}"; do
    filepath="$REFS_DIR/$f"

    bytes=$(wc -c < "$filepath" 2>/dev/null | tr -d ' ')
    if [ -z "$bytes" ]; then
        echo "WARN: could not stat $filepath" >&2
        bytes=0
    fi

    sha256_short=$(compute_sha256_short "$filepath")
    last_heading=$(grep '^### ' "$filepath" 2>/dev/null | tail -1 || echo "")

    echo "## File: $f (${bytes} bytes, sha256: $sha256_short)"
    echo ""
    cat "$filepath" || {
        echo "ERROR: failed to cat $filepath" >&2
        exit 2
    }
    echo ""
    echo "---"
    echo ""

    entry=$(jq -n \
        --arg name "$f" \
        --arg path ".claude/skills/review-domain-knowledge/references/$f" \
        --argjson bytes "$bytes" \
        --arg sha "$sha256_short" \
        --arg heading "$last_heading" \
        '{name: $name, path: $path, byte_size: $bytes, sha256_short: $sha, last_section_heading: $heading}') || {
        echo "WARN: failed to build trace entry for $f" >&2
        continue
    }

    if [ -n "$TRACE_ENTRIES" ]; then
        TRACE_ENTRIES="${TRACE_ENTRIES},${entry}"
    else
        TRACE_ENTRIES="$entry"
    fi
done

echo "<!-- END AUTO-INJECTED DOMAIN REFERENCES -->"

# --- 6. Write trace JSON ----------------------------------------------------
SOURCE_TYPE="${LOADER_SOURCE:-bash}"
TRACE_FILE="$TRACE_DIR/loaded.json"

jq -n \
    --arg workflow "$WORKFLOW" \
    --arg loader_version "2.1" \
    --arg source "$SOURCE_TYPE" \
    --arg loaded_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg session_id "$SESSION_ID" \
    --argjson files "[$TRACE_ENTRIES]" \
    '{
        workflow: $workflow,
        loader_version: $loader_version,
        source: $source,
        loaded_at: $loaded_at,
        session_id: $session_id,
        files_loaded: $files
    }' > "$TRACE_FILE" || {
    echo "WARN: failed to write trace JSON $TRACE_FILE" >&2
}

# --- 7. Print discovery markers for agents/LLM ------------------------------
echo ""
echo "SESSION_ID: $SESSION_ID"
echo "TRACE: $TRACE_FILE"
