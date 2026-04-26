# Agent Engineering & Design Audit Remediation Plan — 검증 보고서

| 항목 | 값 |
|---|---|
| 검증 대상 | [`docs/plans/engineering-design-audit-remediation-plan.md`](./engineering-design-audit-remediation-plan.md) (Codex 작성) |
| 검증일 | 2026-04-25 |
| 검증자 | Opus 4.7 |
| 검증 범위 | 계획서에 기재된 모든 "문제" 진단과 "수정안"이 실제 코드베이스와 일치하는지 |
| 검증 방법 | 계획서에 인용된 모든 파일 경로·스크립트·라인 동작을 직접 확인 |

---

## 0. 요약 결론

계획서의 **전략적 방향(모델 지시 강화보다 산출물 계약 강제 우선)**은 타당하고, 지적 사항의 약 **80%는 사실에 부합**한다. 다만 다음 세 항목은 **현재 코드베이스와 불일치하거나 이미 해결된 사안**이므로 계획 수정이 필요하다.

| 중대성 | 항목 | 요지 |
|---|---|---|
| 🔴 높음 | 작업 5-1 "Pipeline state 도입" | **이미 완전한 skill로 구현되어 있다**. `.claude/skills/pipeline-state/` 및 `save-state.py`/`load-state.py`/`diff-rounds.py`가 활발히 사용 중이며 `/resume`이 이에 의존한다. "도입"이 아닌 "스키마 확장"으로 재정의해야 한다. |
| 🔴 높음 | 작업 6-3 "Policy customization tracking 정리" | **이미 해결되어 있다**. `.gitignore` 137-139행이 `policies/*`를 제외하고 `.gitkeep`만 허용하며, `git ls-files contract-review/library/policies/`는 `.gitkeep`만 반환한다. `policies.default/`도 이미 분리되어 있다. 작업이 불필요하다. |
| 🔴 높음 | 작업 0-2 "tracked cache 정리" | **이미 해결되어 있다**. `git ls-files` 출력에 `__pycache__`/`*.pyc`가 0건이다. 파일시스템상으로는 존재하지만 git에는 추적되지 않는다. 작업이 불필요하다. |
| 🟠 중간 | 작업 8 "dedicated draft DOCX packager" | **`compile-draft.js`가 이미 존재한다**(344줄). 문제는 packager 부재가 아니라 `report-compiler/SKILL.md` 29-30행의 문서가 낡아서 "아직 없다"고 주장하는 점이다. Option A "정식 추가"가 아니라 "SKILL.md 문구 수정 + 테스트 추가"가 정확한 처방이다. |
| 🟡 낮음 | 작업 3-2 review-mode 네이밍 | 계획서는 `light/moderate/strict`로 적었으나 실제 `review-mode.yaml`과 AGENT.md는 `strict/moderate/loose`(3-tier, 반대 방향)을 사용한다. 기존 네이밍을 따르거나 마이그레이션 합의가 필요하다. |

그 외 나머지 사항은 진단이 **대체로 정확**하고, 수정안도 **실행 가능**하다. 다만 일부 수정안은 설계상의 주의점(특히 session_id 전파, language policy 해소 방향)을 해결하지 않고 한쪽 답만 채택했다.

---

## 1. 배치별 검증 결과

아래 표의 '평가' 열은 다음 기준을 사용한다.

- ✅ **정확** — 문제 진단과 수정안이 코드베이스와 일치
- 🟡 **부분 정확** — 진단은 맞으나 수정안이 기존 설계를 놓치거나 보완이 필요
- 🔴 **부정확** — 문제 진단 자체가 이미 해결된 상태이거나 사실과 다름

### Batch 0 — Baseline Stabilization

| 작업 | 평가 | 근거 |
|---|---|---|
| **0-1 테스트 entrypoint 정리** | ✅ 정확 | `package.json` 확인 결과 `"test": "echo \"Error: no test specified\" && exit 1"`. `python3 -m pytest -q`는 144 passed로 통과. 수정안 타당. |
| **0-2 tracked cache 정리** | 🔴 **부정확** | `git ls-files \| grep -E '__pycache__\|\.pyc$'` 출력이 **0건**. 파일시스템상 `__pycache__/`는 존재하지만 git에는 이미 추적되지 않음(.gitignore 포함). 작업을 삭제해야 한다. |

### Batch 1 — Output Contract Hard Gates

| 작업 | 평가 | 근거 |
|---|---|---|
| **1-1 JSON Schema 추가** | ✅ 정확 | `.claude/schemas/` 디렉터리 부존재 확인. schema 전면 부재가 맞음. |
| **1-2 보고서 completeness hard fail** | ✅ 정확 | [`compile-report.js`](../../.claude/skills/report-compiler/scripts/compile-report.js) 1152-1194행 `validateClauseCompleteness()`는 경고만 기록(`console.warn` + `review_notes.unshift`)하고 렌더링을 계속한다. 실제로 주석에 "This does NOT halt rendering"이라고 명시되어 있음. 수정안 타당. |
| **1-3 redline/comment partial failure gate** | ✅ 정확 | [`apply-redlines.py`](../../.claude/skills/docx-redliner/scripts/apply-redlines.py) 390-396행은 `total_redlines > 0 and applied_count == 0`에서만 실패 처리. [`apply-comments.py`](../../.claude/skills/docx-redliner/scripts/apply-comments.py) 429-444행도 동일 패턴. partial 실패는 통과. 수정안 타당. |

### Batch 2 — DOCX Mapping Reliability

| 작업 | 평가 | 근거 |
|---|---|---|
| **2-1 Clause mapping confidence model 개선** | ✅ 정확 | [`map-clauses-to-docx.py`](../../.claude/skills/docx-redliner/scripts/map-clauses-to-docx.py) 204행 `sim > 0.4` threshold는 매우 낮음. exact substring 후 fuzzy fallback만 있고, `match_method`나 heading-aware 로직 없음. 확장 필요성 타당. |
| **2-2 Coverage fallback을 코드로 구현** | 🟡 부분 정확 | [`docx-redliner/SKILL.md`](../../.claude/skills/docx-redliner/SKILL.md) 98-115행에 fallback 정책은 이미 문서화됨. 스크립트는 `coverage < 0.9`에서 exit 2만 반환하고 50% halt 경계는 코드 미구현. 문제 진단과 처방 모두 타당하나, 계획서에 "SKILL.md에만 있다"로 표현하면 충분. 단, 제안 스키마에 `coverage_status`, `unmapped_clause_ids` 추가는 기존 `mapped`/`coverage`/`coverage_pct` 필드와의 관계 정리 필요. |

### Batch 3 — Language & Review Mode Canonicalization

| 작업 | 평가 | 근거 |
|---|---|---|
| **3-1 Canonical language policy 파일 추가** | ✅ 정확 — 단, 해소 방향 불일치 조정 필요 | 실제 [INTERNAL] 코멘트 언어 기술이 **세 문서에서 모두 다름**: <br>• `.claude/commands/contract-review.md:101` → "Written in the user's prompt language" <br>• `.claude/skills/review-domain-knowledge/SKILL.md:104` → "Report language" <br>• `.claude/agents/review-agent/AGENT.md:574` → "in the contract's original language to match the reviewer reading context" <br>계획서의 제안 YAML(`internal_comments.language: report_language`)은 세 답 중 한쪽을 임의 채택한 것이므로, PR 전 어느 문서가 맞는 답인지에 대한 결정 요청이 먼저 필요하다. |
| **3-2 Review mode policy 파일 추가** | 🟡 부분 정확 — **네이밍 충돌** | 계획서 YAML은 `light/moderate/strict`이나 실제 [`review-mode.yaml`](../../contract-review/library/policies/review-mode.yaml)과 [`AGENT.md:318-320`](../../.claude/agents/review-agent/AGENT.md)은 **`strict/moderate/loose`**(방향도 반대)이다. 또한 review-mode.yaml은 이미 mode별 `redline_scope`·`acceptable_playbook_tiers`·`comment_generation` 필드를 보유하고 있으므로 "새 YAML 추가"가 아닌 "기존 YAML에 threshold 명시화 + canonical source 지정"이 정확한 처방이다. |

### Batch 4 — Token Efficiency

| 작업 | 평가 | 근거 |
|---|---|---|
| **4-1 Reference loader digest-first 전환** | ✅ 정확 | [`load-domain-references.sh`](../../.claude/scripts/load-domain-references.sh) 120-159행은 모든 파일을 `cat`으로 전체 출력. `review-guide.md`(25,850B) + `audience-firewall.md`(4,046B) = **29,896B ≈ 29.9KB** — 계획서 수치 확인됨. digest-first 전환은 합리적. |
| **4-2 Retrieval summary-first 전환** | ✅ 정확 | [`query-index.py`](../../.claude/skills/index-manager/scripts/query-index.py) 386-388행에서 per-clause 매칭 실패 시 `per_clause = combined_candidates`로 전체 후보를 주입. 406-409행에서 최종 후보 전원에 대해 `hydrate_candidates_text()`로 full text hydrate. 수정안 타당. |
| **4-3 Large document chunk reference reuse** | ✅ 정확 | [`AGENT.md:636-640`](../../.claude/agents/review-agent/AGENT.md)에 "each chunk (not only the first), the agent MUST run ... load-domain-references.sh review" — 청크 수만큼 29.9KB 반복 주입. digest 재사용은 타당. |

### Batch 5 — Pipeline Architecture

| 작업 | 평가 | 근거 |
|---|---|---|
| **5-1 Pipeline state 도입** | 🔴 **부정확 — 이미 존재** | [`.claude/skills/pipeline-state/SKILL.md`](../../.claude/skills/pipeline-state/SKILL.md)에 풀 스펙 존재. [`save-state.py`](../../.claude/skills/pipeline-state/scripts/save-state.py)(132줄+), [`load-state.py`](../../.claude/skills/pipeline-state/scripts/load-state.py)(207줄+), [`diff-rounds.py`](../../.claude/skills/pipeline-state/scripts/diff-rounds.py) 모두 구현됨. `/resume` 명령도 이를 전제로 동작([`commands/resume.md:11`](../../.claude/commands/resume.md)). <br><br>실제 스키마는 `pipeline`/`matter_id`/`round`/`last_completed_step`/`step_artifacts.step_N.status` 구조이며, 계획서 제안 스키마(`schema_version`/`session_id`/`steps.*.status`)와 다름. <br><br>**처방**: "도입"이 아닌 "기존 스키마에 `session_id`·`schema_version` 필드 추가 + 스키마 버전 마이그레이션"으로 재작성 필요. |
| **5-2 Explicit session id 전달** | ✅ 정확 | [`AGENT.md:197-218`](../../.claude/agents/review-agent/AGENT.md)이 `ls -t contract-review/library/runs/sessions/*/loaded.json \| head -1` 방식으로 latest trace 선택. 동일 행 주석에 "Claude Code does not propagate a stable session ID across sub-agent dispatch"라는 제약이 명시되어 있으므로, 계획서 제안대로 env var 강제 전달이 동시 실행 collision 해소에 적절. 단, sub-agent 경계에서 env var이 실제로 전파되는지 실험 검증이 선행되어야 한다(계획서 내용과 `CLAUDE.md`의 Open Question 1 참조). |
| **5-3 Slash command를 thin router로 축소** | ✅ 정확 | [`contract-review.md`](../../.claude/commands/contract-review.md)(113줄)와 [`AGENT.md`](../../.claude/agents/review-agent/AGENT.md)(650줄)는 리스크 grading, comment 언어 정책, threshold 설명 등이 **내용상 중복**. divergence 리스크 실재. 수정안 타당. |

### Batch 6 — Production Safety Features

| 작업 | 평가 | 근거 |
|---|---|---|
| **6-1 External-clean post-export scanner** | ✅ 정확 | [`strip-internal-comments.py`](../../.claude/skills/docx-redliner/scripts/strip-internal-comments.py)는 `[INTERNAL]` prefix 코멘트 제거만 수행. 본문/헤더/푸터/tracked-changes 텍스트에 내부 전략어가 남았는지는 검사하지 않음. `scan-docx-for-internal-markers.py`도 부존재. 수정안 타당. |
| **6-2 Source ingest 실제 구현** | ✅ 정확 | `.claude/skills/ingest/scripts/` 디렉터리 **부존재**(SKILL.md만 존재). `contract-review/library/indexes/source-registry.json`도 **부존재**. `library/sources/` 하위는 `.gitkeep`만. 수정안 타당. |
| **6-3 Policy customization tracking 정리** | 🔴 **부정확 — 이미 해결됨** | [`.gitignore`](../../.gitignore) 137-139행: <br>`# User-customized policies (gitignored — defaults ship in policies.default/)` <br>`/contract-review/library/policies/*` <br>`!/contract-review/library/policies/.gitkeep` <br><br>`git ls-files contract-review/library/policies/` 출력은 `.gitkeep`만. `policies.default/`도 이미 독립 존재. `git check-ignore -v`로 `review-mode.yaml` 등 모든 YAML이 ignore됨을 확인. 작업이 불필요하므로 **PR에서 제거해야 한다**. |

### Batch 7 — Prompt Injection & Routing Hardening

| 작업 | 평가 | 근거 |
|---|---|---|
| **7-1 Untrusted wrapper 강제** | ✅ 정확 | [`AGENT.md:7-22`](../../.claude/agents/review-agent/AGENT.md)의 "Safety Envelope"는 "mentally enclose ... in `<untrusted_contract_content>` delimiters" — 즉 **정신적/프롬프트상** 래핑일 뿐 normalize 결과물에 물리적 태그가 없음. 수정안(normalize 출력에 실제 XML 래퍼 추가) 타당. |
| **7-2 Hook routing fail-closed** | ✅ 정확 | [`inject-domain-references.sh:39-46`](../../.claude/hooks/inject-domain-references.sh)은 jq 부재 시 `echo '{}'` + `exit 0`. 에러는 stderr로만 나가고 사용자에게 보이지 않으며 review workflow가 계속됨. review에서 fail-closed는 타당. |

### Batch 8 — Drafting Workflow Contract

| 작업 | 평가 | 근거 |
|---|---|---|
| **8 Draft 워크플로 계약 통일** | 🟡 부분 정확 — 기존 자산 누락 | 문제 진단(3개 문서의 보장 수준 불일치)은 **정확**: <br>• `draft.md:130` → DOCX 강제 생성 <br>• `drafting-agent/AGENT.md:100` → "If no workspace is active ... skip DOCX generation" <br>• `report-compiler/SKILL.md:29-30` → "packager가 아직 없다" <br><br>그러나 처방 **Option A "compile-draft.js 정식 추가"는 부정확** — [`compile-draft.js`](../../.claude/skills/report-compiler/scripts/compile-draft.js)가 **이미 존재(344줄)**. 올바른 처방은 "SKILL.md 29-30행 낡은 문구 수정 + drafting-agent의 optional workspace 문구 제거 + compile-draft에 대한 테스트 추가"이다. |

---

## 2. 계획서가 잘 잡아낸 지점

1. **"prompt가 아닌 코드로 강제하라"** — 핵심 결론 섹션의 우선순위 재정렬(완성도 gate → confidence gate → token → state → production)은 올바르다.
2. **compile-report.js 완성도 gate** — 2026-04-11 인시던트 메커니즘(Step 6에서 27건이 Step 10에서 10건으로 collapse)이 여전히 warning-only임을 정확히 포착.
3. **query-index.py "clause 매칭 실패 시 combined 전체 주입"** — 프롬프트만 보고는 발견하기 어려운 실제 동작을 코드로 확인해 지적.
4. **Chunk별 reference 재주입** — `AGENT.md`가 v2.1 "Reference re-injection per chunk"를 자랑스럽게 내세우는데, 이것이 곧 토큰 낭비의 원흉임을 뒤집어 본 것은 타당.
5. **Language policy 3-way divergence** — 실제로 세 문서가 서로 다른 답을 기록하고 있으며, 어느 하나가 리그레션인지조차 불분명한 상태.

---

## 3. 계획서가 놓친 지점

### 3-1. 기존 자산(pipeline-state, compile-draft) 인지 실패

감사를 수행하기 전에 **"이 기능이 이미 존재하지 않는가"**를 확인하지 않은 흔적이 두 곳에서 나타난다(Batch 5-1, Batch 8). 특히 Batch 5-1은 PR 5의 핵심인데, 이미 있는 것을 "도입"으로 표현하면 리뷰어가 혼란스러워지고, 실제 필요한 스키마 마이그레이션 작업이 드러나지 않는다.

### 3-2. 네이밍 합의 미결

- Batch 3-2는 `light/moderate/strict`로 네이밍을 제안하나 기존은 `strict/moderate/loose`. 만약 계획서 네이밍을 채택한다면 최소 다음이 연쇄 변경된다.
  - [`review-mode.yaml`](../../contract-review/library/policies/review-mode.yaml)의 mode key 이름과 `recommended_for` 매핑
  - [`review-mode.yaml`](../../contract-review/library/policies/review-mode.yaml)의 `mode_triggers` 키 전부
  - [`AGENT.md:318-320, 501`](../../.claude/agents/review-agent/AGENT.md)
  - [`review.json` 스키마](../../.claude/agents/review-agent/AGENT.md) 내 `"review_mode"` enum

이 연쇄 변경이 계획서에 포함되어 있지 않다.

### 3-3. 실행 가능한 검증 전략 부재

Batch 5-2(explicit session id 전달)는 근본적으로 "sub-agent 경계에서 env var이 전파되는가" 여부에 의존한다. `CLAUDE.md`와 `output/Domain-Reference-강제로드-아키텍처-기획-v2.md` Section 14에서 이를 "Open Question"으로 다루고 있음에도, 계획서는 그 검증 없이 수정안만 제시한다. **"먼저 Test 6을 완료하라"**는 선행 조건이 PR 5 수용 기준에 들어가야 한다.

### 3-4. 테스트 fixture 디렉터리 부존재

`tests/fixtures/` 디렉터리가 **존재하지 않는다**(현재 `tests/` 하위는 `test_*.py`만). Batch 4 테스트 전략의 모든 fixture 경로(`tests/fixtures/review/...`, `tests/fixtures/redlines/...` 등)는 새로 만들어야 한다. 계획서는 이를 "추가"로 표현해야 하며, 기존 tests와의 통합(conftest, pytest path) 전략이 필요하다.

### 3-5. 한국어 법률 의견 스타일 가이드와의 상호작용 미논의

프로젝트 CLAUDE.md는 한국어 검토 메모에 대해 `_private/docs/ko-legal-opinion-style-guide.md`를 엄격히 따르도록 강제한다. Batch 1-2(completeness fail), Batch 1-3(partial fail), Batch 3-1(언어 정책 canonical YAML)은 모두 이 스타일 가이드와 교차 영향이 있다. 계획서가 스타일 가이드 문구 변경/보존 의무를 언급하지 않은 점은 위험 요소다.

### 3-6. "성공 기준"의 측정 가능성

Section 2의 "review workflow 한 건에서 baseline reference 전문이 불필요하게 2회 이상 주입되지 않는다"는 기준은 **어떻게 측정하는가**가 계획서에 없다. 토큰 측정을 위한 로깅 인프라(Section 7의 `pipeline_metrics.json`)를 어느 단계에서 구현하는지 배치에 명시되지 않았다.

---

## 4. PR 분리에 대한 재검토

계획서 Section 5의 PR 분리는 대체로 타당하나, 위 검증 결과에 따라 다음 조정이 필요하다.

| 현재 PR | 조정 제안 | 이유 |
|---|---|---|
| **PR 1** (Baseline + Schema gates) | 작업 0-2 제거 | 이미 해결됨 |
| **PR 5** (Pipeline state + session) | 제목을 "Pipeline state schema migration + session isolation"으로 변경 | 도입이 아닌 확장임을 명확화 |
| **PR 6** (Production safety) | 작업 6-3 제거 | 이미 해결됨 |
| **PR 7** (Drafting) | Option A를 "SKILL.md 문구 갱신 + 기존 compile-draft.js 테스트 추가"로 수정 | packager는 이미 존재 |

PR 3(Policy canonicalization)은 **착수 전에** language-policy.yaml의 canonical 답(특히 [INTERNAL] 코멘트 언어)에 대한 사용자/프로덕트 오너 결정이 선행되어야 한다. 현재 세 문서가 서로 다른 답을 주장하는 것은 어느 한쪽이 리그레션일 가능성이 높으며, 계획서 자체로는 근거가 부족하다.

---

## 5. 결론 및 권고

- 계획서의 **전략적 판단은 신뢰할 만하다**. 출력물 계약을 prompt가 아닌 코드로 강제한다는 중심 원칙은 올바르며, 배치 1-1·1-2·1-3, 2-1, 4-1·4-2·4-3, 5-3, 6-1·6-2, 7-1·7-2는 그대로 진행해도 좋다.
- **세 개의 "이미 해결됨" 오진단(0-2, 5-1, 6-3)과 한 개의 "이미 존재함"(Batch 8 compile-draft.js)은 PR에 들어가기 전에 수정되어야 한다.** 그렇지 않으면 구현자가 불필요한 삭제 커밋을 만들거나, 더 나쁘게는 기존 자산을 덮어쓰게 된다.
- **Batch 3-2의 mode 네이밍과 3-1의 [INTERNAL] 코멘트 언어**는 **결정 대기 항목**으로 분리하여, 구현 전 사용자 합의를 받은 뒤 진행해야 한다.
- **선행 검증 필요 항목**: Batch 5-2 env var 전파 실험(Test 6), Batch 4-1 digest 전환 전후 golden output 비교.

권장 실행 순서:

1. 본 검증 보고서에 대한 사용자 승인 → 계획서 개정판 작성
2. PR 1(수정판) 착수 — 가장 안전한 가드레일
3. PR 3의 canonical 답 결정 → PR 3 착수
4. 동시에 PR 2(DOCX mapping) 진행
5. PR 4(token), PR 5(state migration with Test 6 완료 후), PR 6(safety), PR 7(drafting 문서 정합) 순차 진행

---

## 6. 검증 방법론 부록

본 보고서는 아래 명령으로 확인 가능한 사실만 근거로 삼았다.

```bash
# Batch 0-1
cat package.json | grep test
python3 -m pytest -q

# Batch 0-2, 6-3
git ls-files | grep -E '__pycache__|\.pyc$'
git ls-files contract-review/library/policies/
git check-ignore -v contract-review/library/policies/review-mode.yaml

# Batch 1-1, 6-2
ls .claude/schemas/
ls contract-review/library/indexes/source-registry.json
ls .claude/skills/ingest/scripts/

# Batch 1-2
grep -n "validateClauseCompleteness\|console.warn\|halt" .claude/skills/report-compiler/scripts/compile-report.js

# Batch 1-3
grep -n "applied_count == 0\|comments_applied_count" .claude/skills/docx-redliner/scripts/apply-*.py

# Batch 2-1
grep -n "sim > 0\." .claude/skills/docx-redliner/scripts/map-clauses-to-docx.py

# Batch 4-1
wc -c .claude/skills/review-domain-knowledge/references/*.md

# Batch 4-2
sed -n '373,410p' .claude/skills/index-manager/scripts/query-index.py

# Batch 4-3
grep -n "chunk\|re-injection" .claude/agents/review-agent/AGENT.md

# Batch 5-1
ls .claude/skills/pipeline-state/
cat .claude/skills/pipeline-state/SKILL.md

# Batch 5-2
grep -n "ls -t\|loaded.json\|session_id" .claude/agents/review-agent/AGENT.md

# Batch 8
ls .claude/skills/report-compiler/scripts/
sed -n '25,35p' .claude/skills/report-compiler/SKILL.md
```

모든 결과는 `contract-review-agent` repo 현재 상태(`main` 브랜치 기준, 검증 시점 2026-04-25)에서 재현 가능하다.
