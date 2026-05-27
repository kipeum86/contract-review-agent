#!/usr/bin/env bash

# Source this helper before review/draft/runtime filesystem work.
# Explicit CRA_* environment variables win; otherwise prefer the unified
# workspace and keep legacy root paths available during the bridge period.

if [ -z "${CRA_PROJECT_ROOT:-}" ]; then
    if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
        CRA_PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
    elif [ -n "${BASH_SOURCE[0]:-}" ]; then
        _CRA_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        CRA_PROJECT_ROOT="$(cd "$_CRA_SCRIPT_DIR/../.." && pwd)"
    elif [ -d "contract-review" ] && [ -d ".claude" ]; then
        CRA_PROJECT_ROOT="$(pwd)"
    else
        CRA_PROJECT_ROOT="$(pwd)"
    fi
fi

CRA_PROJECT_ROOT="$(cd "$CRA_PROJECT_ROOT" && pwd)"
export CRA_PROJECT_ROOT

CRA_WORKSPACE_DIR="${CRA_WORKSPACE_DIR:-$CRA_PROJECT_ROOT/contract-review/workspace}"
CRA_LEGACY_INPUT_DIR="${CRA_LEGACY_INPUT_DIR:-$CRA_PROJECT_ROOT/input}"
CRA_LEGACY_OUTPUT_DIR="${CRA_LEGACY_OUTPUT_DIR:-$CRA_PROJECT_ROOT/output}"
CRA_LEGACY_LOGS_DIR="${CRA_LEGACY_LOGS_DIR:-$CRA_PROJECT_ROOT/logs}"
CRA_LEGACY_MATTERS_DIR="${CRA_LEGACY_MATTERS_DIR:-$CRA_PROJECT_ROOT/contract-review/matters}"
CRA_LEGACY_RUNS_DIR="${CRA_LEGACY_RUNS_DIR:-$CRA_PROJECT_ROOT/contract-review/library/runs}"

export CRA_WORKSPACE_DIR
export CRA_LEGACY_INPUT_DIR
export CRA_LEGACY_OUTPUT_DIR
export CRA_LEGACY_LOGS_DIR
export CRA_LEGACY_MATTERS_DIR
export CRA_LEGACY_RUNS_DIR

_cra_pick_dir() {
    local var_name="$1"
    local workspace_dir="$2"
    local legacy_dir="$3"
    local current_value

    eval "current_value=\"\${$var_name:-}\""
    if [ -n "$current_value" ]; then
        export "$var_name=$current_value"
        return
    fi

    if [ -d "$workspace_dir" ]; then
        export "$var_name=$workspace_dir"
    elif [ -d "$legacy_dir" ]; then
        export "$var_name=$legacy_dir"
    else
        export "$var_name=$workspace_dir"
    fi
}

_cra_join_distinct_existing() {
    local first="$1"
    local second="$2"

    if [ "$first" = "$second" ] || [ ! -d "$second" ]; then
        printf '%s' "$first"
    else
        printf '%s:%s' "$first" "$second"
    fi
}

_cra_pick_dir CRA_INPUT_DIR "$CRA_WORKSPACE_DIR/input" "$CRA_LEGACY_INPUT_DIR"
_cra_pick_dir CRA_OUTPUT_DIR "$CRA_WORKSPACE_DIR/output" "$CRA_LEGACY_OUTPUT_DIR"
_cra_pick_dir CRA_LOGS_DIR "$CRA_WORKSPACE_DIR/logs" "$CRA_LEGACY_LOGS_DIR"
_cra_pick_dir CRA_MATTERS_DIR "$CRA_WORKSPACE_DIR/matters" "$CRA_LEGACY_MATTERS_DIR"
_cra_pick_dir CRA_RUNS_DIR "$CRA_WORKSPACE_DIR/runs" "$CRA_LEGACY_RUNS_DIR"

CRA_INPUT_DIRS="$( _cra_join_distinct_existing "$CRA_INPUT_DIR" "$CRA_LEGACY_INPUT_DIR" )"
CRA_OUTPUT_DIRS="$( _cra_join_distinct_existing "$CRA_OUTPUT_DIR" "$CRA_LEGACY_OUTPUT_DIR" )"
CRA_MATTERS_DIRS="$( _cra_join_distinct_existing "$CRA_MATTERS_DIR" "$CRA_LEGACY_MATTERS_DIR" )"

export CRA_INPUT_DIRS
export CRA_OUTPUT_DIRS
export CRA_MATTERS_DIRS
