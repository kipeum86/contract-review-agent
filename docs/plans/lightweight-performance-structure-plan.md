# Lightweight Performance & Workspace Structure Plan

| 항목 | 값 |
|---|---|
| 생성일 | 2026-05-26 |
| 작성자 | Codex |
| 대상 | VS Code 설정, Claude hook, local/runtime workspace 구조 |
| 목적 | 무거운 리팩터링 없이 IDE 체감 성능, agent hook 지연, 산출물 폴더 가독성을 개선 |
| 범위 | 이전 점검에서 제안한 1번, 2번, 5번 |
| 권장 실행 방식 | 작은 PR 3개 또는 커밋 3개로 분리 |

## 0. 핵심 결론

이 개선은 core review logic을 바꾸지 않고, 개발 환경과 실행 산출물 주변부만 가볍게 정리한다.

우선순위는 다음과 같다.

1. VS Code가 대량 계약 라이브러리와 runtime 산출물을 계속 watch/search하지 않도록 제외 설정을 추가한다.
2. `.claude/settings.json`의 inline PreToolUse hook을 별도 script로 빼고, 불필요한 hook 실행 범위를 줄인다.
3. `input/`, `output/`, `logs/`, `contract-review/matters/`, `contract-review/library/runs/` 같은 local/runtime 폴더를 장기적으로 `contract-review/workspace/` 아래로 모으되, 기존 경로 호환을 유지한다.

## 1. 범위와 비범위

### 범위

- `.vscode/settings.json`에 `files.watcherExclude`, `search.exclude`, 필요 시 `files.exclude` 추가
- `.claude/settings.json`의 PreToolUse inline Python을 `.claude/hooks/pretooluse-guard.py`로 분리
- hook matcher와 guard 조건을 안전하게 축소
- runtime workspace 목표 구조와 이행 단계 정의
- README, HOW-TO-USE, CLAUDE.md, slash command 문서의 경로 표기 정합화 계획

### 비범위

- 승인된 계약 라이브러리(`contract-review/library/approved`)의 데이터 모델 변경
- `query-index.py`, `build-index.py`의 retrieval logic 변경
- 기존 `input/`과 `output/` 즉시 삭제
- 과거 matter/runs/logs의 강제 이동
- 외부 DB, vector store, 새 framework 도입

## 2. 현황 요약

### 파일 규모

- repo 전체: 약 51 MB
- `contract-review`: 약 21 MB
- `node_modules`: 약 18 MB
- `contract-review/library`: 약 3,536개 파일
- 큰 JSON 인덱스:
  - `clauses.json`: 약 1.6 MB
  - `clause-texts.json`: 약 1.25 MB
  - `retrieval-map.json`: 약 0.39 MB

### 측정된 실행 비용

- `load-domain-references.sh review --mode=digest`: 약 0.08초
- `query-index.py query` summary mode: 약 0.04초
- `query-index.py search` text query: 약 0.03초
- `build-index.py rebuild`: 약 0.15초

따라서 현재 병목은 핵심 스크립트 CPU 시간이 아니라, IDE watcher/search 범위와 agent hook 반복 실행의 누적 비용일 가능성이 높다.

## 3. Batch 1 - VS Code Watch/Search 제외

### 목표

VS Code가 대량 데이터와 local-only 산출물을 계속 감시하거나 검색하지 않게 하여 workspace 반응성을 개선한다.

### 대상 파일

- `.vscode/settings.json`

### 수정안

기존 설정:

```json
{
  "chatgpt.openOnStartup": false
}
```

권장 설정:

```json
{
  "chatgpt.openOnStartup": false,
  "files.watcherExclude": {
    "**/.git/**": true,
    "**/.pytest_cache/**": true,
    "**/__pycache__/**": true,
    "**/node_modules/**": true,
    "input/**": true,
    "output/**": true,
    "logs/**": true,
    "contract-review/matters/**": true,
    "contract-review/library/runs/**": true,
    "contract-review/library/inbox/_processed/**": true,
    "contract-review/library/inbox/_failed/**": true,
    "contract-review/library/approved/**/normalized/**": true,
    "contract-review/library/approved/**/quality/**": true
  },
  "search.exclude": {
    "**/.git/**": true,
    "**/.pytest_cache/**": true,
    "**/__pycache__/**": true,
    "**/node_modules/**": true,
    "input/**": true,
    "output/**": true,
    "logs/**": true,
    "contract-review/matters/**": true,
    "contract-review/library/runs/**": true,
    "contract-review/library/inbox/_processed/**": true,
    "contract-review/library/inbox/_failed/**": true
  }
}
```

### 설계 판단

- `contract-review/library/indexes/**`는 제외하지 않는다. 인덱스는 debug와 검색 확인에 자주 필요하다.
- `contract-review/library/approved/**` 전체를 search에서 제외하지 않는다. 승인 template 본문을 IDE에서 검색할 일이 있기 때문이다.
- 다만 `normalized/`와 `quality/`처럼 반복 산출물 성격이 강한 하위 폴더는 watcher에서 제외한다.
- `files.exclude`는 기본으로 추가하지 않는다. 파일 탐색기에서 보이지 않으면 사용자가 헷갈릴 수 있으므로, 필요할 때만 별도 결정한다.

### 검증

```bash
python3 -m json.tool .vscode/settings.json
git status --short
```

### 수용 기준

- `.vscode/settings.json`이 valid JSON이다.
- `input/`, `output/`, `logs/`, `matters/`, `library/runs/`가 watcher와 search에서 제외된다.
- `contract-review/library/indexes/`는 계속 검색 가능하다.
- 테스트는 코드 변경이 없으므로 필수는 아니지만, 최종 PR에서는 `python3 -m pytest -q`를 1회 실행한다.

## 4. Batch 2 - Claude Hook 경량화

### 목표

매 Bash/Edit/Write tool 사용마다 실행되는 inline Python hook의 유지보수성과 반복 실행 비용을 줄인다.

### 현재 구조

- `.claude/settings.json`의 `PreToolUse` hook이 `Write|Edit|Bash`에 매칭된다.
- hook command가 긴 `python3 -c "...inline script..."` 형태다.
- 현재 guard는 두 가지를 한다.
  - 허용 디렉터리 밖 파일 write 차단
  - `approved/` 직접 write성 Bash command 차단

### 대상 파일

- `.claude/settings.json`
- 신규: `.claude/hooks/pretooluse-guard.py`
- 선택: `tests/test_production_safety_features.py` 또는 신규 `tests/test_claude_hooks.py`

### 수정안

#### 2-1. Inline script 분리

`.claude/hooks/pretooluse-guard.py`를 추가한다.

역할:

- stdin 또는 `TOOL_INPUT`에서 JSON 입력을 읽는다.
- `file_path`가 있는 경우 write allowlist를 검사한다.
- `command` 또는 `cmd`가 있는 경우 `approved/` 직접 write성 command를 검사한다.
- 문제 없으면 exit 0, 차단 시 stderr에 `BLOCKED: ...` 출력 후 exit 1.

`.claude/settings.json`은 아래처럼 짧게 바꾼다.

```json
{
  "matcher": "Write|Edit|Bash",
  "hooks": [
    {
      "type": "command",
      "command": "python3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/pretooluse-guard.py"
    }
  ]
}
```

#### 2-2. Bash guard fast path 추가

`Bash` command에 approved 관련 marker가 전혀 없으면 정규식 검사를 건너뛴다.

검사 대상 marker:

```python
APPROVED_MARKERS = (
    "contract-review/library/approved",
    "approved/templates",
    "approved/precedents",
    "approved/playbooks",
    "approved/comment-bank",
)
```

#### 2-3. Matcher 축소는 보류

`Write|Edit|Bash` matcher는 유지한다. directory write 차단과 approved 직접 write 차단은 안전 장치이므로, 성능만 보고 제거하지 않는다.

단, 별도 script로 분리한 뒤 실제 체감 지연이 계속 크면 다음 단계에서 matcher를 `Write|Edit|Bash(command includes approved marker)`처럼 더 좁히는 방안을 재검토한다. Claude hook matcher가 부분 조건을 지원하지 않으면 script fast path만 유지한다.

### 테스트 전략

Python unit style로 hook script를 직접 호출한다.

테스트 케이스:

- 허용 경로 write: exit 0
- repo 외부 write: exit 1
- `approved/templates`에 `cp`, `mv`, `rsync`, `tee`, redirect direct write: exit 1
- 허용 publisher script: exit 0
- 일반 Bash command: exit 0
- malformed JSON: exit 0

예시:

```bash
TOOL_INPUT='{"file_path":"contract-review/matters/x/round_1/working/a.json"}' \
  python3 .claude/hooks/pretooluse-guard.py

TOOL_INPUT='{"command":"cp a contract-review/library/approved/templates/x"}' \
  python3 .claude/hooks/pretooluse-guard.py
```

### 수용 기준

- `.claude/settings.json`의 긴 inline Python이 제거된다.
- 기존 차단 정책은 동일하게 유지된다.
- hook script 단위 테스트가 통과한다.
- `python3 -m pytest -q` 통과.
- hook failure message가 기존과 동일하거나 더 명확하다.

## 5. Batch 3 - Local Workspace 구조 정리

### 목표

실행 산출물과 사용자 local-only 파일을 장기적으로 한곳에 모아 repo root와 `contract-review/library`의 인지 부담을 줄인다.

### 핵심 원칙

- 기존 사용자 습관을 깨지 않는다.
- `input/`과 `output/`은 즉시 제거하지 않는다.
- 경로 변경은 resolver/helper와 문서 변경을 먼저 둔다.
- 과거 산출물은 자동 이동하지 않는다.

### 목표 구조

```text
contract-review/
├── library/                  # 승인 라이브러리, 정책, 인덱스
├── workspace/                # local-only runtime workspace
│   ├── input/                # review/draft input drop zone
│   ├── output/               # user-facing deliverables
│   ├── logs/                 # session notes
│   ├── matters/              # matter working directories
│   └── runs/                 # ingestion/session traces
└── matters/                  # legacy path, bridge period only
```

### 이행 단계

#### 3-1. Workspace 디렉터리와 ignore 규칙 추가

추가 후보:

```text
contract-review/workspace/.gitkeep
contract-review/workspace/input/.gitkeep
contract-review/workspace/output/.gitkeep
contract-review/workspace/logs/.gitkeep
contract-review/workspace/matters/.gitkeep
contract-review/workspace/runs/.gitkeep
```

`.gitignore` 추가:

```gitignore
# Unified local runtime workspace
/contract-review/workspace/input/*
!/contract-review/workspace/input/.gitkeep
/contract-review/workspace/output/*
!/contract-review/workspace/output/.gitkeep
/contract-review/workspace/logs/*
!/contract-review/workspace/logs/.gitkeep
/contract-review/workspace/matters/*
!/contract-review/workspace/matters/.gitkeep
/contract-review/workspace/runs/*
!/contract-review/workspace/runs/.gitkeep
```

#### 3-2. 경로 resolver를 먼저 도입

신규 helper 후보:

```text
.claude/scripts/workspace-paths.sh
```

역할:

- `CRA_INPUT_DIR`
- `CRA_OUTPUT_DIR`
- `CRA_MATTERS_DIR`
- `CRA_RUNS_DIR`
- `CRA_LOGS_DIR`

우선순위:

1. 명시 env var
2. `contract-review/workspace/...`
3. legacy root path fallback

예시:

```bash
CRA_INPUT_DIR="${CRA_INPUT_DIR:-contract-review/workspace/input}"
if [ ! -d "$CRA_INPUT_DIR" ] && [ -d "input" ]; then
  CRA_INPUT_DIR="input"
fi
```

#### 3-3. Agent와 command 문서 업데이트

업데이트 대상:

- `CLAUDE.md`
- `README.md`
- `docs/en/HOW-TO-USE.md`
- `docs/ko/HOW-TO-USE.md`
- `docs/ko/README.md`
- `.claude/commands/contract-review.md`
- `.claude/commands/rereview.md`
- `.claude/commands/draft.md`
- `.claude/commands/export-clean.md`
- `.claude/agents/review-agent/AGENT.md`
- `.claude/agents/drafting-agent/AGENT.md`
- `.claude/agents/ingestion-agent/AGENT.md`

문서 표현:

- 새 기본값: `contract-review/workspace/input/`, `contract-review/workspace/output/`
- legacy 호환: 기존 `input/`, `output/`도 bridge 기간 동안 계속 인식

#### 3-4. Bridge 기간 운영

Bridge 기간에는 다음을 모두 허용한다.

- 사용자가 root `input/`에 파일을 넣은 경우
- 사용자가 `contract-review/workspace/input/`에 파일을 넣은 경우
- output은 기본적으로 새 `workspace/output/`에 쓰되, 기존 command 문서와 충돌하는 동안 root `output/` 복사본 생성을 옵션으로 둔다.

권장 기간:

- 최소 1 minor release 또는 2주
- README와 HOW-TO-USE에 legacy deprecation note를 남긴다.

### 수용 기준

- 새 workspace 디렉터리 구조가 존재한다.
- `.gitignore`가 workspace 하위 산출물을 commit하지 않도록 보호한다.
- review/draft/export-clean 문서가 새 경로와 legacy fallback을 일관되게 설명한다.
- root `input/`/`output/`만 사용하는 기존 workflow가 깨지지 않는다.
- `python3 -m pytest -q` 통과.

### 보류 항목

- root `input/`, `output/`, `logs/` 삭제
- 기존 `contract-review/matters/` 자동 이동
- `contract-review/library/runs/` 즉시 relocation

이 보류 항목들은 실제 사용자 workflow가 새 workspace 경로에 적응한 뒤 별도 migration PR에서 처리한다.

## 6. PR 분리 제안

| PR | 제목 | 포함 작업 | 리스크 |
|---|---|---|---|
| PR 1 | `chore(vscode): exclude runtime folders from watch/search` | Batch 1 | 낮음 |
| PR 2 | `chore(hooks): extract pretooluse guard script` | Batch 2 | 중간 |
| PR 3 | `chore(workspace): introduce runtime workspace bridge` | Batch 3 | 중간-높음 |

권장 순서:

1. PR 1을 먼저 반영한다. 코드 동작 변경이 없고 즉시 체감 개선 가능성이 있다.
2. PR 2에서 hook behavior parity 테스트를 추가한다.
3. PR 3은 문서와 helper만 먼저 넣고, 실제 agent script 경로 변경은 별도 후속 작업으로 나눈다.

## 7. 검증 체크리스트

- [x] `.vscode/settings.json` valid JSON
- [x] `.vscode/settings.json`에 `input/`, `output/`, `logs/`, `matters/`, `runs/` search/watch 제외 설정 추가
- [x] `.claude/settings.json`에서 inline Python hook 제거
- [x] `.claude/hooks/pretooluse-guard.py` 단위 테스트 추가
- [x] 기존 approved 직접 write 차단 유지
- [x] workspace 경로 문서가 root legacy 경로와 충돌하지 않음
- [x] `.gitignore`가 workspace local-only 산출물을 보호
- [x] `python3 -m pytest -q` 통과

## 8. Rollback 계획

### Batch 1

`.vscode/settings.json`의 exclude block만 되돌리면 된다.

### Batch 2

`.claude/settings.json`을 이전 inline hook으로 되돌리거나, `pretooluse-guard.py` command를 일시적으로 제거한다. 보안 guard 약화가 생기므로 rollback 시 반드시 별도 메모를 남긴다.

### Batch 3

새 `contract-review/workspace/` 디렉터리와 문서 변경을 되돌리면 된다. bridge 방식이므로 legacy `input/`, `output/`, `matters/`, `library/runs/`가 남아 있어 data migration rollback은 필요하지 않다.

## 9. 최종 권장안

지금 바로 구현한다면 Batch 1과 Batch 2까지만 먼저 진행하는 것이 가장 좋다. Batch 3은 효과보다 경로 호환성 리스크가 크므로, helper와 문서 bridge를 먼저 설계하고 실제 default output 위치 변경은 별도 승인 후 진행한다.

## 10. 후속 런타임 연결 기록

2026-05-27 후속 세션에서 `.claude/scripts/load-domain-references.sh`의 기본 trace root를 workspace helper에 연결했다.

- `--trace-dir`를 명시한 호출은 기존처럼 caller 지정 경로를 그대로 사용한다.
- 명시 trace dir이 없으면 `$CRA_RUNS_DIR/sessions/{session_id}/loaded.json`을 사용한다.
- `contract-review/workspace/runs/`가 있으면 새 기본 경로가 된다.
- workspace가 아직 없고 legacy `contract-review/library/runs/`가 있으면 legacy 경로로 fallback한다.
- 기존 trace 파일은 이동하지 않는다.
