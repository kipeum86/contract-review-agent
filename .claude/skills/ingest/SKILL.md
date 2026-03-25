---
name: ingest
description: >
  library/inbox/에 넣은 외부 참조 소스 파일(PDF, DOCX 등)을 자동으로
  Markdown 변환, Grade 판별, frontmatter 생성, 폴더 배치, 인덱스 업데이트까지
  원스텝으로 처리한다. /ingest로 트리거.
---

# Source Ingest

`contract-review/library/inbox/`에 참조 소스 파일을 넣고 `/ingest`를 실행하면 자동으로 처리한다.

> **참고**: 이 스킬은 **참조 소스**(법령, 판례, 해설 등)를 Grade 기반으로 분류·배치한다.
> 계약서 템플릿/선례 ingestion은 기존 10단계 파이프라인(ingestion-agent)을 사용한다.

## Trigger

- `/ingest` — inbox 전체 처리
- 사용자가 "소스 추가", "자료 넣었어", "ingest", "inbox" 등 요청 시

---

## Workflow

```
library/inbox/ 에 파일 드롭
  │
  ├─ Step 1: 파일 스캔
  ├─ Step 2: Markdown 변환
  ├─ Step 3: Grade 자동 판별
  ├─ Step 4: Frontmatter 생성
  ├─ Step 5: 목적 폴더로 이동
  └─ Step 6: 인덱스 업데이트
```

### Step 1: Inbox 스캔

```
inbox/ 내 모든 파일을 Glob으로 탐색 (inbox/raw/ 포함)
지원 포맷: .pdf, .docx, .pptx, .xlsx, .html, .md, .txt
비지원: .hwp, .hwpx → 유저에게 "PDF/DOCX 변환 후 다시 넣어주세요" 안내
```

- 파일이 0개면 "inbox가 비어 있습니다" 안내 후 종료
- 하위 폴더 안의 파일도 재귀 탐색
- `.gitkeep`, `_processed/`, `_failed/`, `sidecars/` 내 파일은 제외

**계약서 템플릿 vs 참조 소스 구분:**
- 사용자가 명시적으로 "소스 추가", "참조 자료" 등 참조 소스임을 언급하면 이 스킬로 처리
- 사용자가 "템플릿 등록", "계약서 추가" 등 계약서임을 언급하면 기존 ingestion-agent로 라우팅
- 불분명한 경우 사용자에게 질문:
  > "이 파일은 참조 소스(법령/판례/해설)인가요, 아니면 계약서 템플릿인가요?"

### Step 2: Markdown 변환

| 입력 포맷 | 변환 방법 |
|----------|----------|
| `.pdf` | `mcp__markitdown__convert_to_markdown` (uri: `file:///절대경로`) |
| `.docx` | `mcp__markitdown__convert_to_markdown` |
| `.pptx`, `.xlsx`, `.html` | `mcp__markitdown__convert_to_markdown` |
| `.md`, `.txt` | 변환 불필요, 그대로 사용 |

**변환 실패 시:** 해당 파일을 `library/inbox/_failed/`로 이동 + 유저에게 실패 사유 안내

### Step 3: Grade 자동 판별

변환된 Markdown 내용을 분석하여 Grade를 판별한다.

#### 판별 규칙 (우선순위 순)

**Grade A — 공식 1차 소스 (법령, 규정, 공식 가이드라인):**

| 시그널 | 예시 |
|--------|------|
| 법률 번호 패턴 | `법률 제XXXXX호`, `대통령령 제XXXXX호` |
| 고시/훈령 번호 | `고시 제XXXX-XXX호`, `훈령 제XXX호` |
| 출처 도메인 | law.go.kr, elaw.klri.re.kr |
| 발행 기관 | 법무부, 금융위원회, 공정거래위원회, 중소벤처기업부, 금융감독원 |
| 핵심 법률 | 상법, 자본시장법, 민법, 공정거래법, 외국인투자촉진법, 벤처투자법 |
| 표준약관/표준계약서 | 공정위 승인 표준약관, 정부기관 발행 표준계약서 |
| 가이드라인 패턴 | "안내서", "가이드라인", "해설서" + 정부 기관명 |

**Grade B — 2차 소스 (판례, 로펌 해설, 업계 표준):**

| 시그널 | 예시 |
|--------|------|
| 판례 번호 | `대법원 20XXdaXXXXX`, `서울고등법원 20XXnaXXXXX` |
| 결정/의결 번호 | `의결 제20XX-XXX호`, `공정위 시정명령` |
| 로펌 레터헤드/도메인 | kimchang.com, bkl.co.kr, leeko.com, yulchon.com, shinkim.com |
| 뉴스레터 형식 | "법률 뉴스레터", "Client Alert", "Legal Update" |
| KVCA/업계 해설 | KVCA 표준계약서 해설서, 벤처기업협회 가이드 |
| 실무 해설서 | "계약실무", "법률실무", "거래구조 해설" |
| 법조 칼럼 | 법률신문, 대한변호사협회 |

**Grade C — 학술/참고:**

| 시그널 | 예시 |
|--------|------|
| 학술지 형식 | 초록/Abstract, 참고문헌/References 섹션 |
| 학술 DB 출처 | KCI, RISS, SSRN, Google Scholar |
| 저널명 패턴 | "법학연구", "상사법연구", "기업법연구", "Law Review" |
| 학위 논문 | 석사/박사 학위논문, thesis/dissertation |
| 세미나/컨퍼런스 | 발표자료, 토론문, 학회 proceedings |

**Grade D — 제외 (ingest 거부):**
- 일반 뉴스 기사, AI 생성 요약, 위키, 소셜 미디어, 블로그
- 거부 시 안내: "이 자료는 신뢰도가 낮아 라이브러리에 포함할 수 없습니다 (Grade D)."

**판별 불가:**
- 위 시그널이 어디에도 매칭되지 않으면 유저에게 질문:
  > "이 파일의 성격을 판별하지 못했습니다: `{filename}`
  > 내용 일부: {첫 200자}
  > Grade를 지정해주세요: A (법령/공식), B (판례/로펌), C (학술)"
- 유저 응답 후 처리 계속

### Step 4: Frontmatter 생성

변환된 .md 파일에 YAML frontmatter를 자동 생성한다.

```yaml
---
# === 식별 정보 ===
source_id: "{grade}-{category}-{slug}"    # 예: "a-commercial-code-capital-increase-2025"
slug: "{자동 생성}"
title_kr: "{문서에서 추출한 제목}"
title_en: "{영문 제목 있으면 추출, 없으면 빈값}"
document_type: "{statute | enforcement_decree | regulation | guideline | decision | precedent | newsletter | commentary | article | paper}"

# === 소스 정보 ===
source_grade: "{A | B | C}"
publisher: "{발행 기관/로펌/저널명}"
author: "{저자명 (추출 가능한 경우)}"
published_date: "{발행일 (추출 가능한 경우)}"
source_url: "{URL (추출 가능한 경우)}"
original_format: "{pdf | docx | ...}"
ingested_at: "{처리 시각 ISO 8601}"

# === 검색 메타 ===
keywords: ["{내용 기반 키워드 5-10개}"]
topics: ["{주제 분류}"]
relevant_statutes: ["{인용된 법조문 목록, 예: 상법 제418조, 자본시장법 제9조}"]
contract_families_relevant: ["{관련 계약 유형: ssa, sha, safe, spa, license 등}"]
char_count: {글자수}

# === 검증 ===
verification_status: "{VERIFIED | UNVERIFIED}"
grade_confidence: "{high | medium | low}"
---
```

**핵심 필드 추출 로직:**
1. **제목**: 첫 번째 `#` 헤딩 또는 문서 최상단 볼드 텍스트
2. **키워드**: 계약법 관련 핵심 용어 추출 (투자계약, 주주간계약, 전환권, 우선매수권, 동반매도, 희석방지 등)
3. **relevant_statutes**: 정규식으로 "제XX조" 패턴 추출 → 법률명 + 조문 번호 매칭
4. **contract_families_relevant**: 문서 내용에서 관련 계약 유형 판별 (contract-families.yaml 참조)
5. **publisher**: 로펌명, 기관명, 저널명 등 추출
6. **published_date**: 날짜 패턴 추출 (YYYY.MM.DD, YYYY년 M월 D일 등)

### Step 5: 목적 폴더로 이동

Grade와 document_type에 따라 자동 배치:

```
Grade A:
  statute, enforcement_decree → library/grade-a/statutes/
  regulation                  → library/grade-a/regulations/
  guideline                   → library/grade-a/guidelines/
  기타 공식 문서               → library/grade-a/{category}/

Grade B:
  decision, precedent         → library/grade-b/precedents/
  newsletter, commentary      → library/grade-b/law-firm/
  KVCA/업계 해설              → library/grade-b/industry/
  기타                        → library/grade-b/{category}/

Grade C:
  paper, article              → library/grade-c/academic/
  세미나/발표                  → library/grade-c/seminars/
  기타                        → library/grade-c/{category}/
```

**파일명 규칙:** `{slug}.md`
- slug는 제목에서 생성: 한글 유지, 공백→하이픈, 특수문자 제거
- 중복 시 `-2`, `-3` 접미사

**원본 파일:** `library/inbox/_processed/`로 이동 (삭제하지 않음)

### Step 6: 인덱스 업데이트

처리 완료 후 `library/indexes/source-registry.json`을 업데이트한다.

**source-registry.json 엔트리 구조:**

```json
{
  "source_id": "a-statutes-commercial-code-capital-increase",
  "title_kr": "상법 제418조 (신주의 발행)",
  "source_grade": "A",
  "document_type": "statute",
  "path": "grade-a/statutes/commercial-code-capital-increase.md",
  "contract_families_relevant": ["ssa", "spa"],
  "keywords": ["신주발행", "주주배정", "제3자배정"],
  "ingested_at": "2026-03-25T10:00:00+09:00"
}
```

기존 `source-registry.json`이 없으면 새로 생성한다.

---

## 처리 결과 리포트

모든 파일 처리 후 요약 리포트를 출력한다:

```
Ingest 완료

처리: N개 파일
  Grade A: X건 (파일명 → grade-a/하위폴더/)
  Grade B: Y건
  Grade C: Z건
  판별 불가: W건 (Grade 지정 필요)
  Grade D 거부: V건

원본: library/inbox/_processed/ 로 이동
```

---

## 에러 처리

| 상황 | 대응 |
|------|------|
| inbox 비어있음 | "inbox가 비어 있습니다" 안내 |
| 미지원 포맷 (.hwp 등) | 해당 파일 스킵 + "PDF/DOCX로 변환 필요" 안내 |
| markitdown 변환 실패 | `_failed/`로 이동 + 실패 사유 안내 |
| Grade 판별 불가 | 유저에게 Grade 선택 질문 |
| 파일명 중복 | slug에 `-2`, `-3` 접미사 |
| frontmatter 추출 실패 | 빈 값으로 생성 + `grade_confidence: low` |

---

## 주의사항

1. **원본 보존**: inbox 원본은 절대 삭제하지 않음 → `_processed/`로 이동
2. **Grade D 배제**: 뉴스, AI 요약, 위키 등은 Grade D로 판별 시 ingest 거부 + 안내
3. **대용량 파일**: 50MB 초과 파일은 경고 후 유저 확인 요청
4. **스캔 PDF**: OCR 품질이 낮으면 `grade_confidence: low` + 유저 검토 권고
5. **기존 파일 보호**: 이미 `library/grade-x/`에 있는 동일 slug 파일은 덮어쓰지 않음
6. **계약서 템플릿 구분**: 참조 소스가 아닌 계약서 템플릿은 기존 10단계 파이프라인으로 라우팅
