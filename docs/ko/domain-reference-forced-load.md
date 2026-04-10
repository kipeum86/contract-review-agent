# Domain Reference Forced-Load Architecture

> **상태**: 구현 완료 (2026-04-10). 커밋 `c5a4a3e`..`a595f44` (main branch). 이 문서는 2026-04-09 인시던트 대응으로 작성된 기획이며 v1 → v2 → v2.1 in-place patch를 거쳐 ship된 최종 아키텍처이다.
>
> **작성일**: 2026-04-09 (v2), patched 2026-04-10 (v2.1)
> **대상 프로젝트**: contract-review-agent
> **구현 방식**: 코드베이스 레벨 (커밋하여 모든 사용자에게 git pull로 배포)
>
> **핵심 메커니즘**: **Bash Indirect Injection** — Hook은 짧은 Bash 명령 지시문만 주입하고, LLM이 Bash tool로 loader script를 실행하여 파일 내용 전체를 Bash tool result로 context에 주입. 3중 방어선 (Hook / AGENT.md / CLAUDE.md dispatch) + script 자동 생성 forensic trace.
>
> **읽는 순서**: Section 1 (배경/인시던트) → Section 5 (아키텍처) → Section 10 (테스트 절차) → Section 14 (아직 실측 필요한 항목). 나머지는 구현 상세 및 v1→v2 설계 변경 이력이다.

## v2 → v2.1 Patch Summary (9 patches from /plan-eng-review)

| # | Patch | 섹션 |
|---|---|---|
| P1 | Draft/ingest 경량화 — BLOCKING 문구 제거, loader 호출만 | 5.2 + 5.4 + 6 |
| P2 | Pre-Pipeline 0 filesystem check (LLM self-check 제거) | 5.4 |
| P3 | Session ID: `ls -t` 방식으로 전환 (환경변수 의존 제거) | 5.3 + 5.4 Step 1.5 + 12 |
| P4 | compile-report.js pseudo-code 재작성 (실제 구조 반영, 양 renderer) | 5.4 Step 10 + 9.3 |
| P5 | jq dependency 명시 + script assertion | 7 + 11.2 + 5.2/5.3 |
| P6 | Defensive error handling + `emit_injection()` DRY helper | 5.2 + 5.3 |
| P7 | Test 4b 추가 — compile-report.js unit test (3 variants) | 10 |
| P8 | Test 9 추가 — concurrent sessions edge case | 10 |
| P9 | detect_workflow 우선순위 주석 보강 | 5.2 |

---

## v1 대비 주요 변경 사항 (필독)

v1은 **Hook으로 파일 내용 전체(~25KB)를 `additionalContext`에 직접 주입**하는 설계였다. `/plan-eng-review` feasibility spike에서 이것이 **물리적으로 불가능**하다는 것이 판명되었다:

- Claude Code hook `additionalContext` 필드는 **10,000 문자 제한** (공식 문서 명시)
- `review-guide.md` = 25,018 bytes → **2.5배 초과**
- 초과 시 파일로 저장되고 "preview + 경로"로 치환 → LLM이 파일을 Read해야 하는 상황 → **인시던트 원인과 동일 경로로 회귀**

v2는 이 제약을 우회하기 위해 **메커니즘을 전환**했다:

| 구분 | v1 | v2 |
|---|---|---|
| Hook 역할 | 파일 내용 전체 주입 | **짧은 Bash 명령 지시문만 주입** (< 1KB) |
| 파일 내용 전달 경로 | Hook `additionalContext` (10K cap) | **Bash tool stdout → LLM context** (no cap) |
| Script 개수 | 1개 (loader) | **2개 분리** (injector for hook / loader for Bash) |
| 방어선 | 2중 (Hook + AGENT.md) | **3중** (Hook + AGENT.md Step 5.5 + CLAUDE.md dispatch 절차) |
| Trace 경로 | `matters/{id}/working/baseline-context/` (존재 전 시점 문제) | **`library/runs/sessions/{id}/`** 선 기록 → Step 1.5에서 matter로 merge |
| Executive Summary trace 라인 | LLM이 작성 (hallucination 위험) | **compile-report.js가 JSON 읽어 자동 주입** (LLM 우회) |
| 기존 ingest hook | 공존 가정 (중복 주입 문제) | **새 통합 hook에 흡수** (회귀 테스트 CRITICAL) |
| Chunking | 미고려 | **각 chunk 시작 시 loader 재실행** |
| Test 개수 | 5 (Test 1-5) | **9** (+ Test 0.5 regression, Test 6 sub-agent, Test 7 adherence gate, Test 8 chunking) |

모든 세부 결정은 `logs/session-2026-04-09-common-law-conversion-and-forced-load-architecture.md`에 기록됨.

---

## 1. 배경

### 1.1 인시던트

2026-04-09, 사용자 A(지인)가 `/contract-review`로 EPC 계약 검토를 실행한 뒤 결과가 기대와 달라 Claude에게 직접 물었다:

> "검토 과정에서 review-guide.md의 '### EPC / Construction Contracts'를 기반으로 검토를 했니? 아니면 고려하지 않고 검토를 했니? 사실대로만 답해줘"

Claude의 답변:

> "사실대로 말씀드리겠습니다. **고려하지 않았습니다.** 검토 과정에서 review-guide.md를 읽지 않았습니다. 파일이 IDE에서 열려 있다는 알림은 받았지만, 실제로 해당 파일을 읽는 도구 호출을 하지 않았고, 내용을 분석에 반영하지 않았습니다. 검토는 전적으로 계약서 원문 파싱 결과와 제 **사전 학습 지식**(FIDIC Silver Book, 국제 EPC 시장 관행)에 기반하여 수행되었습니다."

### 1.2 영향 범위

사용자 A가 직전에 `Common-Law-전환-통합-프롬프트.md`를 실행하여 `review-guide.md`에 심어둔 **Common Law Contract Risk Reference**, **EPC 블록**, **E&W/US/SG jurisdiction flag** 전부가 **한 번도 실제 검토에 사용되지 않았다**. 사용자 A가 투자한 customization이 완전히 무시된 것이다.

과거의 모든 `/contract-review` 결과 신뢰성도 재평가 필요. 검토 결과가 파일 기반인지 LLM 사전학습 지식 기반인지 **사후 구분이 불가능**하기 때문이다.

### 1.3 구조적 결함 — 일회성 버그가 아닌 이유

`.claude/agents/review-agent/AGENT.md` Step 6 원문:

> "Apply the four-lens analysis framework from `review-guide.md` (Asymmetries / Overbroad Qualifiers / Missing Protections / Structural Traps)"

이 지시는 LLM이 두 가지 의미로 해석 가능:
1. **좁은 해석**: "Read 도구로 로드하고 내용에 따라 수행"
2. **넓은 해석**: "'four-lens framework'라는 개념을 사전학습 지식에서 꺼내 수행"

LLM은 일관되게 **넓은 해석**을 선택해왔다. 지시어를 "MUST Read"로 강화하는 것만으로는 해결되지 않는다 — 어떤 강한 언어도 LLM의 자발적 준수에 의존하는 이상 재발 가능. `references/` 폴더의 모든 파일(audience-firewall.md, drafting-guide.md, domain-policy.md)에 동일 패턴이 적용된다.

## 2. 문제 정의

**커스터마이즈 가능한 도메인 지식 파일이 존재하지만, 이를 실제 LLM context에 주입하는 메커니즘이 지시문(prompt)에만 의존한다.** 결과적으로:

1. 사용자의 customization(law firm house position, risk baseline, jurisdiction 기준 등)이 무시됨
2. 검토 결과의 일관성 없음 — 세션마다 파일을 읽을 수도, 안 읽을 수도 있음
3. Forensic 증거 없음 — 사후 "이 검토가 review-guide.md를 실제 사용했는가?" 검증 불가
4. 디버깅 불가 — 이상한 결과가 나왔을 때 파일 내용 문제인지, 파일 미로드 문제인지 구분 불가

## 3. 목표와 비목표

### 3.1 Goals

| # | 목표 | 측정 기준 |
|---|---|---|
| G1 | LLM의 자발적 Read 호출 없이 reference 파일 내용을 context에 주입 | Loader script Bash 실행 결과 context에 실제 존재 (canary heading 검증) |
| G2 | **3중 방어선** (Hook + AGENT.md Step 5.5 + CLAUDE.md dispatch 절차) | 각 레이어 독립 작동 검증 |
| G3 | **Review workflow 완전 방어 + draft/ingest 경량 지원** (P1 — Incremental) | review/rereview는 3중 방어선 전체 적용, draft/ingest는 loader 호출 hint만 (실제 인시던트 없음) |
| G4 | **Script-generated forensic trace** (LLM hallucination 우회) | sha256 + canary heading이 실제 파일과 일치 |
| G5 | Zero friction after git pull | 사용자가 git pull 후 별도 설정 없이 (또는 hook 실행 승인 1회만으로) 즉시 작동 |
| G6 | Context efficiency | Workflow 키워드 감지 시에만 주입. `/library` 같은 무관 명령에는 주입 안 함 |
| G7 | Extensibility | 새 workflow 또는 새 reference 파일 추가가 단일 매핑 테이블만 수정하면 되도록 |
| G8 | 기존 파일 내용 무변경 | Reference 파일 자체는 건드리지 않음 |
| G9 | **기존 ingest hook 기능 완전 보존** | Regression test (Test 0.5) 통과 |
| G10 | **LLM Bash 실행 준수율 ≥ 90%** | Test 7 gate 통과 (10회 중 ≥ 9회) |
| G11 | Chunking + reference 일관성 | 각 chunk 시작 시 loader 재실행, chunk별 trace 누적 |

### 3.2 Non-Goals

- Policy YAML 파일 강제 로드 (이미 `query-index.py`가 `open()`으로 처리)
- Reference 파일 내용 schema 검증 (freeform markdown)
- Agent 간 reference 공유 (각 agent 독립 로드)
- Hook rate limiting (실행 시간 ~30-60ms로 negligible)
- Windows 지원 (bash script 전제)
- Claude Code 외 도구 완전 지원 (Cursor/Codex CLI 등은 hook 미발동 — AGENT.md Bash 경로만 best-effort)
- 과거 검토 결과 자동 소급 재검증 (사용자 수동 `/rereview`)
- `drafting-guide.md` / `domain-policy.md` 내용 업데이트 (로드 메커니즘만 픽스, 내용은 별도 작업)
- Agent 간 dispatch 프로토콜 재설계 (sub-agent 구조 유지)
- `library/runs/sessions/` 자동 정리/aging (수동 정리, Future work)
- Hook으로 큰 파일 전체 주입 (v1에서 시도했으나 10K cap으로 폐기)
- Selective sub-section injection (Future Enhancements — Section 16)
- Template vs General 명시적 선택 UI (Future Enhancements — Section 16)
- 대형 계약서 chunking 시 reference caching (현재는 매 chunk 재주입)

## 4. 설계 원칙

| 원칙 | 의미 |
|---|---|
| **Explicit over implicit** | "파일을 읽어라"고 지시하지 않고, Bash 명령으로 파일 내용을 context에 밀어넣음 |
| **Redundancy** | Hook(엔진 레벨) + AGENT.md(sub-agent 레벨) + CLAUDE.md(root agent dispatch 레벨) 3중 경로 |
| **Fail loud** | Reference 파일이 없거나 깨지면 즉시 exit 2, 조용히 skip 금지. Hook도 loader 실패를 catch하여 에러 JSON 주입 |
| **Idempotent** | 반복 실행해도 부작용 없음. Hook과 AGENT.md Bash step이 중복 주입해도 무해 |
| **Canonical source** | Reference 파일은 복사하지 않고 그 자리에서 읽음 |
| **Observable** | 모든 로드는 script-generated trace JSON으로 기록. sha256 + canary heading으로 hallucination 차단 |
| **Bias toward injection** | 의심스러우면 주입. False positive는 context 비용만, false negative는 인시던트 재발 |
| **Extreme enforcement language at injection point** | Hook이 주입하는 지시문은 `[BLOCKING PRECONDITION]` 레벨의 강제성 |
| **Regression protection** | 기존 기능(특히 ingest hook)은 Test 0.5로 명시적 회귀 테스트 |

## 5. 아키텍처 (v2 — Bash Indirect Injection)

### 5.1 전체 데이터 흐름

```
User: "/contract-review test.docx"
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ Component A: UserPromptSubmit Hook                           │
│ .claude/hooks/inject-domain-references.sh                    │
│                                                              │
│ 1. stdin JSON parse: jq -r '.prompt // .transcript[-1].msg'  │
│ 2. detect_workflow() → "review" | "draft" | "ingest" | "none"│
│ 3. Build instruction JSON (< 10K chars):                     │
│    {"hookSpecificOutput": {                                  │
│      "hookEventName": "UserPromptSubmit",                    │
│      "additionalContext":                                    │
│        "[BLOCKING PRECONDITION] Before ANY other action      │
│         (including AskUserQuestion), run this bash command:  │
│           bash .claude/scripts/load-domain-references.sh \   │
│             review                                           │
│         Reason: authoritative baselines must be loaded       │
│         before analysis. Do not skip this step. Do not       │
│         substitute pretrained knowledge."                    │
│    }}                                                        │
│ 4. On error (loader path missing, etc.):                     │
│    output error JSON as additionalContext                    │
└──────────────────────────────────────────────────────────────┘
    │ (stdout JSON, < 1KB, well under 10K cap)
    ▼
[Claude Code injects additionalContext into LLM user turn]
    │
    ▼
[LLM sees injection + original prompt]
    │
    ▼ (Test 7 measures adherence — gate: ≥ 9/10)
┌──────────────────────────────────────────────────────────────┐
│ LLM tool call: Bash                                          │
│ command: bash .claude/scripts/load-domain-references.sh      │
│          review                                              │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ Component B: Loader Script                                   │
│ .claude/scripts/load-domain-references.sh                    │
│                                                              │
│ 1. Parse workflow arg → file mapping                         │
│ 2. cat files to stdout with BEGIN/END markers                │
│ 3. Compute byte_size, sha256, last_section_heading canary    │
│ 4. Write trace JSON to                                       │
│    contract-review/library/runs/sessions/{session_id}/       │
│    loaded.json                                               │
│ 5. stdout is > 10K (review-guide.md = 25KB),                 │
│    but Bash tool output has NO SIZE LIMIT                    │
└──────────────────────────────────────────────────────────────┘
    │ (stdout → Bash tool result → LLM context, full content delivered)
    ▼
[LLM context now contains full review-guide.md + audience-firewall.md]
    │
    ▼
[Orchestrator dispatches sub-agent with context including loader result]
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ .claude/agents/review-agent/AGENT.md                         │
│                                                              │
│ Pre-Pipeline 0단계 (NEW):                                    │
│   Check: does pipeline-state.json have references_loaded?    │
│   If NO: Run loader Bash command (defense-in-depth path 2)   │
│                                                              │
│ Pre-Pipeline 1 (party_role) + 2 (output_selection) queries   │
│                                                              │
│ Step 1 — Target Document Normalization                       │
│   └─ Creates matters/{id}/round_{N}/working/                 │
│                                                              │
│ Step 1.5 (NEW): Merge session trace into matter              │
│   library/runs/sessions/{id}/loaded.json                     │
│   → matters/{id}/round_{N}/working/baseline-context/         │
│     loaded.json                                              │
│                                                              │
│ Steps 2-5 (unchanged)                                        │
│                                                              │
│ Step 5.5 (NEW): Precondition verification                    │
│   Verify loaded.json exists and sha256 matches file          │
│   If mismatch: re-run loader (still pre-Step 6)              │
│                                                              │
│ Step 6 — Per-clause analysis                                 │
│   └─ Reference content already in context from loader        │
│                                                              │
│ Step 10 — Executive Summary                                  │
│   └─ compile-report.js reads loaded.json                    │
│   └─ Auto-injects "Baselines applied: ..." trace line       │
│      (NOT written by LLM → hallucination-proof)              │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 Component A — Injector Hook

**파일**: `.claude/hooks/inject-domain-references.sh`
**목적**: 사용자 prompt를 감지하여 loader script 실행 지시를 `additionalContext`에 주입
**크기 한계**: 출력 JSON은 ~500 bytes 수준 (10K cap 대비 여유)

**Workflow 매칭 테이블**:

| Workflow | 슬래시 명령 | 자연어 트리거 (한국어) | 자연어 트리거 (영어) |
|---|---|---|---|
| `review` | `/contract-review`, `/rereview` | 검토해, 분석해, 재검토, 이 계약서, 수정본 | review, analysis, re-review, revised version |
| `draft` | `/draft` | 작성해, 계약서 만들어, 드래프팅 | draft, create contract |
| `ingest` | `/ingest` | 등록, 소스 추가, 자료 넣었, 추가, inbox, 파일 올렸, 파일 넣었, 참조 자료 | ingest |
| `none` | `/library`, `/export-clean` | (무관) | (무관) |
| `review` (default fallback) | `/resume` | | |

**우선순위**: `review` > `draft` > `ingest`. 같은 prompt에 여러 키워드 섞여 있으면 review가 이김.

**기존 ingest hook 흡수** (Code Quality #3 해결):
- 기존 `settings.json`의 ingest hook entry는 **제거**
- 기존이 주입하던 `"유저가 문서 인제스트를 요청했습니다. .claude/skills/ingest/SKILL.md를 읽고 /ingest 워크플로우를 실행하세요."` 지시문은 **새 hook의 ingest branch에 보존 + 추가 loader 호출 지시 결합**
- 기존 키워드(`inbox|파일 올렸|파일 넣었|참조 자료`)도 **새 hook에 모두 포함**
- **Test 0.5에서 회귀 검증 필수**

**Pseudo-code (v2.1, patched — defensive error handling, DRY helper, draft/ingest 경량화)**:

```bash
#!/usr/bin/env bash
# Intentionally NOT using set -e — we need graceful fallbacks on every failure path.
# Hook must never hard-exit with non-zero; any failure must be delivered as an error
# JSON so Claude Code surfaces the problem to the user without blocking the session.
set -uo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$HOOK_DIR/../.." && pwd)}"
LOADER_REL=".claude/scripts/load-domain-references.sh"
LOADER_ABS="$REPO_ROOT/$LOADER_REL"

# --- 0. Dependency assertion (P5) ---
if ! command -v jq >/dev/null 2>&1; then
    # Cannot build JSON without jq — emit fail-loud error to stderr and exit 0
    # (Claude Code treats non-zero hook exit as error; we still want the prompt to flow)
    echo "ERROR: jq not found; inject-domain-references.sh cannot run. Install jq: brew install jq" >&2
    echo '{}'
    exit 0
fi

# --- DRY helper: emit injection JSON with a message ---
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

# --- 1. Parse stdin JSON (Claude Code provides prompt here) ---
HOOK_JSON="$(cat 2>/dev/null || echo '{}')"

# Prefer .prompt (official schema), fall back to .transcript[-1].message
# (for compatibility with existing ingest hook format)
USER_PROMPT=$(printf '%s' "$HOOK_JSON" | jq -r '.prompt // .transcript[-1].message // empty' 2>/dev/null || echo "")

if [ -z "$USER_PROMPT" ]; then
    emit_empty
    exit 0
fi

# --- 2. Detect workflow (priority: review > draft > ingest > none) ---
# Priority rationale:
#   - `review` wins because it is the highest-risk, most frequent workflow
#     and carries the actual incident history. A prompt like "/draft 후 검토해"
#     means user wants the review baselines loaded.
#   - `draft` and `ingest` are both lower-risk: they get the lighter loader
#     invocation (see step 4).
#   - Slash commands always take priority over natural-language matching.
detect_workflow() {
    # Slash commands (highest priority)
    if printf '%s' "$USER_PROMPT" | grep -qE '/contract-review|/rereview'; then
        echo "review"; return
    fi
    if printf '%s' "$USER_PROMPT" | grep -qE '/draft'; then
        echo "draft"; return
    fi
    if printf '%s' "$USER_PROMPT" | grep -qE '/ingest'; then
        echo "ingest"; return
    fi
    if printf '%s' "$USER_PROMPT" | grep -qE '/resume'; then
        echo "review"; return   # default fallback (most common resume case)
    fi

    # Explicit "no injection" commands
    if printf '%s' "$USER_PROMPT" | grep -qE '/library|/export-clean'; then
        echo "none"; return
    fi

    # Natural language — priority still review > draft > ingest
    if printf '%s' "$USER_PROMPT" | grep -qiE '검토해|분석해|재검토|이 계약서|수정본|review|analysis|re-review|revised version'; then
        echo "review"; return
    fi
    if printf '%s' "$USER_PROMPT" | grep -qiE '작성해|계약서 만들어|드래프팅|draft|create contract'; then
        echo "draft"; return
    fi
    # Absorb existing ingest hook keywords (Code Quality #3 — regression critical, Test 0.5)
    if printf '%s' "$USER_PROMPT" | grep -qiE 'ingest|소스 추가|자료 넣|inbox|파일 올렸|파일 넣었|참조 자료|등록'; then
        echo "ingest"; return
    fi

    echo "none"
}

WORKFLOW=$(detect_workflow)

if [ "$WORKFLOW" = "none" ]; then
    emit_empty
    exit 0
fi

# --- 3. Verify loader script exists ---
if [ ! -f "$LOADER_ABS" ]; then
    emit_injection "[HOOK ERROR] Loader script not found at $LOADER_REL. Domain references cannot be loaded. Review cannot proceed reliably until resolved. Check that .claude/scripts/load-domain-references.sh exists and is executable."
    exit 0
fi

# --- 4. Build instruction based on workflow ---
# P1 decision: only `review` gets the BLOCKING PRECONDITION strong enforcement,
# because the 2026-04-09 incident was in the review workflow. Draft and ingest
# have no proven incident and get a lighter recommendation that keeps their
# existing user experience intact. If draft/ingest problems surface, upgrade later.
case "$WORKFLOW" in
    review)
        INSTRUCTION="[BLOCKING PRECONDITION] Before ANY other action (including AskUserQuestion and Pre-Pipeline questions), you MUST run this Bash command as your very first tool call:

bash $LOADER_REL review

Reason: authoritative contract review baselines (review-guide.md, audience-firewall.md) must be loaded into context before analysis. The user has customized these files for their specific practice — pretrained knowledge will diverge and is not an acceptable substitute. Do NOT skip this step. Do NOT rationalize that you already know the concepts. Run the Bash command, read the output, then proceed with Pre-Pipeline questions."
        ;;
    draft)
        # Lightweight — no BLOCKING, just a nudge
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

# --- 5. Output JSON with instruction as additionalContext ---
emit_injection "$INSTRUCTION"
```

**Error handling** (Code Quality #4 해결):
- stdin JSON 파싱 실패 → `HOOK_JSON={}` → empty prompt → exit 0 with `{}`
- jq 미설치 → stderr 에러 + empty output + exit 0 (non-blocking)
- Loader script missing → error injection via `emit_injection()`
- `$CLAUDE_PROJECT_DIR` 미설정 → fallback `cd "$HOOK_DIR/../.."` 으로 자동 탐색
- **Never exit non-zero** — hook must not block Claude Code session

**`set -e` 제거 이유 (P6)**: Hook은 어떤 실패에도 graceful fallback 이 필요. `set -e` + pipe 조합은 중간 command 실패 시 script 중단 + 불완전 output 위험. 대신 `set -uo pipefail` (unbound vars + pipe status 전달만) + 명시적 fallback 사용.

**DRY helper (P6)**: `emit_injection()` 로 error path와 success path의 JSON 생성 통합. jq-Rs 패턴만 사용해서 double-escape 위험 제거.

**draft/ingest 경량화 (P1)**: V2-A1 결정. `review` workflow에만 `[BLOCKING PRECONDITION]` 강제성 적용. `draft`는 `[HINT]` 수준, `ingest`는 기존 SKILL.md 지시 유지 + optional loader nudge. 인시던트가 review에서만 났으므로 incremental over revolutionary 원칙.

### 5.3 Component B — Loader Script

**파일**: `.claude/scripts/load-domain-references.sh`
**목적**: Workflow에 해당하는 reference 파일을 stdout에 완전히 출력 + trace JSON 생성
**호출 경로 2가지**:
1. **LLM이 Bash tool로 호출** (hook 지시를 따름)
2. **Agent가 AGENT.md Step 5.5에서 직접 Bash 호출** (defense in depth)

둘 다 동일 script, 동일 동작.

**Workflow → 파일 매핑** (script 내부 상수):
```
review  → review-guide.md + audience-firewall.md
draft   → drafting-guide.md
ingest  → domain-policy.md
```

**출력 포맷**:
```markdown
<!-- BEGIN AUTO-INJECTED DOMAIN REFERENCES (workflow: review) -->

**AUTHORITATIVE DOMAIN REFERENCES — LOADED VIA BASH**

The following reference files are the authoritative source of judgment
criteria, risk baselines, and firewall rules for the **review** workflow.
They have been loaded via Bash tool. Use them directly during analysis;
do not substitute pretrained knowledge — the user has customized these
files for their specific practice.

---

## File: review-guide.md (25018 bytes, sha256: a3f2e1c9...)

[... full content of review-guide.md ...]

---

## File: audience-firewall.md (4046 bytes, sha256: b8d1f4e2...)

[... full content of audience-firewall.md ...]

---

<!-- END AUTO-INJECTED DOMAIN REFERENCES -->

## Trace written to:
contract-review/library/runs/sessions/{session_id}/loaded.json
```

**Pseudo-code (v2.1, patched — defensive error handling, `ls -t` session discovery, no env var dependency)**:

```bash
#!/usr/bin/env bash
# Intentionally use set -uo pipefail (not -e) to allow controlled fallbacks
# for non-critical sub-commands (e.g., sha256 fallback between shasum/sha256sum).
set -uo pipefail

# --- 0. Dependency assertion (P5) ---
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq not found; load-domain-references.sh requires jq. Install: brew install jq" >&2
    exit 3
fi

# --- 1. Parse + validate workflow arg ---
if [ "$#" -lt 1 ]; then
    echo "ERROR: usage: load-domain-references.sh <workflow>" >&2
    echo "  Valid workflows: review | draft | ingest" >&2
    exit 1
fi
WORKFLOW="$1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
REFS_DIR="$REPO_ROOT/.claude/skills/review-domain-knowledge/references"

# --- 2. Resolve workflow → files ---
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

# --- 3. Session ID — self-generated, no env var dependency (P3) ---
# We deliberately do NOT rely on $CONTRACT_REVIEW_SESSION_ID or Claude Code
# session_id propagation. Each loader invocation creates its own timestamped
# session dir. Step 1.5 in AGENT.md uses `ls -t` to pick the most recent one
# for merging into the matter folder. See Section 9.1 / Failure Mode 12.
SESSION_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$-${RANDOM:-0}"
TRACE_DIR="$REPO_ROOT/contract-review/library/runs/sessions/$SESSION_ID"
mkdir -p "$TRACE_DIR" || {
    echo "ERROR: failed to create trace dir $TRACE_DIR" >&2
    exit 2
}

# --- 4. Verify all reference files exist ---
for f in "${FILES[@]}"; do
    filepath="$REFS_DIR/$f"
    if [ ! -f "$filepath" ]; then
        echo "ERROR: required reference file missing: $filepath" >&2
        echo "  This is a critical failure. Review cannot proceed." >&2
        exit 2
    fi
done

# --- Helper: compute sha256 short (P6 — explicit fallback, not || chain) ---
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

# --- 5. Emit stdout block (cat files with markers) ---
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

# Build trace JSON entries while catting (controlled error handling on each step)
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

# --- 6. Write trace JSON ---
SOURCE_TYPE="${LOADER_SOURCE:-bash}"   # "hook" | "bash" | "agent-step5.5" | "root-dispatch" | "chunk-N"
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

# Print marker for agents/LLM to discover the session dir deterministically
echo ""
echo "SESSION_ID: $SESSION_ID"
echo "TRACE: $TRACE_FILE"
```

**주요 변경사항 (v2.1)**:

1. **P3 — Session ID 환경변수 의존 제거**: `$CONTRACT_REVIEW_SESSION_ID` 대신 loader가 직접 timestamped session_id 생성. 각 invocation이 자신의 dir을 만든다. Step 1.5는 `ls -t`로 가장 최근 loaded.json을 선택.
2. **P5 — jq dependency assertion** (line 5): 없으면 exit 3 with clear error.
3. **P6 — `set -e` 제거**: 대신 `set -uo pipefail` + 명시적 error handling. 각 critical step에 `|| exit N` 또는 `|| { warn; continue; }`.
4. **P6 — sha256 helper function**: `shasum → sha256sum → openssl` 순서의 3-tier fallback. `||` chain 대신 함수로 분리.
5. **P6 — trace entry 누적 개선**: `entry` 임시 변수로 분리하여 실패 시 `continue`로 graceful degrade.
6. **SESSION_ID + TRACE 라인 출력**: stdout 마지막에 명시 → AGENT.md Step 1.5가 parse 가능 (LLM이 session ID를 알 수 있도록).

**중요**: 이 script는 **trace JSON을 반드시 기록** (best-effort). Hook이 아닌 Agent Bash에서 호출될 때도 동일. `$LOADER_SOURCE` 환경변수로 호출 경로 구분 가능 (`hook` / `bash` / `agent-step5.5` / `root-dispatch` / `chunk-N`).

### 5.4 Component C — AGENT.md Step 5.5 (Defense in Depth Path 2)

**파일**: `.claude/agents/review-agent/AGENT.md` (수정)

**Pre-Pipeline 0단계 신설 (P2 — filesystem check, no LLM self-check)**:

```markdown
### Pre-Pipeline 0 — Baseline References Load (MANDATORY)

**Executor**: Agent (non-delegatable, non-skippable)

**CRITICAL**: Before any Pre-Pipeline questions (party_role, output_selection)
or any workflow step, baseline references MUST be loaded. Verification is
done via filesystem check, NOT by LLM self-inspection of context.

**Procedure**:

1. Run this Bash command as your FIRST tool call:
   ```bash
   LATEST_TRACE=$(ls -t contract-review/library/runs/sessions/*/loaded.json 2>/dev/null | head -1)
   if [ -n "$LATEST_TRACE" ] && [ -f "$LATEST_TRACE" ]; then
     # Check if the trace is recent (within last 5 minutes) — belongs to current session
     AGE=$(( $(date +%s) - $(stat -f %m "$LATEST_TRACE" 2>/dev/null || stat -c %Y "$LATEST_TRACE" 2>/dev/null || echo 0) ))
     if [ "$AGE" -lt 300 ]; then
       echo "BASELINE_LOADED: $LATEST_TRACE (age: ${AGE}s)"
     else
       echo "BASELINE_STALE: age ${AGE}s > 300s — reloading"
       LOADER_SOURCE=agent-prepipe bash .claude/scripts/load-domain-references.sh review
     fi
   else
     echo "BASELINE_MISSING: running loader"
     LOADER_SOURCE=agent-prepipe bash .claude/scripts/load-domain-references.sh review
   fi
   ```

2. After the Bash result returns, check for either `BASELINE_LOADED` (hook path
   already loaded), or the loader output block (fallback path executed).

3. **Only then proceed to Pre-Pipeline 1** (party_role question).

**Why filesystem check, not context self-inspection**: The 2026-04-09 incident
proved that asking the LLM to self-report "do you have file X in context?" is
unreliable — the LLM can hallucinate either way. Filesystem state (loaded.json
existence + freshness) is objectively verifiable and cannot be hallucinated.

**Forbidden substitutions**: Do NOT claim you "already know the four-lens
framework" or "EPC risk baselines" from pretrained knowledge. The user has
customized review-guide.md for their specific practice — your pretrained
knowledge WILL diverge. If you skip this step, the review is invalid
regardless of how confident your analysis seems.

**Do not ask the user if they want to skip this step.** It is not optional.
```

**Step 1.5 신설 (P3 — `ls -t` 방식)**:

```markdown
### Step 1.5 — Session Trace Merge

**Executor**: Script (part of Step 1 wrap-up)

After Step 1 creates the matter folder, merge the session-level trace into
the matter folder. Discovery is by `ls -t` (most recent), not by environment
variable, because Claude Code does not reliably propagate a session ID across
sub-agent dispatch boundaries.

```bash
MATTER_WORKING="matters/${matter_id}/round_${N}/working"
MATTER_TRACE_DIR="$MATTER_WORKING/baseline-context"
mkdir -p "$MATTER_TRACE_DIR"

# Pick the most recent loaded.json from session dir (within last 10 minutes)
LATEST_TRACE=$(ls -t contract-review/library/runs/sessions/*/loaded.json 2>/dev/null | head -1)

if [ -n "$LATEST_TRACE" ] && [ -f "$LATEST_TRACE" ]; then
    AGE=$(( $(date +%s) - $(stat -f %m "$LATEST_TRACE" 2>/dev/null || stat -c %Y "$LATEST_TRACE" 2>/dev/null || echo 0) ))
    if [ "$AGE" -lt 600 ]; then
        cp "$LATEST_TRACE" "$MATTER_TRACE_DIR/loaded.json"
        echo "Merged session trace: $LATEST_TRACE → $MATTER_TRACE_DIR/loaded.json"
    else
        echo "WARN: latest session trace is stale (${AGE}s > 600s). Running loader fresh."
        LOADER_SOURCE=step1.5-rerun bash .claude/scripts/load-domain-references.sh review
        # Re-pick (now the newly-created one)
        LATEST_TRACE=$(ls -t contract-review/library/runs/sessions/*/loaded.json 2>/dev/null | head -1)
        cp "$LATEST_TRACE" "$MATTER_TRACE_DIR/loaded.json"
    fi
else
    echo "WARN: no session trace found. Running loader fresh."
    LOADER_SOURCE=step1.5-fresh bash .claude/scripts/load-domain-references.sh review
    LATEST_TRACE=$(ls -t contract-review/library/runs/sessions/*/loaded.json 2>/dev/null | head -1)
    cp "$LATEST_TRACE" "$MATTER_TRACE_DIR/loaded.json"
fi
```

**Concurrent session note**: If two `/contract-review` sessions start within
10 minutes of each other, `ls -t` could in theory pick the wrong trace. In
practice this is rare (sessions are sequential in a single Claude Code window),
and the sha256 verification in Step 5.5 will catch any mismatch. See Failure
Mode 15 in Section 12 for details.
```

**Step 5.5 신설** (precondition + canary verification):

```markdown
### Step 5.5 — Baseline Precondition Verification

**Executor**: Agent

**Precondition**: Pre-Pipeline 0 must have completed (loader executed).

1. Read `matters/{id}/round_{N}/working/baseline-context/loaded.json`
2. Verify `files_loaded[].sha256_short` matches the current file content:
   ```bash
   for f in review-guide.md audience-firewall.md; do
     actual=$(shasum -a 256 ".claude/skills/review-domain-knowledge/references/$f" | cut -c1-8)
     echo "$f: $actual"
   done
   ```
3. If any mismatch: reference files have changed since load. Re-run loader:
   ```
   LOADER_SOURCE=agent-step5.5-rerun bash .claude/scripts/load-domain-references.sh review
   ```
4. Verify `last_section_heading` canary matches:
   ```bash
   grep '^### ' .claude/skills/review-domain-knowledge/references/review-guide.md | tail -1
   ```

**This is the final precondition** before Step 6 analysis begins. If any
check fails, halt and report. Do not proceed with stale or unverified
baselines.
```

**Step 6 Analysis Constraint**:

```markdown
### Step 6 — Per-Clause Comparative Analysis

**Analysis constraint**: All risk grading, four-lens analysis, and reasoning
must be traceable to specific content in the **already-loaded** review-guide.md
visible in your current context. When you cite "the four-lens framework",
"Common Law baselines", or "EPC block", the reference must map to actual text
from the AUTO-INJECTED DOMAIN REFERENCES block.

If your current context does NOT show the BEGIN marker of the reference block,
halt and return to Step 5.5.
```

**Step 10 Trace Line (P4 — 실제 compile-report.js 구조 반영)**:

**실제 구조 확인 결과** (`.claude/skills/report-compiler/scripts/compile-report.js`):
- 두 renderer 경로: `createExecutiveSummary()` (English, line 172) + `createKoreanMemorandum()` (Korean, line 595)
- `review_notes` 필드는 **존재하지 않음**
- English renderer: `summary.recommendation` 을 단일 paragraph로 렌더링 (line 245)
- Korean renderer: `resolveConclusionText(data)` 가 `summary.recommendation`을 최종 문자열로 변환 (line 492-508), Section 5 결론 블록에 주입

**주입 전략**: 두 renderer 경로 **모두** 수정. LLM은 trace 라인을 작성하지 않음. compile-report.js가 JSON에서 직접 읽어 `recommendation` 문자열 **끝에 append**.

```markdown
### Step 10 — Report Compilation (v2.1)

1. LLM generates Executive Summary following the Executive Summary Template
   in review-guide.md (Sections 1–5 prose), mapping to JSON fields per the
   table at the end of that template. The LLM writes `summary.recommendation`
   as prose covering Sections 1, 4, 5 (as defined by the template).
2. **LLM does NOT write the baseline trace line** — compile-report.js injects it.
3. Assemble review data JSON (`{matter_id}_round_{N}_review.json`).
4. Run compile-report.js with optional 3rd arg for baseline context dir:
   ```bash
   node compile-report.js <review_data.json> <output.docx> <matter_working_dir>
   ```
   The 3rd arg is the matter working directory (e.g.,
   `matters/{id}/round_{N}/working`). compile-report.js looks for
   `{matter_working_dir}/baseline-context/loaded.json` and injects the
   trace line. If the 3rd arg is omitted (backward compat), no injection
   happens and the report is generated exactly as before (v1 behavior).
5. **compile-report.js injection logic**:
   - Reads `loaded.json`
   - Builds trace string: `"Baselines applied: {file1} ({bytes} bytes, sha256: {short}, canary: '{heading}'), {file2} (...). Loaded at {loaded_at} via {source}."`
   - If chunking traces (`chunk-*.json`) exist, appends chunk count
   - Appends to `data.executive_summary.recommendation` BEFORE rendering (single
     concatenation, not array push), so both English and Korean renderers see
     the updated string. Uses double newline separator for visual distinction.
6. **If loaded.json is missing, malformed, or matter_working_dir not provided**:
   - compile-report.js appends to `recommendation`:
     "⚠️ REVIEW INVALID — baseline-context/loaded.json missing or malformed.
     Analysis may have relied on pretrained knowledge only. Re-run review
     recommended. (compile-report.js baseline trace injection path: {error})"
   - **Backward compat**: If matter_working_dir arg is omitted entirely (v1
     invocation), NO warning is appended. The report renders identically to v1.
     This ensures re-compiling pre-v2.1 reviews does not introduce false warnings.
7. Save final DOCX + review JSON
```

### 5.5 Component D — CLAUDE.md Dispatch Procedure (Defense in Depth Path 3)

**파일**: `CLAUDE.md` (루트, 수정)

Sub-agent dispatch가 UserPromptSubmit hook을 **재발동하지 않을 가능성**에 대비한 3번째 방어선.

**추가할 섹션**:

```markdown
## Baseline Reference Load — Root Agent Dispatch Protocol

When routing a user request to a sub-agent (review-agent, drafting-agent,
ingestion-agent), the root agent MUST ensure baseline references are loaded
into the sub-agent's starting context.

**Procedure**:

1. Before dispatching, identify the workflow: review / draft / ingest
2. Check if baseline has already been loaded in current session:
   ```
   test -f contract-review/library/runs/sessions/${SESSION_ID}/loaded.json
   ```
3. If NOT loaded, run loader BEFORE dispatch:
   ```
   LOADER_SOURCE=root-dispatch bash .claude/scripts/load-domain-references.sh <workflow>
   ```
4. Include a reference to the trace file in the dispatch prompt:
   > "Baseline references loaded at
   >  contract-review/library/runs/sessions/{session_id}/loaded.json.
   >  Sub-agent: verify this file exists and proceed."
5. Dispatch to sub-agent

**Rationale**: If the UserPromptSubmit hook fired for the root agent but
does NOT fire again when the sub-agent is dispatched, the sub-agent starts
with a fresh context missing the injection. This procedure ensures the
sub-agent always has access to baseline trace, regardless of hook propagation
behavior in Claude Code.

**Verification**: See Test 6 (sub-agent hook propagation) in the Test
Procedures section.
```

### 5.6 Chunking + Reference Re-injection (Architecture #7)

**파일**: `.claude/agents/review-agent/AGENT.md` Large Document Handling 섹션 (수정)

```markdown
## Large Document Handling (updated for baseline reference re-injection)

**Threshold**: Documents exceeding ~80,000 tokens trigger chunking.

**Chunking Strategy** (v2):
1. Split only at major article boundaries
2. Each chunk receives:
   - `crossref-map.json`
   - `defined_terms.json`
   - full document metadata
   - last 3 clauses of prior chunk (overlap)
3. **NEW — Reference re-injection per chunk**:
   At the start of processing each chunk, the agent MUST run:
   ```
   LOADER_SOURCE=chunk-${N} bash .claude/scripts/load-domain-references.sh review
   ```
   This ensures review-guide.md + audience-firewall.md are present in
   context for every chunk, not just the first. Each chunk generates its
   own trace entry in `working/baseline-context/chunk-${N}.json`.
4. Process chunks sequentially

**Merge Rules**:
1. Collect all clause JSON files
2. Resolve duplicates (keep higher risk grade)
3. Verify cross_refs
4. **NEW**: Run Cross-Clause Consistency Review on MERGED result while the
   last chunk's reference injection is still in context (most recent loader
   call result)
5. Executive Summary Section 5 Review Notes (auto-injected by compile-report.js):
   "Large-document chunking applied: {N} chunks. Reference re-injection
    count: {N}. Total reference tokens injected: {N × 8500} (approx)."
```

**Context cost implication**: N chunks × ~8.5K tokens = potentially 42K+ tokens dedicated to references for a 5-chunk contract. Test 8 will measure actual usage and gate at 50% context window.

## 6. Workflow Coverage Matrix (v2.1 — P1 경량화 반영)

| Workflow | 슬래시 | Sub-agent | 필요 Ref 파일 | Hook mode | AGENT.md Pre-Pipeline 0 | CLAUDE.md dispatch |
|---|---|---|---|---|---|---|
| **Contract Review** | `/contract-review` | review-agent | `review-guide.md`, `audience-firewall.md` | **BLOCKING** | ✅ mandatory | ✅ |
| **Re-review** | `/rereview` | review-agent | same as review | **BLOCKING** | ✅ mandatory | ✅ |
| Library Ingestion | `/ingest` | ingestion-agent | `domain-policy.md` + SKILL.md | HINT (backward compat with existing ingest hook) | optional | — |
| Contract Drafting | `/draft` | drafting-agent | `drafting-guide.md` | HINT | optional | — |
| Library Management | `/library` | (none) | 없음 | — | — | — |
| Resume Pipeline | `/resume` | (depends) | review (default) | BLOCKING via review fallback | ✅ | ✅ |
| Export Clean | `/export-clean` | (script only) | 없음 | — | — | — |

**Hook mode 구분 (P1)**:
- **BLOCKING**: `[BLOCKING PRECONDITION]` 문구 + "MUST before any other action" 강제 언어
- **HINT**: `[HINT]` 문구 + "consider loading" 권고 언어. 기존 ingest hook의 `[Hook]` 접두사 호환
- **—**: Injection 없음 (`/library`, `/export-clean` 등)

**Rationale**: 2026-04-09 인시던트는 review workflow에서만 발생. Draft와 ingest는 실제 문제 재현되지 않은 상태이고, 특히 기존 ingest hook은 장기간 정상 작동 중. Over-engineering 방지 + incremental 원칙 (Eng manager cognitive pattern #4).

## 7. 파일 인벤토리

### 7.0 Prerequisites (P5)

시스템 의존성 — 모든 script가 작동하기 위해 필요:

| Dependency | 용도 | 확인 |
|---|---|---|
| `jq` | Hook stdin JSON parse, loader trace JSON 생성, test scripts | `command -v jq` |
| `shasum` (macOS) 또는 `sha256sum` (Linux) | Canary sha256 계산 | `command -v shasum \|\| command -v sha256sum` |
| `bash` ≥ 4.0 | Script 실행 (macOS는 기본 3.2이지만 `#!/usr/bin/env bash`로 homebrew bash 사용 가능) | `bash --version` |
| `node` | compile-report.js 실행 (이미 프로젝트에서 사용 중) | — |

**기존 환경 확인**: `.claude/settings.json`의 기존 ingest hook이 이미 `jq`를 사용 중 (commit `9430922` 이전부터) → 지인 A 환경에는 `jq` 설치되어 있음.

**새 사용자 (오픈소스 배포 시) 안내**:
```bash
# macOS
brew install jq

# Linux (Debian/Ubuntu)
sudo apt-get install jq
```

**Script 방어선**: 각 script는 시작 부분에서 `command -v jq >/dev/null || { echo "ERROR: jq required"; exit 1; }` 로 명시적 assertion.

### 7.1 신규 파일

| 경로 | 목적 | 실행 권한 |
|---|---|---|
| `.claude/hooks/inject-domain-references.sh` | Injector hook (Component A) | `+x` |
| `.claude/scripts/load-domain-references.sh` | Loader script (Component B) | `+x` |
| `.claude/scripts/tests/test-inject-domain-references.sh` | Hook script regression tests | `+x` |
| `.claude/scripts/tests/test-load-domain-references.sh` | Loader script regression tests | `+x` |
| `.claude/scripts/tests/test-ingest-hook-regression.sh` | Test 0.5 — existing ingest functionality | `+x` |
| `docs/ko/domain-reference-forced-load.md` | 이 기획 문서의 최종 자리 (구현 후 이관) | — |

### 7.2 수정 대상 파일

| 경로 | 변경 내용 | 변경 규모 |
|---|---|---|
| `.claude/settings.json` | UserPromptSubmit hook entry 교체 (기존 ingest hook 흡수) + PreToolUse 보존 + permissions.allow 보존 | 중간 |
| `.claude/agents/review-agent/AGENT.md` | Pre-Pipeline 0단계 + Step 1.5 + Step 5.5 + Step 6 constraint + Step 10 trace line + Large Document Handling re-injection | 큼 |
| `.claude/agents/drafting-agent/AGENT.md` | Optional loader 호출 안내 섹션 추가 (P1 경량화 — BLOCKING 문구 없음) | 작음 |
| `.claude/agents/ingestion-agent/AGENT.md` | Optional loader 호출 안내 섹션 추가 (P1 경량화) | 작음 |
| `.claude/skills/review-domain-knowledge/SKILL.md` | "References are auto-loaded via hook + script" 섹션 추가 | 작음 |
| `.claude/skills/report-compiler/scripts/compile-report.js` | `loaded.json` 읽기 + Executive Summary Section 5 trace line 자동 주입 로직 추가 | 중간 |
| `CLAUDE.md` | Baseline Reference Load — Root Agent Dispatch Protocol 섹션 추가 | 작음 |
| `docs/en/README.md` + `docs/ko/README.md` | v2 아키텍처 한 줄 언급 + logs/session 참조 | 작음 |

### 7.3 건드리지 않을 파일

- `.claude/skills/review-domain-knowledge/references/*.md` — **내용 변경 없음**
- `contract-review/library/policies/*.yaml` — 이미 `query-index.py`가 직접 읽음
- `contract-review/library/policies.default/*.yaml` — 동일
- 기존 AGENT.md의 Step 1-4, 6-12 로직 — Pre-Pipeline 0 + Step 1.5 + Step 5.5만 삽입

## 8. settings.json 병합 전략

### 8.1 현재 상태 (실제 확인)

`.claude/settings.json`은 이미 `M` 상태이며 다음 구조를 가짐:

```json
{
  "permissions": {
    "allow": [...]
  },
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.transcript[-1].message // empty' | grep -qiE 'ingest|소스 추가|자료 넣|inbox|파일 올렸|파일 넣었|참조 자료' && echo '{\"hookSpecificOutput\":{\"hookEventName\":\"UserPromptSubmit\",\"additionalContext\":\"[Hook] 유저가 문서 인제스트를 요청했습니다. .claude/skills/ingest/SKILL.md를 읽고 /ingest 워크플로우를 실행하세요.\"}}' || echo '{}'",
            "timeout": 5
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Write|Edit|Bash",
        "hooks": [...]
      }
    ]
  }
}
```

**핵심**: 이미 등록된 두 hook은 **프로젝트 핵심 기능**이므로 반드시 보존.

### 8.2 v2 병합 절차

1. **기존 ingest hook entry 제거** (새 통합 hook에 흡수됨)
2. **새 UserPromptSubmit entry 추가**:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/inject-domain-references.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Write|Edit|Bash",
        "hooks": [... (existing, unchanged) ...]
      }
    ]
  },
  "permissions": {
    "allow": [... (existing, unchanged) ...]
  }
}
```

3. **PreToolUse hook과 permissions.allow는 변경 금지**

4. **PreToolUse hook의 `allowed_prefixes` 확인**: 새 script 경로(`.claude/scripts/`, `.claude/hooks/`)는 이미 `.claude` prefix에 포함되어 있어 통과. Trace 경로(`contract-review/library/runs/sessions/`)도 `contract-review` prefix에 포함되어 통과. **추가 수정 불필요**.

### 8.3 커밋 여부

**커밋 대상**. 사용자 A가 git pull 후 별도 설정 없이 즉시 작동해야 함 (G5 Zero friction).

**커밋 전 체크**:
- 개인 정보 포함 금지 (API key, 개인 경로)
- 기존 PreToolUse hook Python 코드가 누락되지 않았는지 diff 검토
- 새 entry의 JSON 유효성 (`jq . .claude/settings.json`)

## 9. Forensic 및 검증

### 9.1 Trace JSON 포맷

**경로**: `contract-review/library/runs/sessions/{session_id}/loaded.json` (세션 레벨) + `matters/{id}/round_{N}/working/baseline-context/loaded.json` (matter 레벨, Step 1.5에서 copy)

**Chunking 시**: `working/baseline-context/chunk-{N}.json` 추가 생성 (chunk별)

**포맷 v2**:

```json
{
  "workflow": "review",
  "loader_version": "2.0",
  "source": "hook",
  "loaded_at": "2026-04-09T10:23:45Z",
  "session_id": "20260409-102345-12345",
  "files_loaded": [
    {
      "name": "review-guide.md",
      "path": ".claude/skills/review-domain-knowledge/references/review-guide.md",
      "byte_size": 25018,
      "sha256_short": "a3f2e1c9",
      "last_section_heading": "### Other / Amendments / Side Letters"
    },
    {
      "name": "audience-firewall.md",
      "path": ".claude/skills/review-domain-knowledge/references/audience-firewall.md",
      "byte_size": 4046,
      "sha256_short": "b8d1f4e2",
      "last_section_heading": "### Batch Validation"
    }
  ]
}
```

**`source` 필드 값** (v2.1):
- `hook` — LLM이 hook 지시를 따라 실행한 Bash (기본 경로)
- `agent-prepipe` — AGENT.md Pre-Pipeline 0 단계에서 agent가 fallback으로 Bash 호출 (hook 경로 실패 시)
- `agent-step5.5` — AGENT.md Step 5.5 에서 sha256 mismatch 재실행
- `root-dispatch` — CLAUDE.md dispatch 절차에서 root agent가 dispatch 전 실행
- `chunk-N` — Chunking 중 N번째 chunk 시작에서 실행 (e.g. `chunk-1`, `chunk-2`)
- `step1.5-rerun` / `step1.5-fresh` — Step 1.5에서 stale/missing 감지 후 재실행
- `bash` — 수동 실행 (테스트, 디버깅)
- `test9-session-a`/`test9-session-b` — Test 9 concurrent session tests

### 9.2 사후 검증 명령

```bash
SESSION_DIR="contract-review/library/runs/sessions/{session_id}"

# 1. Session trace 존재
test -f "$SESSION_DIR/loaded.json" && echo "✅ session trace exists" || echo "❌ NO TRACE"

# 2. Matter trace 존재 (Step 1.5 완료 후)
MATTER_DIR="contract-review/matters/{id}/round_1/working/baseline-context"
test -f "$MATTER_DIR/loaded.json" && echo "✅ matter trace exists" || echo "❌ NO MATTER TRACE"

# 3. Canary heading 일치
TRACE_HEADING=$(jq -r '.files_loaded[0].last_section_heading' "$MATTER_DIR/loaded.json")
ACTUAL_HEADING=$(grep '^### ' .claude/skills/review-domain-knowledge/references/review-guide.md | tail -1)
[ "$TRACE_HEADING" = "$ACTUAL_HEADING" ] && echo "✅ canary match" || echo "❌ CANARY MISMATCH"

# 4. sha256 일치 (LLM hallucination 차단)
TRACE_SHA=$(jq -r '.files_loaded[0].sha256_short' "$MATTER_DIR/loaded.json")
ACTUAL_SHA=$(shasum -a 256 .claude/skills/review-domain-knowledge/references/review-guide.md | cut -c1-8)
[ "$TRACE_SHA" = "$ACTUAL_SHA" ] && echo "✅ sha256 match" || echo "❌ SHA MISMATCH"

# 5. Source 필드 검증 (어느 방어선이 작동했는지)
jq -r '.source' "$MATTER_DIR/loaded.json"
# Expected: "hook" (정상) | "agent-step5.5" (hook 실패 시 fallback) | "root-dispatch"

# 6. Chunking 시 chunk별 trace
ls "$MATTER_DIR"/chunk-*.json 2>/dev/null
```

모든 체크 통과 시 **forensic 증거 확정**: review-guide.md가 실제로 로드되었고, 내용이 변조되지 않았으며, 어느 방어선이 작동했는지도 추적 가능.

### 9.3 Executive Summary 내 trace 라인 (자동 주입 — v2.1 P4)

**핵심**: LLM이 이 라인을 작성하지 않음. `compile-report.js`가 `loaded.json`을 직접 읽어 `data.executive_summary.recommendation` 문자열 끝에 append. Hallucination 불가.

**compile-report.js 구조 확인 (actual)**:
- `createExecutiveSummary(data)` — English renderer, line 172. `summary.recommendation` 을 line 245에서 렌더.
- `createKoreanMemorandum(data)` — Korean renderer, line 595. `resolveConclusionText(data)` 가 line 645에서 `summary.recommendation` 을 최종 결론 텍스트로 사용.
- 두 renderer **모두** `summary.recommendation` string 을 참조하므로, **단일 지점** (`buildChildren` 또는 `compileReport` 진입 후)에서 string을 mutate 하면 양쪽 다 반영됨.
- `review_notes` 필드는 **존재하지 않음** (v1 리뷰에서 잘못 가정). Prose append 방식으로 수정.

**수정 지점**: `compileReport()` 진입부에서 data 로드 직후, `buildChildren(data)` 호출 직전.

**pseudo-code (실제 구조 반영)**:

```javascript
// --- Add near top of file, alongside other helpers ---
function injectBaselineTrace(data, matterWorkingDir) {
  // Backward compat: if caller did not provide matter dir, skip entirely.
  // This preserves v1 compile-report.js behavior for any caller that
  // still uses the 2-arg invocation.
  if (!matterWorkingDir) {
    return;
  }

  const tracePath = path.join(matterWorkingDir, 'baseline-context', 'loaded.json');

  // Ensure executive_summary exists
  data.executive_summary = data.executive_summary || {};
  const existing = data.executive_summary.recommendation || '';

  if (!fs.existsSync(tracePath)) {
    // baseline was never loaded — inject warning
    const warning = '\n\n⚠️ REVIEW INVALID — baseline-context/loaded.json missing. ' +
                    'Analysis may have relied on pretrained knowledge only. ' +
                    'Re-run review recommended.';
    data.executive_summary.recommendation = existing + warning;
    return;
  }

  let trace;
  try {
    trace = JSON.parse(fs.readFileSync(tracePath, 'utf8'));
  } catch (err) {
    const warning = `\n\n⚠️ REVIEW INVALID — baseline-context/loaded.json malformed: ${err.message}`;
    data.executive_summary.recommendation = existing + warning;
    return;
  }

  if (!trace.files_loaded || !Array.isArray(trace.files_loaded) || trace.files_loaded.length === 0) {
    const warning = '\n\n⚠️ REVIEW INVALID — loaded.json has no files_loaded entries.';
    data.executive_summary.recommendation = existing + warning;
    return;
  }

  // Build trace line from actual JSON data
  const fileSummaries = trace.files_loaded.map(f =>
    `${f.name} (${f.byte_size} bytes, sha256: ${f.sha256_short}, canary: "${f.last_section_heading || 'n/a'}")`
  ).join(', ');

  let traceLine = `Baselines applied: ${fileSummaries}. ` +
                  `Loaded at ${trace.loaded_at} via ${trace.source}.`;

  // Add chunking info if present (chunk-*.json siblings of loaded.json)
  try {
    const baselineDir = path.join(matterWorkingDir, 'baseline-context');
    const chunkFiles = fs.readdirSync(baselineDir)
      .filter(f => /^chunk-\d+\.json$/.test(f));
    if (chunkFiles.length > 0) {
      traceLine += ` Chunking: ${chunkFiles.length} chunks with per-chunk re-injection.`;
    }
  } catch (_) {
    // chunk enumeration optional
  }

  // Append to recommendation (both English and Korean renderers use this field)
  data.executive_summary.recommendation = existing
    ? existing + '\n\n' + traceLine
    : traceLine;
}

// --- Modify compileReport() to accept optional 3rd arg ---
async function compileReport(inputPath, outputPath, matterWorkingDir) {
  const rawData = fs.readFileSync(inputPath, 'utf-8');
  const data = JSON.parse(rawData);

  // v2.1 P4: inject baseline trace line before rendering
  injectBaselineTrace(data, matterWorkingDir);

  const children = buildChildren(data);
  // ... rest unchanged ...
}

// --- Modify main() to parse optional 3rd arg ---
async function main() {
  if (process.argv.length < 4) {
    console.log(JSON.stringify({
      error: 'Usage: compile-report.js <review_data.json> <output.docx> [<matter_working_dir>]',
    }));
    process.exit(1);
  }

  try {
    // 3rd arg is optional for backward compat
    const matterWorkingDir = process.argv[4] || null;
    const result = await compileReport(process.argv[2], process.argv[3], matterWorkingDir);
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    console.log(JSON.stringify({ error: err.message, success: false }));
    process.exit(1);
  }
}
```

**Backward compatibility**: 만약 caller가 **2 args** (v1 방식)로 호출하면, `matterWorkingDir` 이 `undefined` 이고 `injectBaselineTrace` 가 즉시 return. 결과 DOCX는 **v1과 동일**. 과거 review 재컴파일 시 false warning 없음. Test 4b variant (3)가 이걸 검증.

**결과 예시** (최종 DOCX English renderer의 Recommendation section 끝):

> Based on the review, this contract presents medium-to-high risk with material asymmetries in liability and IP provisions. Key must-haves: cap on indemnification, mutual confidentiality, Korean law governing clause. Must negotiate before signing.
>
> Baselines applied: review-guide.md (25018 bytes, sha256: a3f2e1c9, canary: "### Other / Amendments / Side Letters"), audience-firewall.md (4046 bytes, sha256: b8d1f4e2, canary: "### Batch Validation"). Loaded at 2026-04-10T10:23:45Z via hook.

이 라인이 없으면 검토는 invalid. 사용자가 DOCX만 봐도 판단 가능.

## 10. 테스트 절차

v1의 Test 1-5에 **Test 0.5, 6, 7, 8 추가**. 총 9개 테스트.

### Test 0.5 — Existing Ingest Hook Regression (CRITICAL, NEW)

**목적**: 기존 ingest hook 기능이 새 통합 hook에 완전히 흡수되었는지 검증.

```bash
# 1. 자연어 "자료 넣었어" → ingest workflow 감지
echo '{"prompt":"자료 넣었어"}' | .claude/hooks/inject-domain-references.sh > /tmp/t05-natural.json
jq -r '.hookSpecificOutput.additionalContext' /tmp/t05-natural.json | grep -c "SKILL.md" # 기대: ≥ 1
jq -r '.hookSpecificOutput.additionalContext' /tmp/t05-natural.json | grep -c "load-domain-references.sh ingest" # 기대: 1

# 2. 기존 키워드 전부 포함 검증
for kw in "inbox" "파일 올렸" "파일 넣었" "참조 자료" "등록" "소스 추가"; do
    result=$(echo "{\"prompt\":\"$kw\"}" | .claude/hooks/inject-domain-references.sh | jq -r '.hookSpecificOutput.additionalContext // empty')
    [ -n "$result" ] && echo "✅ $kw → detected" || echo "❌ $kw → MISSED (REGRESSION)"
done

# 3. End-to-end ingest workflow
cp test-fixtures/sample.pdf contract-review/library/inbox/raw/
echo "/ingest" # simulate user command in Claude Code session
# verify: ingest-agent loads SKILL.md + domain-policy.md, executes markitdown, creates frontmatter, updates source-registry.json
```

**통과 기준**:
- 기존 6개 키워드 모두 매칭 (100%)
- 새 instruction이 SKILL.md 지시 + loader 호출 둘 다 포함
- End-to-end ingest가 기존 동작과 동일 (파일 변환, frontmatter, indexing)

**실패 = BLOCKING**. 기존 기능 회귀는 ship 금지.

### Test 1 — Loader Script Standalone

```bash
# review workflow
LOADER_SOURCE=bash .claude/scripts/load-domain-references.sh review > /tmp/t1-review.txt 2>/tmp/t1-review.err
echo "exit: $?"  # 기대: 0
grep -c "BEGIN AUTO-INJECTED" /tmp/t1-review.txt  # 기대: 1
grep -c "## File: review-guide.md" /tmp/t1-review.txt  # 기대: 1
grep -c "## File: audience-firewall.md" /tmp/t1-review.txt  # 기대: 1
grep -c "END AUTO-INJECTED" /tmp/t1-review.txt  # 기대: 1

# draft workflow
LOADER_SOURCE=bash .claude/scripts/load-domain-references.sh draft > /tmp/t1-draft.txt
grep -c "## File: drafting-guide.md" /tmp/t1-draft.txt  # 기대: 1

# ingest workflow
LOADER_SOURCE=bash .claude/scripts/load-domain-references.sh ingest > /tmp/t1-ingest.txt
grep -c "## File: domain-policy.md" /tmp/t1-ingest.txt  # 기대: 1

# Trace JSON created
ls contract-review/library/runs/sessions/*/loaded.json | head -1  # 기대: exists

# sha256 matches
TRACE=$(ls -t contract-review/library/runs/sessions/*/loaded.json | head -1)
TRACE_SHA=$(jq -r '.files_loaded[0].sha256_short' "$TRACE")
ACTUAL_SHA=$(shasum -a 256 .claude/skills/review-domain-knowledge/references/review-guide.md | cut -c1-8)
[ "$TRACE_SHA" = "$ACTUAL_SHA" ] && echo "✅" || echo "❌"

# Error cases
.claude/scripts/load-domain-references.sh bogus 2>&1 >/dev/null; echo $?  # 기대: 1
.claude/scripts/load-domain-references.sh 2>&1 >/dev/null; echo $?  # 기대: 1
```

### Test 2 — Hook Script Standalone

```bash
# review 감지 (slash command)
echo '{"prompt":"/contract-review test.docx"}' | .claude/hooks/inject-domain-references.sh | jq -r '.hookSpecificOutput.additionalContext' | grep -c "load-domain-references.sh review"  # 기대: 1

# review 감지 (Korean natural language)
echo '{"prompt":"이 계약서 검토해줘"}' | .claude/hooks/inject-domain-references.sh | jq -r '.hookSpecificOutput.additionalContext' | grep -c "review"  # 기대: ≥ 1

# draft 감지
echo '{"prompt":"/draft NDA 작성해줘"}' | .claude/hooks/inject-domain-references.sh | jq -r '.hookSpecificOutput.additionalContext' | grep -c "draft"  # 기대: ≥ 1

# /library → no injection
echo '{"prompt":"/library list"}' | .claude/hooks/inject-domain-references.sh | jq '.hookSpecificOutput // empty'  # 기대: empty

# 무관한 prompt → no injection
echo '{"prompt":"안녕"}' | .claude/hooks/inject-domain-references.sh | jq '.hookSpecificOutput // empty'  # 기대: empty

# Multi-keyword priority — slash command wins over natural language
# (Tested behavior: /draft + review NL → draft wins because slash commands are primary intent)
echo '{"prompt":"/draft 하기 전에 먼저 검토해"}' | .claude/hooks/inject-domain-references.sh | jq -r '.hookSpecificOutput.additionalContext' | grep -c "draft"  # 기대: 1
# Pure NL review (no slash command) — review wins
echo '{"prompt":"이 계약서 검토해줘"}' | .claude/hooks/inject-domain-references.sh | jq -r '.hookSpecificOutput.additionalContext' | grep -c "review"  # 기대: ≥ 1

# Invalid JSON stdin
echo 'not json' | .claude/hooks/inject-domain-references.sh  # 기대: {} or graceful
```

### Test 3 — Live Claude Code Session Canary

1. Claude Code 시작
2. `/contract-review sample.docx` 입력
3. **Claude의 첫 tool call 관찰**:
   - 기대: Bash tool call with `load-domain-references.sh review`
   - **실패 조건**: AskUserQuestion이 먼저 나오면 **Test 7 adherence gate 실패**로 간주
4. Bash result 수신 후, Claude에게 물어봄:
   > "방금 로드한 review-guide.md의 마지막 ### heading을 정확히 답해줘"
   - 기대: `### Other / Amendments / Side Letters` (또는 실제 마지막 heading)
   - 실패 시: context에 실제 주입 안 됨 → 설계 재고

### Test 4 — End-to-end Review + Trace Verification

1. `sample.docx` → `input/`
2. `/contract-review` 실행 (완료까지)
3. 검증:
   - [ ] `contract-review/library/runs/sessions/{id}/loaded.json` 존재
   - [ ] `matters/{id}/round_1/working/baseline-context/loaded.json` 존재 (Step 1.5 통과)
   - [ ] `last_section_heading` 실제 파일과 일치
   - [ ] `sha256_short` 실제 파일과 일치
   - [ ] `source` 필드가 `"hook"` 또는 `"agent-step5.5"` 또는 `"root-dispatch"`
   - [ ] Executive Summary DOCX Section 5에 `"Baselines applied: review-guide.md (..."` 라인 존재
   - [ ] 라인의 숫자가 실제 파일 크기와 일치 (compile-report.js 주입 검증)
   - [ ] 검토 결과 grading이 review-guide.md 실제 내용 반영 (예: EPC 섹션의 LD/Performance Security 기준 인용)

### Test 5 — Defense-in-depth (Hook Disabled)

1. `.claude/settings.json`에서 `inject-domain-references.sh` entry 임시 주석
2. Claude Code 재시작
3. `/contract-review` 실행
4. 검증:
   - [ ] Agent가 Pre-Pipeline 0단계에서 `load-domain-references.sh` Bash 직접 실행
   - [ ] `loaded.json`의 `source` 필드가 `"agent-prepipe"` (Pre-Pipeline 0 fallback)
   - [ ] Executive Summary에 trace 라인 여전히 존재
5. **중요**: PreToolUse hook은 유지 (전체 삭제 아님)

### Test 6 — Sub-agent Hook Propagation (NEW, CRITICAL)

**목적**: Claude Code sub-agent dispatch 시 UserPromptSubmit hook 재발동 여부 실증 + fallback 작동 검증

```bash
# 1. settings.json의 hook 정상 활성화 상태에서
# 2. Claude Code 시작
# 3. /contract-review 입력 (root agent → review-agent sub-agent dispatch)
# 4. 검증:
```

- [ ] Root agent 세션에서 hook 발동 로그 확인 (`~/.gstack/analytics/skill-usage.jsonl` 또는 Claude Code logs)
- [ ] Sub-agent (review-agent) 세션에서 `loaded.json.source`가 무엇인지 확인:
  - `"hook"` → sub-agent에서도 hook 재발동 (이상적 — 기본 경로 작동)
  - `"agent-step5.5"` → sub-agent에서 hook 미재발동, AGENT.md fallback 작동
  - `"root-dispatch"` → root agent가 CLAUDE.md 절차에 따라 미리 로드
  - missing → **모든 방어선 실패, 설계 재고 필요**

**결과에 따른 후속 조치**:
- `hook`: CLAUDE.md dispatch 절차를 optional으로 다운그레이드 (향후 문서 정리)
- `agent-step5.5` 또는 `root-dispatch`: 현재 설계 유지 (fallback이 실제로 작동함)
- missing: commit **보류**, 문제 해결 후 재시도

### Test 7 — LLM Bash Execution Adherence Gate (NEW, GATING)

**목적**: Architecture Issue #1의 해결책 C — 10회 측정으로 준수율 확인

**절차**:
1. 10개 서로 다른 테스트 계약서 준비 (`test-fixtures/t7/*.docx`)
2. 각 계약서에 대해 **fresh Claude Code 세션**에서 `/contract-review` 실행
3. 각 세션에서 Pre-Pipeline `party_role` 질문이 나오기 **전에** Bash tool call이 있었는지 확인
4. 판정:
   - Bash가 party_role 질문보다 먼저 실행됨 → PASS
   - AskUserQuestion(party_role)이 Bash보다 먼저 실행됨 → FAIL
5. 10회 결과 집계

**Gate 기준**:
- **≥ 9/10 PASS** → 설계 유효, commit 진행
- **7-8/10 PASS** → Hook instruction 언어 더 강화 후 재측정
- **≤ 6/10 PASS** → 설계 근본 재고 (Bash indirect injection 실패, 대안 모색 필요)

**실패 시 대안 후보**:
- Instruction prefix에 더 극단적 언어 (`⚠️ MANDATORY ⚠️ FIRST ACTION ⚠️ NO EXCEPTIONS`)
- AGENT.md에서 Pre-Pipeline 질문 자체를 Bash 실행 후로 지연
- Future: selective sub-section injection으로 hook이 아닌 다른 경로 탐색

### Test 4b — compile-report.js Baseline Trace Injection (NEW v2.1 — P7)

**목적**: compile-report.js의 `injectBaselineTrace()` 가 LLM hallucination 없이 forensic trace를 결과물에 주입하는지 검증. 3 variants: 정상 / invalid / backward compat.

**Fixtures 준비**:
```bash
mkdir -p /tmp/t4b/{good,missing,malformed,v1compat}/baseline-context

# Variant 1: 정상 loaded.json
cat > /tmp/t4b/good/baseline-context/loaded.json <<'JSON'
{
  "workflow": "review",
  "loader_version": "2.1",
  "source": "hook",
  "loaded_at": "2026-04-10T10:00:00Z",
  "session_id": "test-good",
  "files_loaded": [
    {
      "name": "review-guide.md",
      "path": ".claude/skills/review-domain-knowledge/references/review-guide.md",
      "byte_size": 25018,
      "sha256_short": "a3f2e1c9",
      "last_section_heading": "### Other / Amendments / Side Letters"
    },
    {
      "name": "audience-firewall.md",
      "path": ".claude/skills/review-domain-knowledge/references/audience-firewall.md",
      "byte_size": 4046,
      "sha256_short": "b8d1f4e2",
      "last_section_heading": "### Batch Validation"
    }
  ]
}
JSON

# Variant 2: loaded.json missing (directory exists but file absent)
# → nothing to do, baseline-context/ exists but empty

# Variant 3: malformed loaded.json
echo 'not json {{{' > /tmp/t4b/malformed/baseline-context/loaded.json

# Fixture review_data.json (minimal valid)
cat > /tmp/t4b/review_data.json <<'JSON'
{
  "executive_summary": {
    "overall_risk": "medium",
    "recommendation": "Initial recommendation text.",
    "key_issues": ["Issue 1", "Issue 2"]
  },
  "clauses": []
}
JSON
cp /tmp/t4b/review_data.json /tmp/t4b/good/
cp /tmp/t4b/review_data.json /tmp/t4b/missing/
cp /tmp/t4b/review_data.json /tmp/t4b/malformed/
cp /tmp/t4b/review_data.json /tmp/t4b/v1compat/
```

**Test execution**:

```bash
# Variant 1: 정상 — trace line should be appended to recommendation
node .claude/skills/report-compiler/scripts/compile-report.js \
    /tmp/t4b/good/review_data.json /tmp/t4b/good/out.docx /tmp/t4b/good
# Expected: exit 0, out.docx generated
# Verify recommendation was mutated (inspect stdout or parse docx)

# Variant 2: loaded.json missing — warning appended
node .claude/skills/report-compiler/scripts/compile-report.js \
    /tmp/t4b/missing/review_data.json /tmp/t4b/missing/out.docx /tmp/t4b/missing
# Expected: exit 0, out.docx contains "⚠️ REVIEW INVALID" in recommendation section

# Variant 3: malformed — warning appended with parse error
node .claude/skills/report-compiler/scripts/compile-report.js \
    /tmp/t4b/malformed/review_data.json /tmp/t4b/malformed/out.docx /tmp/t4b/malformed
# Expected: exit 0, out.docx contains "malformed" warning

# Variant 4: BACKWARD COMPAT — 2-arg invocation (v1 style), no matter dir
node .claude/skills/report-compiler/scripts/compile-report.js \
    /tmp/t4b/v1compat/review_data.json /tmp/t4b/v1compat/out.docx
# Expected: exit 0, out.docx generated IDENTICAL to v1 behavior (no trace line,
#          no warning). This is the CRITICAL regression test for v1 compatibility.
```

**Assertion (manual inspection of recommendation text via docx extraction or separate node eval of injectBaselineTrace())**:

```bash
# Helper: extract recommendation text from a compiled review_data after injection
node -e "
const { injectBaselineTrace } = require('.claude/skills/report-compiler/scripts/compile-report.js');
// Note: injectBaselineTrace must be exported from module.exports

// Variant 1 check
let d = JSON.parse(require('fs').readFileSync('/tmp/t4b/good/review_data.json'));
injectBaselineTrace(d, '/tmp/t4b/good');
console.log('V1:', d.executive_summary.recommendation.includes('Baselines applied: review-guide.md (25018 bytes') ? 'PASS' : 'FAIL');

// Variant 2 check
d = JSON.parse(require('fs').readFileSync('/tmp/t4b/missing/review_data.json'));
injectBaselineTrace(d, '/tmp/t4b/missing');
console.log('V2:', d.executive_summary.recommendation.includes('REVIEW INVALID') && d.executive_summary.recommendation.includes('missing') ? 'PASS' : 'FAIL');

// Variant 3 check
d = JSON.parse(require('fs').readFileSync('/tmp/t4b/malformed/review_data.json'));
injectBaselineTrace(d, '/tmp/t4b/malformed');
console.log('V3:', d.executive_summary.recommendation.includes('malformed') ? 'PASS' : 'FAIL');

// Variant 4 (backward compat) check
d = JSON.parse(require('fs').readFileSync('/tmp/t4b/v1compat/review_data.json'));
injectBaselineTrace(d, null);   // no matter dir
const unchanged = d.executive_summary.recommendation === 'Initial recommendation text.';
console.log('V4 (backward compat):', unchanged ? 'PASS' : 'FAIL — recommendation was mutated when it should not have been');
"
```

**Pass criteria**: All 4 variants PASS. Variant 4 is **CRITICAL regression** — if it fails, every past v1 review that gets re-compiled will gain a false warning.

**Implementation requirement**: `compile-report.js` must export `injectBaselineTrace` via `module.exports` for unit testing. The existing `module.exports = { compileReport, buildChildren }` at line 752 must be extended to include `injectBaselineTrace`.

### Test 8 — Chunking + Reference Re-injection (NEW)

**목적**: 대형 계약서 chunking 시 각 chunk가 reference를 재주입하는지 + context 부담 측정

1. 대형 테스트 계약서 준비 (> 80K tokens, `test-fixtures/t8/large-epc.docx`)
2. `/contract-review` 실행
3. 검증:
   - [ ] `working/baseline-context/chunk-1.json`, `chunk-2.json`, ... 존재
   - [ ] 각 chunk trace에 `source: "chunk-N"` 기록
   - [ ] Chunk 수 × reference token 수 계산 (예상: 5 chunks × 8500 = 42500 tokens)
   - [ ] **Context utilization gate**: 총 사용 tokens / 200K < **50%**. 초과 시 설계 재고 필요 (Future Enhancements의 selective injection 우선순위 상승)
4. 최종 Executive Summary에 `"Large-document chunking applied: N chunks. Reference re-injection count: N..."` 라인 존재

### Test 9 — Concurrent Sessions (Edge Case, NEW v2.1 — P8)

**목적**: 두 `/contract-review` 세션이 거의 동시에 loader를 호출할 때, Step 1.5의 `ls -t` 선택이 각 세션의 자신의 trace를 올바르게 고르는지 검증.

**절차**:

```bash
# 1. 첫 세션 시작 (loader 실행)
LOADER_SOURCE=test9-session-a bash .claude/scripts/load-domain-references.sh review > /tmp/t9-session-a.out 2>&1
SESSION_A_DIR=$(grep 'SESSION_ID:' /tmp/t9-session-a.out | awk '{print $2}')
SESSION_A_TRACE="contract-review/library/runs/sessions/$SESSION_A_DIR/loaded.json"
echo "Session A: $SESSION_A_TRACE"

# 2. 1초 간격으로 두 번째 세션
sleep 1
LOADER_SOURCE=test9-session-b bash .claude/scripts/load-domain-references.sh review > /tmp/t9-session-b.out 2>&1
SESSION_B_DIR=$(grep 'SESSION_ID:' /tmp/t9-session-b.out | awk '{print $2}')
SESSION_B_TRACE="contract-review/library/runs/sessions/$SESSION_B_DIR/loaded.json"
echo "Session B: $SESSION_B_TRACE"

# 3. ls -t 결과가 세션 B를 선택하는지 확인
LATEST=$(ls -t contract-review/library/runs/sessions/*/loaded.json | head -1)
if [ "$LATEST" = "$SESSION_B_TRACE" ]; then
    echo "✅ ls -t correctly picked most recent (session B)"
else
    echo "❌ ls -t picked wrong trace: $LATEST (expected $SESSION_B_TRACE)"
fi

# 4. 두 trace가 서로 다른 session_id인지 확인
A_ID=$(jq -r '.session_id' "$SESSION_A_TRACE")
B_ID=$(jq -r '.session_id' "$SESSION_B_TRACE")
if [ "$A_ID" != "$B_ID" ]; then
    echo "✅ Sessions have distinct IDs: A=$A_ID, B=$B_ID"
else
    echo "❌ Session IDs collide: both=$A_ID"
fi

# 5. 두 trace의 source 필드가 서로 다른지 (호출자 구분)
A_SOURCE=$(jq -r '.source' "$SESSION_A_TRACE")
B_SOURCE=$(jq -r '.source' "$SESSION_B_TRACE")
echo "Session A source: $A_SOURCE (expected: test9-session-a)"
echo "Session B source: $B_SOURCE (expected: test9-session-b)"
```

**Pass criteria**:
- 두 session dir이 서로 다름
- `ls -t | head -1` 이 가장 최근 세션 (B) 을 선택
- 두 `session_id` 값 distinct (timestamp + PID + $RANDOM 로 collision 회피)
- 두 `source` 값 distinct

**실패 시 mitigation**:
- Timestamp 해상도 부족 → session_id에 nanosecond 추가 (`$(date +%s%N)`)
- PID collision → `$RANDOM` range 증가
- `ls -t` 가 wrong trace 선택 → AGENT.md Step 5.5의 sha256 verification이 safety net

**주의**: 이 테스트는 **edge case 검증**. 실사용에서 사용자가 두 Claude Code 세션을 1초 이내 시작할 일은 거의 없음. 하지만 자동화된 test suite나 script 경우 race condition 가능.

## 11. Rollout 및 마이그레이션

### 11.1 개발자 측 작업 순서

Section 15의 구현 phase를 따름. 요약:

1. Phase 1 (병렬): Loader script + Hook script + SKILL.md + compile-report.js 수정
2. Phase 2 (병렬): settings.json 병합 + review-agent/drafting-agent/ingestion-agent AGENT.md 수정
3. Phase 3 (순차): CLAUDE.md dispatch 절차 추가 → Test scripts 작성
4. Phase 4 (순차): Test 1-8 실행 (Test 7 gate 통과 필수)
5. Phase 5 (순차): 기획 문서 이관 + commit + push

### 11.2 사용자 (지인 A) 측 작업

1. **Git pull**:
   ```bash
   cd ~/path/to/contract-review-agent
   git pull origin main
   ```
2. **Prerequisite 확인** (P5):
   ```bash
   command -v jq >/dev/null && echo "✅ jq OK" || echo "❌ Install: brew install jq"
   command -v shasum >/dev/null || command -v sha256sum >/dev/null && echo "✅ sha256 OK" || echo "❌ missing"
   ```
   **이미 기존 ingest hook이 jq 사용 중이라 지인 A 환경에는 설치되어 있을 것.**
3. **실행 권한** (git이 보존할 가능성 높지만 만약을 위해):
   ```bash
   chmod +x .claude/hooks/*.sh .claude/scripts/*.sh .claude/scripts/tests/*.sh
   ```
4. **Hook 승인**: Claude Code 첫 세션 시작 시 "새 hook 실행 허용" 다이얼로그 → Allow
5. **Smoke test**: 테스트 계약서 1건 `input/`에 드롭 → `/contract-review` → trace 파일 확인 (Section 9.2 명령)
5. **중요 과거 검토 재검증**: 픽스 이전 수행한 검토는 LLM 사전학습 지식 기반일 가능성이 높음
   - 기준: 2026-04-09 이전 수행된 모든 `/contract-review` 결과
   - 특히 EPC 계약, Common Law 전환 후 작성한 검토
   - 권장 조치: `/rereview` 또는 `/contract-review` 재실행
6. **`policies/` 디렉토리**: gitignored. 이전 customization 보존됨.

### 11.3 지인 A에게 전달할 안내 메시지

```
[contract-review-agent 중요 업데이트 안내]

지난번 발견한 "Claude가 review-guide.md를 실제로 읽지 않고 사전학습
지식으로 검토하던 문제"의 구조적 수정이 완료됐어.

## 뭐가 바뀌었나
- Hook + Bash script 경로 조합으로 review-guide.md 내용이 매 검토마다
  LLM context에 강제 주입됨
- 3중 방어선 (Hook / AGENT.md / CLAUDE.md dispatch)으로 한 경로 실패 시
  다른 경로 작동
- Executive Summary 마지막에 "Baselines applied: ..." trace 라인이
  자동 주입됨 (없으면 "REVIEW INVALID" 경고)
- forensic 증거로 sha256 해시 포함 — LLM이 hallucinate 불가

## 네가 할 일
1. git pull origin main
2. 처음 Claude Code 시작 시 hook 실행 승인 프롬프트 뜨면 Allow
3. 간단한 smoke test:
   - 더미 계약서 input/에 드롭
   - /contract-review 실행
   - 실행 후 이 경로 확인:
     contract-review/library/runs/sessions/{session_id}/loaded.json
   - 파일이 있고, sha256_short가 아래와 일치하면 픽스 작동:
     shasum -a 256 .claude/skills/review-domain-knowledge/references/review-guide.md | cut -c1-8
4. 최종 보고서 Executive Summary 마지막에
   "Baselines applied: review-guide.md (25018 bytes, sha256: ..., ...)"
   라인이 있는지 확인

## 과거 검토 재검증 권장
- 2026-04-09 이전의 모든 /contract-review 결과는 review-guide.md가
  실제로 사용되지 않았을 가능성이 높음
- 특히 네가 Common Law 전환한 이후 검토한 EPC / 중요 딜들은 /rereview
  또는 재실행 권장
- 지금은 trace 라인이 있으므로 재실행 결과의 forensic이 확보됨

## policies/ 디렉토리 영향 없음
네 customization은 gitignored이라 git pull이 덮어쓰지 않음.

## 이번 픽스의 한계
- Sub-agent dispatch 시 hook 재발동 여부가 공식 문서에 명시 없음 →
  AGENT.md Step 5.5 Bash가 fallback으로 작동. Test 6에서 실측 확인.
- 대형 계약서 (100+ 페이지)는 chunk마다 reference 재주입으로 context
  부담이 20-40%. 중형 계약이 지배적 사용례라 초기 구현은 이대로 유지.
  향후 selective injection으로 최적화 예정 (Future Enhancements).

문제 있으면 바로 연락.
```

### 11.4 다른 도구 사용자

- **Claude Code 비사용자**: 영향 없음
- **Cursor / Codex CLI 등**: Hook 미작동. AGENT.md Step 5.5 Bash가 유일 경로. Cursor에서 `/contract-review` 실행 시 agent가 Step 5.5 지시에 따라 loader를 수동 호출해야 함. Best-effort.

## 12. 실패 모드 및 복구

| 실패 모드 | 증상 | 복구 | Defense-in-depth 작동? |
|---|---|---|---|
| Hook script 실행 권한 없음 | Claude Code hook 에러 | `chmod +x` | AGENT.md Bash로 fallback 가능 |
| `$CLAUDE_PROJECT_DIR` 미설정 | Loader 경로 탐색 실패 | Fallback 로직 자동 적용 | — |
| review-guide.md 파일 부재 | Loader exit 2 | 파일 복원, 경로 확인 | ❌ 복구 필수 |
| Hook stdin JSON 파싱 실패 | Hook이 `{}` 반환 (silent) | stdin 형식 확인 | AGENT.md Bash로 fallback |
| Hook timeout (>5초) | Claude Code가 hook 중단 | Script 최적화 | AGENT.md Bash로 fallback |
| Sub-agent dispatch에서 hook 미재발동 | Context에 injection 없음 | — | ✅ AGENT.md Step 5.5 + CLAUDE.md dispatch |
| LLM이 Pre-Pipeline 0단계 Bash 무시 | Reference 로드 안 됨 | Test 7 gate로 사전 감지 | ❌ Hook에 의존 |
| Trace JSON 기록 실패 | `loaded.json` 없음 | Permissions 확인 | compile-report.js가 "REVIEW INVALID" 주입 |
| compile-report.js `loaded.json` 미감지 | Executive Summary에 warning | — | ✅ 사용자 visible |
| Canary heading mismatch (stale cache) | Step 5.5에서 감지 | Loader 재실행 | — |
| 기존 ingest hook 회귀 | `/ingest` 기능 고장 | Test 0.5로 사전 감지 | ❌ Test 0.5가 gate |
| Chunk 재주입 누락 | Chunk 2+ reference 없음 | Test 8로 사전 감지 | — |
| 동시 세션 trace collision (ls -t picks wrong) | Session A와 B 모두 < 1초 간격 시작 시 `ls -t` 가 B만 선택 → A가 자신의 trace 못 찾음 | Timestamp + PID + $RANDOM 로 session_id 생성 → collision 매우 드묾. Step 5.5 sha256 verification 이 safety net (file 자체는 같으므로 결과 동일). Test 9로 검증. | ✅ safe enough |
| settings.json JSON 파싱 에러 | Claude Code 시작 실패 | `git checkout .claude/settings.json` | — |
| PreToolUse hook이 새 script 경로 block | Script 실행 실패 | Path가 이미 allowed prefix에 포함되어 발생 안 함 | — |

## 13. 비목표 재확인

Section 3.2 참조. 주요 항목:
- Policy YAML 파일 강제 로드 (이미 처리)
- Hook 내용 크기 최적화 (10K cap 회피 위해 Bash indirect로 전환 — 근본 해결)
- Windows 지원
- 과거 검토 자동 재검증
- Selective sub-section injection (Future Enhancements)
- Template vs General 명시적 선택 UI (Future Enhancements)

## 14. 오픈 쿼스천 (v1 대비 축소)

**해소됨** (Feasibility spike 결과):
- ~~Hook의 stdin/stdout 포맷~~ → JSON (확정)
- ~~additionalContext 크기 제한~~ → 10K chars (확정)
- ~~이 설계가 실제로 작동하는가~~ → Bash indirect injection으로 우회 (확정)

**남아있음**:

| # | 질문 | 해소 방법 | 영향 |
|---|---|---|---|
| 1 | Sub-agent dispatch 시 UserPromptSubmit hook 재발동 여부 | **Test 6 실측** | Hook 미재발동 시 AGENT.md + CLAUDE.md fallback 의존도 증가 (하지만 이미 설계됨) |
| 2 | LLM의 Bash 실행 준수율이 실제로 90%+ 인가 | **Test 7 gate** (10회 측정) | 실패 시 설계 재고 |
| 3 | Plan mode에서 UserPromptSubmit hook 작동 여부 | 구현 중 실제 테스트 | Plan mode에서 작동 안 하면 AGENT.md Step 5.5가 단독 경로 |
| 4 | Drafting / Ingestion workflow에서도 동일 문제 재현되는가 | 구현 후 smoke test | 재현 안 되면 해당 agent의 Step 5.5는 optional 다운그레이드 고려 |

## 15. 구현 순서

### Phase 1 (병렬 실행 가능) — 4개 작업

**Lane A1**: Loader script + 단위 테스트
- Create `.claude/scripts/load-domain-references.sh`
- Create `.claude/scripts/tests/test-load-domain-references.sh`
- Run Test 1, verify all paths

**Lane A2**: Hook script + 단위 테스트
- Create `.claude/hooks/inject-domain-references.sh`
- Create `.claude/scripts/tests/test-inject-domain-references.sh`
- Create `.claude/scripts/tests/test-ingest-hook-regression.sh` (Test 0.5)
- Run Test 0.5 + Test 2

**Lane A3**: SKILL.md 업데이트
- `.claude/skills/review-domain-knowledge/SKILL.md` 수정
- "References are auto-loaded" 섹션 추가

**Lane A4**: compile-report.js 수정
- `.claude/skills/report-compiler/scripts/compile-report.js` 수정
- `loaded.json` 읽기 + trace line 주입 로직 추가
- Unit test for `injectBaselineTrace()`

### Phase 2 (병렬 실행 가능) — 4개 작업

**Lane B1**: settings.json 병합
- Current settings.json backup: `git show HEAD:.claude/settings.json > /tmp/settings-backup.json`
- Remove existing ingest hook entry
- Add new injector hook entry
- Preserve PreToolUse + permissions.allow
- Validate: `jq . .claude/settings.json`

**Lane B2**: review-agent/AGENT.md 수정
- Pre-Pipeline 0단계 추가
- Step 1.5 추가
- Step 5.5 추가
- Step 6 analysis constraint 추가
- Step 10 trace line 자동 주입 참조 추가
- Large Document Handling 섹션의 chunk reference re-injection 추가

**Lane B3**: drafting-agent/AGENT.md 수정
- Pre-Pipeline 0단계 추가 (draft workflow)
- Step 5.5 equivalent

**Lane B4**: ingestion-agent/AGENT.md 수정
- Pre-Pipeline 0단계 추가 (ingest workflow)

### Phase 3 (순차) — 2개 작업

**Lane C1**: CLAUDE.md dispatch 절차 추가
- Section "Baseline Reference Load — Root Agent Dispatch Protocol" 추가
- Phase 1-2 완료 후 (script 경로 참조)

**Lane C2**: 문서 이관 + README 업데이트
- `output/Domain-Reference-강제로드-아키텍처-기획-v2.md` → `docs/ko/domain-reference-forced-load.md`
- README.md + docs/ko/README.md에 아키텍처 한 줄 언급

### Phase 4 (순차) — Testing

**Test 1**: Loader standalone (Lane A1 완료 직후)
**Test 2**: Hook standalone (Lane A2 완료 직후)
**Test 0.5**: Ingest regression (Lane A2 완료 직후 — CRITICAL BLOCKING)
**Test 3**: Live Claude Code session canary (Phase 2 완료 후)
**Test 4**: End-to-end review + trace (Phase 2 완료 후)
**Test 5**: Hook disabled fallback (Phase 2 완료 후)
**Test 6**: Sub-agent hook propagation (Phase 3 완료 후)
**Test 7**: LLM Bash adherence gate (Phase 3 완료 후 — GATING)
**Test 8**: Chunking + re-injection (Phase 3 완료 후)

**Test 7 실패 시 flow**:
1. Hook instruction 언어 강화 (Lane A2 재작업)
2. Test 7 재실행
3. 3회 연속 실패 시 설계 근본 재고

### Phase 5 — Commit + Rollout

**Lane D1**: Commit 구조
- Commit 1: scripts (Lane A1 + A2) — `feat: add domain reference loader and injector hook scripts`
- Commit 2: settings.json (Lane B1) — `chore: merge injector hook into settings.json, absorb ingest hook`
- Commit 3: AGENT.md + SKILL.md (Lane B2-B4 + A3) — `feat: integrate forced-load protocol into review/drafting/ingestion agents`
- Commit 4: compile-report.js (Lane A4) — `feat: auto-inject baseline trace line into Executive Summary`
- Commit 5: CLAUDE.md + docs (Lane C1 + C2) — `docs: add root dispatch procedure and architecture documentation`
- Commit 6: tests (all test scripts) — `test: add forced-load regression and adherence tests`

**Lane D2**: Push + 사용자 안내
- `git push origin main`
- 지인 A에게 Section 11.3 안내 메시지 전달

### Phase 6 — Post-ship

- [ ] Session log 업데이트 (구현 완료 일자 추가)
- [ ] Future Enhancements TODO를 issue tracker에 등록
- [ ] 1주 후 사용자 A의 feedback 확인

## 16. Future Enhancements (NEW 섹션)

v2 구현 완료 후 후속 작업. 현재 scope에서 제외되지만 향후 가치 있음.

### 16.1 Selective Sub-section Injection (governing_law 기반)

**문제**: 대형 계약서 chunking 시 reference token이 context의 20-40% 차지.

**해결**: `review-guide.md`를 jurisdiction별 sub-file로 분할:
- `review-guide-common.md` (공통 섹션)
- `review-guide-ew.md` (E&W specific)
- `review-guide-us.md` (US specific)
- `review-guide-sg.md` (Singapore specific)
- `review-guide-epc.md` (EPC block)

Loader script가 `matter-context.yaml`의 `governing_law` 필드를 읽어 해당 sub-file만 주입. Context cost 70%+ 절감.

**구현 난이도**: Medium. 파일 분할 + loader 로직 + `matter-context.yaml` 선행 parsing.
**시기**: v2 구현 후 6개월 이내. 대형 계약서가 빈번해지면 우선순위 상승.

### 16.2 Template vs General Explicit Selection

**아이디어 (지인 A 제안)**: Library 후보가 있을 때 Pre-Pipeline에 세 번째 질문 추가:

> "이 계약서에 대한 라이브러리 템플릿이 발견되었습니다. (N개 후보)
>  1. Template-based 검토 (house position 비교)
>  2. General review (review-guide.md baseline만)"

**장점**:
- 사용자가 모드를 명시적으로 인지
- 투명성 증가
- 선택 announcement가 forensic 보조 역할

**조건**: Library empty 시 질문 skip (지인 A 우려 반영)

**구현**: AGENT.md Pre-Pipeline에 조건부 3번째 질문 + `matter-context.yaml`에 `review_approach: template | general` 필드 추가.

**시기**: v2 안정화 후 별도 commit. 독립적으로 구현 가능.

### 16.3 drafting-guide.md Schema Audit

**문제**: `drafting-guide.md`도 `review-guide.md`와 동일한 구조적 결함 가능성. 지인 A가 drafting workflow를 아직 일반 사용하지 않았지만, 사용 시 같은 인시던트 재발 위험.

**작업**:
- drafting-guide.md 내용 audit
- Common Law baseline 일관성 확인 (review-guide의 Common Law 전환과 동기화)
- Drafting checklist가 실제 workflow와 매치되는지 검증

**시기**: Drafting workflow 일반 사용 시작 전.

### 16.4 Past Review Re-verification Framework

**문제**: v2 구현 이전의 모든 `/contract-review` 결과는 review-guide.md 미사용 가능성. 사용자 안내에 포함되지만, **누가 / 언제 / 어떻게** 재검증할지 체계 없음.

**아이디어**:
- `contract-review/matters/` 하위를 스캔하여 v2 이전 검토 목록 추출
- 각 검토의 중요도 기준 (contract value, deal status) 분류
- 재검증 우선순위 대시보드 생성
- `/rereview-audit` 신규 command 도입

**시기**: 사용자 요구가 있을 때.

### 16.5 Session-level Trace Aggregation

**문제**: `contract-review/library/runs/sessions/` 무한 누적.

**해결**: 주기적 정리 script + 집계 리포트 ("이번 달 X회 review, 모두 baseline loaded") + retention policy.

**시기**: Trace 파일이 누적되어 volume 문제 발생 시.

## Appendix A — Context 비용 (v2 정확한 수치)

### 실측 파일 크기 (wc -c)

| 파일 | Bytes | 대략 tokens (4 chars/token) |
|---|---|---|
| `review-guide.md` | 25,018 | ~6,250 |
| `audience-firewall.md` | 4,046 | ~1,000 |
| `drafting-guide.md` | 23,096 | ~5,800 |
| `domain-policy.md` | 4,119 | ~1,000 |

### 주입 시나리오별 cost

| 시나리오 | Reference tokens | + Contract | + Analysis output | 합계 | 200K window 비율 |
|---|---|---|---|---|---|
| 중형 review (20p, 1 chunk) | ~7,250 | ~20,000 | ~15,000 | ~42,000 | **21%** |
| 대형 review (100p, 5 chunks) | **~36,250** (5×) | ~100,000 | ~30,000 | ~166,000 | **83%** ⚠️ |
| 메가 review (200p, 10 chunks) | **~72,500** (10×) | ~200,000 | ~60,000 | **~332,000** | **166%** 🚨 OVERFLOW |
| Draft (NDA 초안) | ~5,800 | — | ~5,000 | ~11,000 | **5.5%** |
| Ingest (single file) | ~1,000 | — | — | ~1,000 | **0.5%** |

**중요 관찰**:
- **중형 review는 안전** (21%)
- **대형 review는 경계선** (83% — 다른 tool call 여유 축소)
- **메가 review는 현재 설계로 불가능** (200K 초과)

**Mitigation**:
- Test 8에 context utilization gate 추가 (> 50% 시 경고)
- 대형/메가 계약서는 Future Enhancement 16.1 (selective injection) 우선순위 상승
- 메가 계약서의 경우 사용자에게 "chunking 크기 조정" 또는 "manual split" 권고

### 1M context 모델 사용 시 (Opus 4.6 1M)

| 시나리오 | 합계 | 1M window 비율 |
|---|---|---|
| 중형 review | ~42,000 | **4.2%** |
| 대형 review | ~166,000 | **16.6%** |
| 메가 review | ~332,000 | **33.2%** |

1M context에서는 여유 충분. 지인 A의 세션이 1M 모델 사용 시 context 문제 거의 없음.

## Appendix B — 파일 위치 참조

### 기존 파일 (v2에서 수정)

- `CLAUDE.md` (root dispatch 절차 추가)
- `.claude/settings.json` (hook entry 병합)
- `.claude/agents/review-agent/AGENT.md` (Pre-Pipeline 0, Step 1.5, 5.5, 6, 10, Chunking)
- `.claude/agents/drafting-agent/AGENT.md` (Pre-Pipeline 0, Step 5.5 equivalent)
- `.claude/agents/ingestion-agent/AGENT.md` (Pre-Pipeline 0)
- `.claude/skills/review-domain-knowledge/SKILL.md` (auto-load 섹션)
- `.claude/skills/report-compiler/scripts/compile-report.js` (trace line 주입)

### 신규 파일

- `.claude/hooks/inject-domain-references.sh`
- `.claude/scripts/load-domain-references.sh`
- `.claude/scripts/tests/test-inject-domain-references.sh`
- `.claude/scripts/tests/test-load-domain-references.sh`
- `.claude/scripts/tests/test-ingest-hook-regression.sh`
- `docs/ko/domain-reference-forced-load.md` (구현 완료 후 이 파일 이관)

### 동적 생성

- `contract-review/library/runs/sessions/{session_id}/loaded.json`
- `contract-review/matters/{id}/round_{N}/working/baseline-context/loaded.json`
- `contract-review/matters/{id}/round_{N}/working/baseline-context/chunk-{N}.json` (chunking 시)

### 건드리지 않음

- `.claude/skills/review-domain-knowledge/references/*.md` (내용 무변경)
- `contract-review/library/policies/*.yaml`
- `contract-review/library/policies.default/*.yaml`

## Appendix C — 참고 및 주의사항

### v1 대비 학습된 것

1. **Feasibility spike는 기획 확정 전에 해야 함** — v1은 788줄 쓴 뒤 핵심 가정이 틀렸다는 걸 발견. v2는 spike 후 작성.
2. **LLM의 "했다"는 증거가 아님** — 지인 A의 인시던트가 근본 교훈. Forensic trace를 LLM이 생성하면 hallucinate 가능. Script 자동 생성만 유효.
3. **지시어 강화는 구조적 해결이 아님** — "MUST Read" 아무리 추가해도 LLM 자발성 구조가 바뀌지 않음. 실제 context에 내용을 밀어넣는 물리적 경로 필요.
4. **Bash tool output에는 크기 제한이 없다** — Hook `additionalContext`와 대비. 이것이 v2의 핵심 enabler.

### 구현 시 주의

- **Commit 전 반드시 Test 0.5, 1-8 모두 통과 확인**. Test 7 gate 통과가 특히 중요.
- **부분 구현 커밋 금지**. "Hook만 있고 AGENT.md 수정 없음" 같은 상태는 새 실패 모드 유입.
- **지인 A에게 전달 시 trace 검증 명령 포함**. "Claude가 '읽었어요'라고 말했다"는 증거가 아님 (인시던트에서 이미 배움).
- **기존 ingest hook 회귀 위험이 가장 큼**. Test 0.5가 blocking gate.

### Session Log 참조

구현 시 이 기획 문서의 모든 결정 근거는 다음 파일에 기록됨:
- `logs/session-2026-04-09-common-law-conversion-and-forced-load-architecture.md`

특히 Phase 8 (Feasibility Spike)와 Phase 9 (16 issues resolution)의 Q&A 내역이 상세히 남아있음.

---

**v2.1 기획 문서 끝.**

**상태**: v2 review (2026-04-10) 의 9개 patch 가 in-place 로 모두 적용됨. 구현 착수 준비 완료.

---

## GSTACK REVIEW REPORT — v2

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review (v1) | `/plan-eng-review` | Architecture & tests | 1 | ISSUES_OPEN (PLAN) | 16 issues, 3 critical gaps, feasibility spike forced v2 redesign |
| **Eng Review (v2)** | `/plan-eng-review` | v2 targeted review | 1 | **ISSUES_OPEN (PLAN)** | **9 issues, 1 critical gap, all patchable in-place** |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**UNRESOLVED:** 0 — 모든 AskUserQuestion에 응답 받음
**VERDICT:** NOT CLEARED — 9 issues found, but all patches are in-place (no v3 rewrite needed)

### v2 대비 v1 해결 검증

v1 review의 16 issues 모두 v2에 반영됨 확인 (7 Architecture + 5 Code Quality + 1 Performance + 3 Test gaps → 전부 구체적 섹션/pseudo-code/테스트로 매핑).

### v2 Specific Findings (9 issues)

**Architecture (5)**:

| # | Issue | 결정 |
|---|---|---|
| V2-A1 | Draft/ingest over-engineering (실제 인시던트 없는 경로에 강제성 확산) | **C**: 경량 loader 호출만, BLOCKING 문구 제거. Incremental 원칙 준수 |
| V2-A2 | Pre-Pipeline 0의 LLM self-context check (v1 인시던트 근본 원인 재현 위험) | **B**: `test -f` filesystem check. Observable 원칙 |
| V2-A3 | `$CONTRACT_REVIEW_SESSION_ID` 환경변수 주입 경로 미명시 (forensic chain 단절 위험) | **A**: `ls -t ... | head -1` 방식. 환경변수 의존 제거 |
| V2-A4 | compile-report.js pseudo-code 틀림 — `executive_summary.review_notes` 필드 미존재 | **A**: 실제 `createExecutiveSummary()` (line 172-254) 구조 확인 후 재작성. `summary.recommendation` 렌더링 직후 paragraph append 방식 |
| V2-A5 | jq 의존성 문서 미명시 | **A**: Section 7 prerequisites + script assertion + smoke test |

**Code Quality (4, 한 뭉치)**:

| # | Issue | 결정 |
|---|---|---|
| V2-Q1 | `set -e` + pipe + `\|\|` fallback 조합으로 partial stdout 위험 | **A**: defensive error handling 명시 |
| V2-Q2 | Hook error path의 `jq -Rs .` + `sed` + `printf` double-escape 위험 | **A**: success path와 동일 패턴으로 통일 |
| V2-Q3 | Error/success path JSON 생성 중복 (DRY 위반) | **A**: `emit_injection()` helper로 통합 |
| V2-Q4 | detect_workflow() 우선순위 주석 | Minor — 코드 자체로 명확, 주석만 추가 |

**→ 3 코드 품질 이슈는 한 수정 뭉치로 Section 5.2/5.3 pseudo-code 재작성**

**Test (2 추가)**:

| # | Issue | 결정 |
|---|---|---|
| V2-T1 | compile-report.js 새 코드 경로 테스트 전무 (CRITICAL) | Test 4b 추가: (1) 정상 (2) loaded.json 없음 → "REVIEW INVALID" (3) schema 이상 → graceful fallback (backward compat) |
| V2-T2 | Concurrent sessions에서 `ls -t` 오선택 | Test 9 추가 |

**Performance (1)**: 200K context overflow 경고 — 지인 개인용이라 skip. 오픈소스 배포 시 재고.

### Critical Gap (1)

**compile-report.js backward compat** — v2 수정이 v1 당시 생성된 과거 review data 재컴파일 시 silent 깨질 위험. **Test 4b의 variant (3) "loaded.json 없음/schema 이상"으로 커버 예정**.

### Patch List (9 in-place patches, no v3 rewrite)

v2 파일에 적용해야 할 수정 목록. 섹션 번호 매핑:

| # | v2 섹션 | Patch 내용 |
|---|---|---|
| **P1** | Section 3.1 G3 + 5.5 + 6 + 10 Test | Draft/ingest 경량화 (V2-A1) |
| **P2** | Section 5.4 Pre-Pipeline 0 | LLM self-check → filesystem check (V2-A2) |
| **P3** | Section 5.3 + 5.4 Step 1.5 + 12 | `ls -t` 방식 전환 + concurrent collision 기록 (V2-A3) |
| **P4** | Section 5.4 Step 10 + 9.3 | compile-report.js pseudo-code 재작성 — 실제 구조 반영 (V2-A4) |
| **P5** | Section 7 + 11.2 + 5.2/5.3 | jq dependency 명시 + script assertion (V2-A5) |
| **P6** | Section 5.2 + 5.3 | defensive error handling + `emit_injection()` helper + DRY (V2-Q1/Q2/Q3) |
| **P7** | Section 10 | Test 4b (compile-report unit test) 추가 |
| **P8** | Section 10 | Test 9 (concurrent sessions) 추가 |
| **P9** | Section 5.2 detect_workflow | 우선순위 주석 보강 (minor) |

### Completion Summary

- Step 0: Scope Challenge — v2 scope refinement (Draft/ingest 경량화)
- Architecture Review: 5 issues found, all resolved
- Code Quality Review: 4 issues found (3 in one fix cluster)
- Test Review: 2 gaps → Test 4b + Test 9 added
- Performance Review: no blocking issues
- NOT in scope: 5 additional items
- What already exists: compile-report.js 실제 구조 확인 완료 (line 172-254)
- TODOS.md updates: 2 items, both skip (covered by existing artifacts)
- Failure modes: 6 v2-specific, 1 critical gap flagged (compile-report backward compat → Test 4b로 커버)
- Outside voice: skipped (weekly limit)
- Parallelization: v2 Section 15 그대로 유지
- **Lake Score: 9/9 complete options (100%)**

### 다음 단계

1. **v2에 9개 patch in-place 적용** (P1-P9)
2. **Patched v2 → `docs/ko/domain-reference-forced-load.md` 이관** (Phase 3 Lane C2)
3. **Phase 1 구현 착수** (parallelization 전략 유지)

v3 재작성은 불필요. v2의 전체 구조·결정·아키텍처는 유지되고, 9개 patch는 모두 섹션 단위 in-place 수정으로 충분.

---

**v2 기획 문서 + review report 끝.**
