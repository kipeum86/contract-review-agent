#!/usr/bin/env bash
#
# load-domain-references.sh
#
# Loads domain reference files (review-guide.md, audience-firewall.md, etc.)
# into the LLM context via Bash tool stdout. Writes a forensic trace JSON
# to $CRA_RUNS_DIR/sessions/{session_id}/loaded.json by default, or to a
# caller-provided trace directory. The workspace-paths helper keeps legacy
# contract-review/library/runs/ fallback behavior during the bridge period.
#
# Part of the Domain Reference Forced-Load Architecture (v2.2).
# Detailed architecture history is kept in the local-only workspace docs.
#
# Usage:
#   bash .claude/scripts/load-domain-references.sh <workflow> [--mode=full|digest|section] [--section=<heading>] [--file=<name>] [--session-id=<id>] [--trace-dir=<path>]
#
# Workflows:
#   review  → review-guide.md + audience-firewall.md
#   draft   → drafting-guide.md
#   ingest  → domain-policy.md
#
# Environment variables (optional):
#   LOADER_SOURCE       Source label written to trace ("hook" | "agent-prepipe" |
#                       "agent-step5.5" | "root-dispatch" | "chunk-N" | "bash")
#   CONTRACT_REVIEW_SESSION_ID
#                       Explicit session id when --session-id is omitted.
#   CLAUDE_PROJECT_DIR  Override repo root detection (otherwise auto-derived)
#   CRA_RUNS_DIR        Override default runtime trace root.
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
MODE="full"
SECTION=""
SECTION_FILE=""
REQUESTED_SESSION_ID=""
REQUESTED_TRACE_DIR=""
shift

for arg in "$@"; do
    case "$arg" in
        --mode=full|--mode=digest|--mode=section)
            MODE="${arg#--mode=}"
            ;;
        --section=*)
            SECTION="${arg#--section=}"
            ;;
        --file=*)
            SECTION_FILE="${arg#--file=}"
            ;;
        --session-id=*)
            REQUESTED_SESSION_ID="${arg#--session-id=}"
            ;;
        --trace-dir=*)
            REQUESTED_TRACE_DIR="${arg#--trace-dir=}"
            ;;
        *)
            echo "ERROR: unknown option '$arg'" >&2
            echo "  Usage: load-domain-references.sh <workflow> [--mode=full|digest|section] [--section=<heading>] [--file=<name>] [--session-id=<id>] [--trace-dir=<path>]" >&2
            exit 1
            ;;
    esac
done

if [ "$MODE" = "section" ] && [ -z "$SECTION" ]; then
    echo "ERROR: --mode=section requires --section=<heading>" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
if [ -f "$SCRIPT_DIR/workspace-paths.sh" ]; then
    # shellcheck source=.claude/scripts/workspace-paths.sh
    source "$SCRIPT_DIR/workspace-paths.sh"
    REPO_ROOT="$CRA_PROJECT_ROOT"
else
    CRA_RUNS_DIR="${CRA_RUNS_DIR:-$REPO_ROOT/contract-review/library/runs}"
fi
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

# --- 3. Session ID + trace directory -----------------------------------------
# Callers should pass --session-id and --trace-dir once the matter working
# directory exists. The env var is a fallback for shell-only workflows; the
# generated ID preserves backward-compatible manual usage.
SESSION_ID="${REQUESTED_SESSION_ID:-${CONTRACT_REVIEW_SESSION_ID:-}}"
if [ -z "$SESSION_ID" ]; then
    SESSION_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$-${RANDOM:-0}"
fi

if [[ ! "$SESSION_ID" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "ERROR: invalid session id '$SESSION_ID' (allowed: A-Z a-z 0-9 _ . -)" >&2
    exit 1
fi

if [ -n "$REQUESTED_TRACE_DIR" ]; then
    case "$REQUESTED_TRACE_DIR" in
        /*) TRACE_DIR="$REQUESTED_TRACE_DIR" ;;
        *) TRACE_DIR="$REPO_ROOT/$REQUESTED_TRACE_DIR" ;;
    esac
else
    TRACE_DIR="${CRA_RUNS_DIR:-$REPO_ROOT/contract-review/library/runs}/sessions/$SESSION_ID"
fi
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

collect_file_metadata() {
    TRACE_ENTRIES=""
    DIGEST_LINES=""
    BUNDLE_INPUT=""

    for f in "${FILES[@]}"; do
        filepath="$REFS_DIR/$f"

        bytes=$(wc -c < "$filepath" 2>/dev/null | tr -d ' ')
        if [ -z "$bytes" ]; then
            echo "WARN: could not stat $filepath" >&2
            bytes=0
        fi

        sha256_short=$(compute_sha256_short "$filepath")
        last_heading=$(grep '^### ' "$filepath" 2>/dev/null | tail -1 || echo "")
        headings=$(grep -E '^#{1,3} ' "$filepath" 2>/dev/null | sed 's#^#- #' || true)

        DIGEST_LINES="${DIGEST_LINES}## File: ${f} (${bytes} bytes, sha256: ${sha256_short})"$'\n'
        if [ -n "$headings" ]; then
            DIGEST_LINES="${DIGEST_LINES}Available headings:"$'\n'"${headings}"$'\n'
        fi
        DIGEST_LINES="${DIGEST_LINES}"$'\n'
        BUNDLE_INPUT="${BUNDLE_INPUT}${f}:${sha256_short}:${bytes};"

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

    BUNDLE_SHA=$(printf '%s' "$BUNDLE_INPUT" | {
        if command -v shasum >/dev/null 2>&1; then
            shasum -a 256 | cut -c1-12
        elif command -v sha256sum >/dev/null 2>&1; then
            sha256sum | cut -c1-12
        elif command -v openssl >/dev/null 2>&1; then
            openssl dgst -sha256 | awk '{print $NF}' | cut -c1-12
        else
            cat >/dev/null
            echo "unknown"
        fi
    })
}

emit_full() {
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
    echo "Loader mode: full"
    echo ""

    for f in "${FILES[@]}"; do
        filepath="$REFS_DIR/$f"
        bytes=$(wc -c < "$filepath" 2>/dev/null | tr -d ' ')
        sha256_short=$(compute_sha256_short "$filepath")

        echo "## File: $f (${bytes} bytes, sha256: $sha256_short)"
        echo ""
        cat "$filepath" || {
            echo "ERROR: failed to cat $filepath" >&2
            exit 2
        }
        echo ""
        echo "---"
        echo ""
    done

    echo "<!-- END AUTO-INJECTED DOMAIN REFERENCES -->"
}

emit_digest() {
    cat <<'EOF'
<!-- BEGIN AUTO-INJECTED DOMAIN REFERENCE DIGEST -->

**AUTHORITATIVE DOMAIN REFERENCES — DIGEST ONLY**

The reference bundle was verified and traced, but full content was not injected
to conserve tokens. Load only the required sections with:

`bash .claude/scripts/load-domain-references.sh <workflow> --mode=section --section="<heading>"`

Use `--mode=full` only for debugging or when section retrieval is insufficient.

EOF

    echo "Workflow: $WORKFLOW"
    echo "Loader mode: digest"
    echo "Bundle sha256: $BUNDLE_SHA"
    echo ""
    printf '%s' "$DIGEST_LINES"
    echo "<!-- END AUTO-INJECTED DOMAIN REFERENCE DIGEST -->"
}

emit_section_from_file() {
    local file="$1"
    local filepath="$REFS_DIR/$file"
    awk -v wanted="$SECTION" '
        function level(line,    i) {
            for (i = 1; i <= length(line); i++) {
                if (substr(line, i, 1) != "#") return i - 1
            }
            return 0
        }
        BEGIN {
            in_section = 0
            found = 0
            section_level = 0
            wanted_lc = tolower(wanted)
        }
        /^#{1,6} / {
            current_level = level($0)
            heading = $0
            sub(/^#{1,6}[[:space:]]+/, "", heading)
            heading_lc = tolower(heading)
            if (in_section && current_level <= section_level) {
                exit
            }
            if (!in_section && index(heading_lc, wanted_lc) > 0) {
                in_section = 1
                found = 1
                section_level = current_level
            }
        }
        in_section { print }
        END {
            if (!found) exit 42
        }
    ' "$filepath"
}

emit_section() {
    cat <<'EOF'
<!-- BEGIN AUTO-INJECTED DOMAIN REFERENCE SECTION -->

**AUTHORITATIVE DOMAIN REFERENCE SECTION — LOADED VIA BASH**

EOF

    echo "Workflow: $WORKFLOW"
    echo "Loader mode: section"
    echo "Requested section: $SECTION"
    echo ""

    local found_any=0
    for f in "${FILES[@]}"; do
        if [ -n "$SECTION_FILE" ] && [ "$SECTION_FILE" != "$f" ]; then
            continue
        fi
        section_output="$(emit_section_from_file "$f" 2>/dev/null || true)"
        if [ -n "$section_output" ]; then
            found_any=1
            bytes=$(wc -c < "$REFS_DIR/$f" 2>/dev/null | tr -d ' ')
            sha256_short=$(compute_sha256_short "$REFS_DIR/$f")
            echo "## File: $f (${bytes} bytes, sha256: $sha256_short)"
            echo ""
            printf '%s\n' "$section_output"
            echo ""
            echo "---"
            echo ""
        fi
    done

    if [ "$found_any" -ne 1 ]; then
        echo "ERROR: requested section not found: $SECTION" >&2
        exit 2
    fi

    echo "<!-- END AUTO-INJECTED DOMAIN REFERENCE SECTION -->"
}

# --- 5. Emit stdout block ----------------------------------------------------
collect_file_metadata

case "$MODE" in
    full)
        emit_full
        ;;
    digest)
        emit_digest
        ;;
    section)
        emit_section
        ;;
esac

# --- 6. Write trace JSON ----------------------------------------------------
SOURCE_TYPE="${LOADER_SOURCE:-bash}"
TRACE_FILE="$TRACE_DIR/loaded.json"

jq -n \
    --arg workflow "$WORKFLOW" \
    --arg loader_version "2.2" \
    --arg loader_mode "$MODE" \
    --arg bundle_sha256 "$BUNDLE_SHA" \
    --arg source "$SOURCE_TYPE" \
    --arg loaded_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg session_id "$SESSION_ID" \
    --argjson files "[$TRACE_ENTRIES]" \
    '{
        workflow: $workflow,
        loader_version: $loader_version,
        loader_mode: $loader_mode,
        bundle_sha256: $bundle_sha256,
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
