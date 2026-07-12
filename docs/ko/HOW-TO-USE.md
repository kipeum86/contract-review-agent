# 사용 방법

[English](../en/HOW-TO-USE.md) | [한국어](./HOW-TO-USE.md)

> **어느 단계에서든 막히면** Claude Code에게 바로 문의하세요. 터미널이나 VS Code 확장 프로그램 채팅 패널에서 질문해도 되고, 다른 LLM에 스크린샷을 붙여넣어 도움을 받아도 됩니다. 대부분의 경우 단계별로 명확하게 안내해 줍니다.

## 환경

이 프로젝트는 다음 환경에서 구축하고 테스트했습니다:

| 구성 요소 | 내용 |
|-----------|------|
| 에디터 | **VS Code** |
| AI 인터페이스 | **Claude Code** (Anthropic의 Claude용 CLI로, VS Code 통합 터미널에서 실행하거나 채팅 패널이 있는 VS Code 확장 프로그램으로 사용할 수 있습니다) |
| 운영체제 | Windows 11 / macOS |
| 셸 | Bash (Windows에서는 Git Bash, macOS에서는 기본 Terminal) |

Claude Code는 대화형 에이전트로 동작합니다. 자연어 지시나 슬래시 명령을 입력하면 로컬 프로젝트 디렉터리 내에서 파일을 읽고 쓰며, 스크립트를 실행하고, 서브 에이전트를 조율합니다.

**VS Code에서 Claude Code와 상호작용하는 두 가지 방법:**

| 방법 | 시작 방법 | 적합한 경우 |
|------|-----------|-------------|
| **터미널 CLI** | VS Code 터미널을 열고 `claude` 입력 | 고급 사용자, 스크립팅, 상세 출력 확인 |
| **VS Code 확장 프로그램** | Claude Code 확장 프로그램 설치 후 채팅 패널 열기 (`Ctrl+Shift+P` → "Claude Code: Open") | 입문자, 빠른 질의, 시각적 워크플로 |

두 방식 모두 동일한 슬래시 명령과 자연어를 지원하므로, 편의에 따라 선택하면 됩니다. 이 가이드의 예시는 두 인터페이스에서 동일하게 작동합니다.

> Claude Code를 사용하지 않는 환경에서는 `/ingest`, `/contract-review` 같은 슬래시 명령이 그대로 작동하지 않습니다. 사용 중인 AI 환경에 맞게 프롬프트를 조정하여 사용해야 합니다.

---

## 사전 요구사항

| 요구사항 | 버전 | 참고 |
|----------|------|------|
| **Claude Code** | Latest | [설치 가이드](https://docs.anthropic.com/en/docs/claude-code) |
| **Python** | 3.10+ | 파싱/생성 스크립트에 필요 |
| **Node.js** | 18+ | 프로젝트 도구에 필요 |
| **PyYAML** | Latest | `pip install pyyaml` |
| **jq** | 1.6+ | `brew install jq` (macOS) · `apt-get install jq` (Linux). 도메인 레퍼런스 forced-load hook에서 사용 |
| **shasum / sha256sum** | — | macOS 및 대부분의 Linux 배포판에 기본 포함 |

> **왜 jq가 필요한가요?** `.claude/hooks/inject-domain-references.sh` hook과 `.claude/scripts/load-domain-references.sh` loader가 hook의 stdin JSON을 파싱하고, `additionalContext` 주입 페이로드를 생성하고, 포렌식 트레이스 파일(기본 `contract-review/workspace/runs/sessions/*/loaded.json`, legacy fallback `contract-review/library/runs/sessions/*/loaded.json`)을 쓸 때 `jq`를 사용합니다. `jq`가 없으면 hook은 오류만 남기고 컨텍스트 주입을 하지 못하며, loader/pre-pipeline 직접 호출은 non-zero로 실패합니다. 검토 워크플로를 실행하기 전에 설치해야 digest trace와 section load가 정상 동작합니다.

선택 설치 항목:

| 패키지 | 용도 |
|--------|------|
| `pymupdf` 또는 `pypdf` | PDF 파일 지원 |
| `pandoc` | DOCX 변환 품질 향상 |

---

## 설치

```bash
git clone <repository-url> contract-review-agent
cd contract-review-agent
npm install
python -m pip install pyyaml

# jq 설치 확인 (forced-load hook이 사용)
command -v jq || echo "jq 설치: brew install jq  (macOS)  |  apt-get install jq  (Linux)"

# hook/loader 스크립트 실행 권한 확인 (git이 보존하지만 만약을 위해 한 번만 실행)
chmod +x .claude/hooks/*.sh .claude/scripts/*.sh
```

### 설치 후 Claude Code 첫 세션

훅은 트래킹되는 `.claude/settings.json`에 등록되어 있습니다. 이 리포에서
Claude Code를 처음 실행하면 프로젝트 훅 구성(`UserPromptSubmit` 컨텍스트
주입기 + `PreToolUse` 쓰기 가드)을 검토·승인하라는 안내가 표시됩니다.
승인해 주세요 — 주입기는 워크플로별 레퍼런스 로딩 지시를 LLM 컨텍스트에
전달하고, 가드는 `contract-review/library/approved/`로의 실수 직접 쓰기를
차단합니다. 거부하면 review-agent 내부의 2차 방어선(Pre-Pipeline 0 loader)은
여전히 동작하지만 기본 방어층은 비활성화됩니다. 개인 설정은 gitignore되는
`.claude/settings.local.json`에 두세요.

---

## 단계별 설정

### 1. 실무에 맞게 정책 커스터마이즈하기

[`contract-review/library/policies/`](../../contract-review/library/policies/) 아래의 정책 파일은 에이전트가 계약을 분류하고 검토하는 방식을 제어합니다. 기본값은 27개 계약군을 폭넓게 포괄하도록 되어 있지만, 실제 업무 영역에 맞게 조정하는 것이 좋습니다.

Claude Code 터미널이나 확장 프로그램 채팅 패널에서 이렇게 요청하세요:

```text
내가 다루는 계약 유형에 맞게 policy 파일을 다시 작성해줘.

내가 다루는 계약 유형:
- NDA, license, IP assignment, content distribution, game development, ...
```

Claude Code는 계약군, 조항 분류 체계, 검토 모드, 검색 규칙 등을 포함한 여섯 개 정책 파일을 한 번에 다시 작성할 수 있습니다. 필요하면 아래 [정책 파일](#policy-files) 섹션을 보고 YAML 파일을 직접 수정해도 됩니다.

> **팁 — 아직 정책을 어떻게 잡아야 할지 모르겠다면?** 먼저 2단계로 가세요. 사내 템플릿을 ingest한 다음, 다시 돌아와 Claude Code에게 이미 ingest된 계약서를 기준으로 정책을 맞춰 달라고 하세요:
>
> ```text
> ingest된 계약서 유형에 맞게 policies파일 수정해줘.
> Rewrite policies to match the contract types already in my library.
> ```
>
> 정책 명세를 처음부터 쓰는 것보다, 실제 계약서를 기준으로 설정을 맞추는 편이 더 쉬운 경우가 많습니다.

### 2. 라이브러리 초기 문서 등록

사내 템플릿과 참고 계약서를 [`contract-review/library/inbox/raw/`](../../contract-review/library/inbox/raw/)에 넣은 뒤, 터미널이나 확장 프로그램 채팅에서 다음을 입력하세요:

```text
/ingest
```

| 가이드라인 | 내용 |
|-----------|------|
| 분량 | 초기 구축 시 **50개 문서 이하**를 권장합니다. 이후에는 언제든 추가할 수 있습니다. |
| 형식 | DOCX, PDF, Markdown |
| 구조 | 파일 하나당 계약서 하나 |
| 프라이버시 | 모든 파일은 로컬 머신에만 보관되며, 외부로 전송되거나 공유되지 않습니다 |

템플릿과 선례는 기본적으로 **자동 승인**됩니다. 플레이북과 코멘트 뱅크는 사람의 확인이 필요합니다. [`approval-rules.yaml`](../../contract-review/library/policies/approval-rules.yaml)을 참고하세요.

### 3. 계약서 검토하기

검토할 계약서를 [`contract-review/workspace/input/`](../../contract-review/workspace/input/) 폴더에 넣는 것을 권장합니다. 기존 방식대로 프로젝트 루트의 [`input/`](../../input/) 폴더에 넣어도 bridge 기간 동안 계속 인식됩니다. 그 뒤 터미널이나 확장 프로그램 채팅에서 다음을 입력하세요:

```text
/contract-review
```

결과물(레드라인 DOCX, 분석 보고서 등)은 기본적으로 [`contract-review/workspace/output/`](../../contract-review/workspace/output/) 폴더에 저장됩니다. 기존 워크플로의 [`output/`](../../output/) 폴더도 계속 지원됩니다.

workspace 폴더와 기존 `input/` / `output/` 폴더는 모두 버전 관리에서 제외되므로 계약 파일이 로컬 PC 밖으로 나가지 않습니다.

자연어도 사용할 수 있습니다:

```text
이 SaaS 계약서 moderate 모드로 검토해줘.
Review this NDA strictly.
```

### 4. 수정본 재검토하기

상대방이 수정본을 보내오면 `contract-review/workspace/input/` 또는 기존 `input/`에 넣고 다음을 입력하세요:

```text
/rereview
```

에이전트는 새 초안을 이전 검토 라운드와 비교하여 변경된 사항, 수용된 의견, 새로 발생한 쟁점을 정리한 **delta report**를 생성합니다.

### 5. 기타 명령어

| 명령어 | 동작 |
|--------|------|
| `/library` | 라이브러리 자산을 검색, 조회, 표시, 폐기, 보관합니다 |
| `/export-clean` | 레드라인 DOCX에서 `[INTERNAL]` 코멘트를 제거해 상대방 공유용으로 만듭니다 |
| `/resume` | 중단된 파이프라인을 멈춘 지점부터 재개합니다 |
| `/draft` | 새 계약서를 초안 작성합니다 |

자연어 입력도 가능하며, 오케스트레이터가 적절한 워크플로로 자동으로 연결합니다.

---

## VS Code에서의 일반적인 워크플로

보통 세션은 다음과 같이 진행됩니다:

### 옵션 A: 터미널 CLI

1. VS Code에서 **프로젝트를 엽니다**.
2. **통합 터미널을 엽니다** (`` Ctrl+` `` 또는 `View > Terminal`).
3. 터미널에서 `claude`를 입력해 **Claude Code를 시작합니다**.
4. 슬래시 명령이나 자연어로, 영어 또는 한국어로 **지시를 입력합니다**.
5. **Claude Code가 작업하는 과정을 확인합니다**. 터미널에서 파일을 읽고, 스크립트를 실행하고, 결과를 쓰고, 진행 상황을 보고합니다.
6. **결과를 검토합니다**. VS Code에서 출력 파일을 열어 레드라인, 보고서, 분석을 확인합니다.
7. **반복합니다**. 후속 질문을 하거나, 수정을 요청하거나, 다음 단계로 진행합니다.

### 옵션 B: VS Code 확장 프로그램 (채팅 패널)

1. VS Code에서 **프로젝트를 엽니다**.
2. **Claude Code 패널을 엽니다** (`Ctrl+Shift+P` → "Claude Code: Open", 또는 사이드바의 Claude 아이콘 클릭).
3. 채팅 입력창에 슬래시 명령이나 자연어로, 영어 또는 한국어로 **지시를 입력합니다**.
4. **Claude Code가 작업하는 과정을 확인합니다**. 진행 상황과 결과가 채팅 패널에 직접 표시됩니다.
5. **결과를 검토합니다**. 출력 파일은 채팅에서 클릭할 수 있고, `contract-review/workspace/output/` 또는 기존 `output/` 폴더에서 직접 열 수도 있습니다.
6. **반복합니다**. 같은 패널에서 계속 대화를 이어가면 됩니다.

두 방식의 실행 결과는 동일합니다. 처음 사용하는 경우에는 별도의 터미널 설정이 필요 없는 확장 프로그램 패널이 더 접근하기 쉽습니다.

---

<a id="policy-files"></a>

## 정책 파일

[`contract-review/library/policies/`](../../contract-review/library/policies/) 아래의 여섯 개 YAML 파일이 에이전트의 동작을 제어합니다:

| 파일 | 제어 대상 | 수정 여부 |
|------|-----------|-----------|
| `contract-families.yaml` | 지원하는 계약 유형 | **예** |
| `clause-taxonomy.yaml` | 조항 분류 체계 | **예** |
| `review-mode.yaml` | strict / moderate / loose 검토 설정 | **예** |
| `approval-rules.yaml` | 자동 승인 토글과 자산 유형별 규칙 | **예** |
| `retrieval-priority.yaml` | 검색 랭킹, 친화 그룹 | 선택 |
| `metadata-schema.yaml` | 메타데이터 필드 정의 | 선택 |

이 파일들은 에이전트에게 **읽기 전용**입니다. 수정은 사용자(또는 사용자의 요청을 받은 Claude Code)만 할 수 있습니다.

---

## 팁

- **언어**: 에이전트는 영어와 한국어를 모두 지원하며, 입력 언어에 맞춰 응답합니다.
- **검토 모드**: 기본값(`moderate`)은 검토 시마다 변경할 수 있습니다. `"엄격하게 검토해줘"` 또는 `"do a loose review"`와 같이 지정하면 됩니다.
- **파이프라인 재개**: 검토가 중단된 경우(터미널 종료, 오류 등) `/resume`을 입력해 중단 지점부터 이어서 실행할 수 있습니다.
- **대상자 방화벽**: 내부 전략 코멘트(`[INTERNAL]`)는 외부 공유용 산출물에 포함되지 않습니다. 상대방에게 안전하게 공유할 수 있는 버전은 `/export-clean`으로 생성하세요.
