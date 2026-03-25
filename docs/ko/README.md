<div align="center">

# Contract Review Agent

### Claude Code 기반 AI 계약 검토 파이프라인

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../../LICENSE)
[![Claude Code](https://img.shields.io/badge/Built_with-Claude_Code-blueviolet)](https://claude.ai/claude-code)
[![Node.js](https://img.shields.io/badge/Node.js-18%2B-green)](https://nodejs.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)](https://www.python.org/)

[English](../../README.md)&ensp;·&ensp;[한국어](./README.md)

---

계약서를 입력하면 **추적 변경이 적용된 레드라인 Word 파일, 여백 코멘트(내부 전략용 + 외부 공유용),
전체 분석 보고서, 협상 권고안**을 모두 DOCX 형식으로 생성해 반환합니다.

**최종적인 법률 판단은 사람이 내립니다.**

</div>

> [!IMPORTANT]
> **시작 전에 꼭 읽어주세요:**
> - **[면책사항](./DISCLAIMER.md)** — 중요한 한계와 데이터 보안 관련 고려사항
> - **[사용 방법](./HOW-TO-USE.md)** — 설정, 환경, 단계별 안내

---

## 예시 산출물

<table>
<tr>
<th width="120">언어</th>
<th>레드라인 DOCX</th>
<th>검토 보고서</th>
</tr>
<tr>
<td><strong>English</strong></td>
<td><a href="https://docs.google.com/document/d/1KIIW5lY-H-LddPgUGWLiA1kcFQxbJECq/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true">Redlined DOCX</a></td>
<td><a href="https://docs.google.com/document/d/1QinVyQHdyb5VxxkjpmFVdVYgFoxgwX0e/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true">Client Memo</a></td>
</tr>
<tr>
<td><strong>한국어</strong></td>
<td><a href="https://docs.google.com/document/d/1g6AFUqiJp8fCb_3NayHfNhqRDFAq6c0Q/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true">레드라인 DOCX</a></td>
<td><a href="https://docs.google.com/document/d/1y_iMJBNwlvubzs1wfcLq1q8lNL3pQxXQ/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true">검토 의견서</a></td>
</tr>
</table>

---

## 주요 기능

<table>
<tr>
<td width="80" align="center"><h3>1</h3></td>
<td>
<strong>Ingest</strong><br/>
사내 템플릿, 선례, 플레이북을 라이브러리로 등록하여 검색 가능한 형태로 구축합니다
</td>
</tr>
<tr>
<td align="center"><h3>2</h3></td>
<td>
<strong>Review</strong><br/>
상대방 초안을 사내 기준과 조항별로 비교·분석합니다
</td>
</tr>
<tr>
<td align="center"><h3>3</h3></td>
<td>
<strong>Re-review</strong><br/>
협상 후 수정본이 접수되었을 때 변경 사항을 분석합니다
</td>
</tr>
<tr>
<td align="center"><h3>4</h3></td>
<td>
<strong>Draft</strong><br/>
인터뷰 방식으로 계약서 초안을 작성하고 자체 검토를 수행합니다
</td>
</tr>
</table>

> 모든 처리는 **로컬 파일시스템 내에서만** 이루어집니다. 외부 서버나 벡터 데이터베이스를 사용하지 않으며, 데이터가 사용자의 컴퓨터 밖으로 나가지 않습니다.

---

## 빠른 시작

### Step 1 — 설치

```bash
git clone https://github.com/lowtidebuild/contract-review-agent.git
cd contract-review-agent
npm install
python -m pip install pyyaml
```

### Step 2 — 실무에 맞게 정책 커스터마이즈하기

[`contract-review/library/policies/`](../../contract-review/library/policies/) 아래의 정책 파일은 에이전트가 계약을 분류하고 검토하는 방식을 제어합니다. 기본값은 27개 계약군을 폭넓게 포괄하도록 되어 있지만, 실제로는 자신의 업무에 맞게 조정하는 것이 좋습니다.

터미널이나 확장 프로그램 채팅 패널에서 Claude Code에게 바로 이렇게 요청하면 됩니다:

```text
내가 다루는 계약 유형에 맞게 policy 파일을 다시 작성해줘.

내가 다루는 계약 유형:
- NDA, license, IP assignment, content distribution, game development, ...
```

Claude Code는 계약군, 조항 분류 체계, 검토 모드, 검색 규칙 등을 포함한 여섯 개 정책 파일을 한 번에 다시 작성할 수 있습니다. 필요하면 [YAML 파일을 직접 수정](#-정책-파일)해도 됩니다.

> [!TIP]
> **아직 정책을 어떻게 잡아야 할지 모르겠다면?** 먼저 Step 3으로 가세요. 사내 템플릿을 ingest한 다음, 다시 돌아와 Claude Code에게 이미 ingest된 계약서를 기준으로 정책을 맞춰 달라고 하세요:
>
> ```text
> ingest된 계약서 유형에 맞게 policies파일 수정해줘.
> Rewrite policies to match the contract types already in my library.
> ```
>
> 정책 명세를 처음부터 작성하는 것보다, 실제 계약서를 기준으로 설정을 맞추는 편이 더 쉬운 경우가 많습니다.

### Step 3 — 라이브러리 초기 문서 등록

사내 템플릿과 참고 계약서를 [`contract-review/library/inbox/raw/`](../../contract-review/library/inbox/raw/)에 넣은 뒤, 터미널이나 확장 프로그램 채팅에서 다음을 입력하세요:

```text
/ingest
```

| 가이드라인 | 내용 |
|-----------|------|
| 분량 | 초기 구축 시 **50개 문서 이하**를 권장합니다. 이후에는 언제든 추가할 수 있습니다. |
| 형식 | DOCX, PDF, Markdown |
| 구조 | 파일 하나당 계약서 하나 |
| 프라이버시 | 등록한 파일은 로컬 PC에만 보관되며, 외부로 전송되거나 공유되지 않습니다 |

템플릿과 선례는 기본적으로 **자동 승인**됩니다. 플레이북과 코멘트 뱅크는 여전히 사람의 확인이 필요합니다. [`approval-rules.yaml`](../../contract-review/library/policies/approval-rules.yaml)을 참고하세요.

### Step 4 — 계약서 검토하기

검토할 계약서를 프로젝트 루트의 [`input/`](../../input/) 폴더에 넣은 뒤 다음을 입력하세요:

```text
/contract-review
```

결과물(레드라인 DOCX, 분석 보고서 등)은 [`output/`](../../output/) 폴더에 저장됩니다.

`input/`과 `output/`은 모두 버전 관리에서 제외되어 있으므로 계약 파일이 로컬 PC 밖으로 나가지 않습니다.

자연어도 사용할 수 있습니다:

```text
이 SaaS 계약서 moderate 모드로 검토해줘.
Review this NDA strictly.
```

---

## 명령어

| 명령어 | 동작 |
|--------|------|
| `/ingest` | 문서를 라이브러리에 ingest합니다 |
| `/contract-review` | 상대방 계약서를 검토합니다 |
| `/rereview` | 이전 라운드와 비교해 수정본을 다시 검토합니다 |
| `/library` | 라이브러리 자산을 검색, 조회, 표시, 폐기, 보관합니다 |
| `/export-clean` | 레드라인 DOCX에서 `[INTERNAL]` 코멘트를 제거합니다 |
| `/resume` | 중단된 파이프라인을 이어서 실행합니다 |
| `/draft` | 새 계약서를 초안 작성합니다 |

자연어도 지원되며, 오케스트레이터가 적절한 워크플로로 라우팅합니다.

---

## 동작 방식

### 검토 파이프라인

```
  대상 계약서 (DOCX/PDF)
      |
      v
  +-----------------------+
  |  파싱 및 분할          |  조항 단위로 분리
  +-----------------------+
      |
      v
  +-----------------------+
  |  라이브러리 검색        |  사내 조항과 매칭
  +-----------------------+
      |
      v
  +-----------------------+
  |  조항별 비교           |  리스크 등급 + 갭 분석
  +-----------------------+
      |
      v
  +-----------------------+
  |  레드라인 생성          |  추적 변경 + 코멘트
  +-----------------------+
      |
      +------+------+------+
      |      |      |
      v      v      v
    내부용   외부용   검토
   레드라인  정리본  보고서
    DOCX    DOCX    DOCX
```

<details>
<summary><strong>결과물 예시</strong> — 실제 산출물을 확인하세요</summary>
<br/>

| 산출물 | 언어 | 링크 |
|--------|------|------|
| Client Memo | English | [Google Docs에서 보기](https://docs.google.com/document/d/1QinVyQHdyb5VxxkjpmFVdVYgFoxgwX0e/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true) |
| Contract Redlined | English | [Google Docs에서 보기](https://docs.google.com/document/d/1KIIW5lY-H-LddPgUGWLiA1kcFQxbJECq/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true) |
| 검토 의견서 | 한국어 | [Google Docs에서 보기](https://docs.google.com/document/d/1y_iMJBNwlvubzs1wfcLq1q8lNL3pQxXQ/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true) |
| 계약서 검토본 | 한국어 | [Google Docs에서 보기](https://docs.google.com/document/d/1g6AFUqiJp8fCb_3NayHfNhqRDFAq6c0Q/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true) |

</details>

### 검토 모드

| 모드 | 사용 시점 | 레드라인 범위 |
|------|-----------|---------------|
| **`strict`** | 고액 거래, M&A, 협상 우위에 있을 때 | 모든 이탈 사항 |
| **`moderate`** | 일반적인 상거래 계약 | Critical + High risk |
| **`loose`** | 협상 여지가 제한적이거나 신속한 검토가 필요한 경우, LOI/MOU | Critical only |

기본값은 `moderate`입니다. 검토 시마다 `"이거 엄격하게 검토해줘"` 또는 `"do a loose review"`와 같이 지정해 변경할 수 있습니다.

### 라이브러리 인제스트

```
inbox/raw/  ──>  validate  ──>  classify  ──>  segment  ──>  approved/
                                                   \
                                                    └──>  quarantine/  (실패 시)
```

템플릿과 선례는 기본적으로 자동 승인 처리되므로, 별도의 수동 승인 절차가 필요하지 않습니다.

### 참조 소스 추가하기

계약서 템플릿 외에 **법령, 판례, 로펌 해설, 학술 논문** 등의 참조 소스를 Grade 기반으로 분류하여 라이브러리에 등록할 수 있습니다. 등록된 참조 소스는 계약 검토 시 맥락 정보로 활용됩니다.

1. 파일(PDF, DOCX 등)을 `contract-review/library/inbox/raw/`에 넣습니다
2. 에이전트에게 알려줍니다: `/ingest` 또는 "참조 자료 넣었어"
3. 에이전트가 자동으로:
   - 구조화된 Markdown으로 변환
   - 소스 등급(A/B/C) 자동 판별
   - 메타데이터(frontmatter) 생성
   - 적절한 `library/grade-{a,b,c}/` 폴더에 배치
   - 검색 인덱스 업데이트

| 등급 | 소스 유형 | 신뢰 수준 |
|------|-----------|-----------|
| **A** | 법령, 시행령, 정부 가이드라인, KVCA 표준계약서 | 권위적 (authoritative) |
| **B** | 판례, 로펌 뉴스레터, KVCA 해설서, 실무 가이드 | 검증됨 (verified) |
| **C** | 학술 논문, 세미나 자료, 학회 발표 | 참고용 (reference) |
| **D** | 뉴스, AI 요약, 위키 | 제외 (거부) |

> **참고:** 파일을 넣는 것만으로는 자동 처리되지 않습니다.
> `/ingest`를 실행하거나 에이전트에게 알려줘야(예: "inbox에 자료 넣었어")
> 파싱 파이프라인이 시작됩니다.

### 검색 전략

임베딩이나 벡터 데이터베이스를 사용하지 않습니다. 검색은 다음 단계로 이루어집니다:

1. **결정적 필터링** — 계약군, 조항 유형, 준거법 기준으로 JSON 인덱스를 필터링
2. **후보 축소** — 후보 수가 임계값을 넘으면 구조적 속성으로 추가 매칭
3. **LLM 판단** — 필터링된 집합에서 최적 후보 선택
4. **우선순위 랭킹** — [`retrieval-priority.yaml`](../../contract-review/library/policies/retrieval-priority.yaml)로 제어

모든 매칭 경로를 추적할 수 있어 완전한 감사(audit)가 가능합니다.

---

## 저장소 구조

```
.
├── input/                       # 검토할 계약서를 여기에 넣습니다 (gitignored)
├── output/                      # 검토 결과가 여기에 생성됩니다 (gitignored)
│
├── .claude/
│   ├── agents/                  # 서브 에이전트: ingestion, review, drafting
│   ├── skills/                  # 스킬: 파싱, 인덱싱, 검증, 레드라이닝 등
│   └── settings.json
│
├── contract-review/
│   ├── library/
│   │   ├── inbox/raw/           # 원본 템플릿을 여기에 넣습니다 (gitignored)
│   │   ├── inbox/sidecars/      # 보조 메타데이터 (gitignored)
│   │   ├── staging/             # 검증 완료, 승인 대기 (gitignored)
│   │   ├── approved/            # 게시된 자산 (gitignored)
│   │   ├── quarantine/          # 실패 / 거절된 항목 (gitignored)
│   │   ├── grade-a/             # Grade A 참조 소스 (법령, 규정)
│   │   ├── grade-b/             # Grade B 참조 소스 (판례, 해설)
│   │   ├── grade-c/             # Grade C 참조 소스 (학술, 세미나)
│   │   ├── indexes/             # JSON 인덱스 (자동 관리)
│   │   └── policies/            # YAML 설정 파일 (사용자 관리)
│   └── matters/                 # 딜별 작업 디렉터리 (gitignored)
│
├── docs/
├── CLAUDE.md                    # 오케스트레이터 라우팅 규칙
└── package.json
```

---

## 정책 파일

[`contract-review/library/policies/`](../../contract-review/library/policies/) 아래의 여섯 개 YAML 파일이 에이전트의 동작을 제어합니다. 이 파일들이 가장 중요한 커스터마이즈 지점입니다.

| 파일 | 제어 대상 | 수정 여부 |
|------|-----------|-----------|
| `contract-families.yaml` | 지원하는 계약 유형 (27개 계약군: NDA, SPA, 게임 개발, 퍼블리싱 등) | **예** |
| `clause-taxonomy.yaml` | 조항 분류 체계 (M&A, IP, 콘텐츠, 게임 개발 카테고리 등) | **예** |
| `review-mode.yaml` | strict / moderate / loose 검토 설정과 딜 유형별 권장 모드 | **예** |
| `approval-rules.yaml` | 자동 승인 토글과 자산 유형별 규칙 | **예** |
| `retrieval-priority.yaml` | 검색 랭킹, 계약군 간 매칭을 위한 친화 그룹 | 선택 |
| `metadata-schema.yaml` | 메타데이터 필드 정의 (이중언어 지원, 산업 태그 등) | 선택 |

정책 파일은 에이전트에게 **읽기 전용**입니다. 수정은 사용자만 하며, `indexes/`는 에이전트가 자동으로 관리합니다.

---

## 사전 요구사항

| 요구사항 | 버전 |
|----------|------|
| Python | 3.10+ |
| Node.js | 18+ |
| PyYAML | `pip install pyyaml` |

선택 사항: `pymupdf` 또는 `pypdf` (PDF 지원), `pandoc` (향상된 DOCX 변환).

---

## 아키텍처

에이전트는 오케스트레이터(`CLAUDE.md`)가 조정하는 세 개의 전문 서브 에이전트로 구성됩니다:

```
                    ┌─────────────────────┐
                    │    Orchestrator      │
                    │    (CLAUDE.md)       │
                    └──────┬──────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            v              v              v
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │  Ingestion │  │   Review   │  │  Drafting  │
   │   Agent    │  │   Agent    │  │   Agent    │
   └────────────┘  └────────────┘  └────────────┘
```

<details>
<summary><strong>주요 아키텍처 설계 원칙</strong></summary>
<br/>

- **임베딩 / 벡터 DB 미사용** — 검색은 결정적 JSON 인덱스 필터링 + LLM 판단으로 처리합니다
- **파이프라인 상태 저장** — 각 단계가 `pipeline-state.json`을 기록하므로 중단 후 재개가 가능합니다
- **대상자 방화벽** — `[INTERNAL]`과 `[EXTERNAL]` 코멘트 스트림을 모든 단계에서 엄격히 분리합니다
- **파일 기반 데이터 전달** — 대용량 페이로드는 인라인이 아닌 `matters/` 또는 `library/runs/` 하위 파일로 전달합니다

</details>

---

## 설계 원칙

| 원칙 | 설명 |
|------|------|
| **사람이 최종 결정한다** | 에이전트는 제안하고, 판단은 사람이 합니다 |
| **로컬 처리 및 감사 가능성** | 모든 데이터는 로컬 디스크에 저장되며, 모든 산출물을 직접 검토할 수 있습니다 |
| **대상자 방화벽** | 내부 전략 정보가 외부 공유용 산출물에 포함되지 않습니다 |
| **재개 가능성** | 파이프라인 상태를 저장하므로 중단 후 이어서 실행할 수 있습니다 |
| **업종 중립성** | 도메인 특화 설정은 코드가 아닌 정책 파일로 관리합니다 |

---

## 로드맵

| 단계 | 범위 |
|------|------|
| **v1-alpha** | 인제스트, 라이브러리 관리, 검토(JSON/MD 보고서), 파이프라인 상태, 슬래시 명령 |
| **v1-beta** | DOCX 레드라인/코멘트, 외부 공유용 clean export, 재검토 delta 보고서 |
| **v2** | 계약서 초안 작성, 표 단위 레드라인, 플레이북 자동 제안, 임베딩 검색 |

---

## 참고 자료

- [사용 방법](./HOW-TO-USE.md) — 설정 가이드와 단계별 워크스루
- [CLAUDE.md](../../CLAUDE.md) — 오케스트레이터 라우팅과 안전 규칙
- [구현 노트](./implementation-notes.md) — 저장소 구현 세부사항

## 라이선스

MIT — 자세한 내용은 [LICENSE](../../LICENSE)를 참고하세요.
