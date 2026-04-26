---
name: ingest
description: >
  library/inbox/에 넣은 외부 참조 소스 파일(PDF, DOCX 등)을 자동으로
  Markdown 변환, frontmatter 생성, 폴더 배치, 인덱스 업데이트까지
  원스텝으로 처리한다. /ingest로 트리거.
---

# Source Ingest

`contract-review/library/inbox/`에 참조 소스 파일을 넣고 `/ingest`를 실행하면 자동으로 처리한다.

> **참고**: 이 스킬은 **참조 소스**(법령, 판례, 해설, 샘플 양식 등)를 Markdown으로 변환·구조화한다.
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
  ├─ Step 3: Frontmatter 생성 + sources/ 배치
  └─ Step 4: 인덱스 업데이트
```

Executable implementation:

```bash
python3 .claude/skills/ingest/scripts/source_ingest.py <source-file> \
  --source-id <id> \
  --jurisdiction KR \
  --source-type statute \
  --authority-level primary_law

python3 .claude/skills/ingest/scripts/validate_source_registry.py \
  contract-review/library/sources/source-registry.json
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

### Step 3: Frontmatter 생성 + sources/ 배치

변환된 .md 파일에 YAML frontmatter를 자동 생성한다.

```yaml
---
# === 식별 정보 ===
source_id: "{category}-{slug}"        # 예: "statute-commercial-code-capital-increase"
slug: "{자동 생성}"
title_kr: "{문서에서 추출한 제목}"
title_en: "{영문 제목 있으면 추출, 없으면 빈값}"
document_type: "{statute | enforcement_decree | regulation | guideline | decision | precedent | newsletter | commentary | article | paper | sample_form | other}"

# === 소스 정보 ===
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
---
```

**핵심 필드 추출 로직:**
1. **제목**: 첫 번째 `#` 헤딩 또는 문서 최상단 볼드 텍스트
2. **키워드**: 계약법 관련 핵심 용어 추출 (투자계약, 주주간계약, 전환권, 우선매수권, 동반매도, 희석방지 등)
3. **relevant_statutes**: 정규식으로 "제XX조" 패턴 추출 → 법률명 + 조문 번호 매칭
4. **contract_families_relevant**: 문서 내용에서 관련 계약 유형 판별 (contract-families.yaml 참조)
5. **publisher**: 로펌명, 기관명, 저널명 등 추출
6. **published_date**: 날짜 패턴 추출 (YYYY.MM.DD, YYYY년 M월 D일 등)

**저장 위치:** `library/sources/{slug}.md`
- slug는 제목에서 생성: 한글 유지, 공백→하이픈, 특수문자 제거
- 중복 시 `-2`, `-3` 접미사

**원본 파일:** `library/inbox/_processed/`로 이동 (삭제하지 않음)

### Step 4: 인덱스 업데이트

처리 완료 후 `library/sources/source-registry.json`을 업데이트한다.

**source-registry.json 엔트리 구조:**

```json
{
  "source_id": "statute-commercial-code-capital-increase",
  "title_kr": "상법 제418조 (신주의 발행)",
  "document_type": "statute",
  "path": "sources/commercial-code-capital-increase.md",
  "contract_families_relevant": ["ssa", "spa"],
  "keywords": ["신주발행", "주주배정", "제3자배정"],
  "ingested_at": "2026-03-25T10:00:00+09:00"
}
```

기존 `source-registry.json`이 없으면 새로 생성한다.

Validation rules:

- Duplicate `source_id` is a hard failure.
- Missing source file path or SHA mismatch is a hard failure.
- Stale `last_checked` is a warning in `validate_source_registry.py` and must be surfaced in review metadata when cited.
- Review report internal metadata should preserve cited `source_id` values so stale-source warnings can be traced.

---

## 처리 결과 리포트

모든 파일 처리 후 요약 리포트를 출력한다:

```
Ingest 완료

처리: N개 파일
  성공: X건 (파일명 → sources/)
  실패: Y건 (_failed/로 이동)

원본: library/inbox/_processed/ 로 이동
```

---

## 에러 처리

| 상황 | 대응 |
|------|------|
| inbox 비어있음 | "inbox가 비어 있습니다" 안내 |
| 미지원 포맷 (.hwp 등) | 해당 파일 스킵 + "PDF/DOCX로 변환 필요" 안내 |
| markitdown 변환 실패 | `_failed/`로 이동 + 실패 사유 안내 |
| 파일명 중복 | slug에 `-2`, `-3` 접미사 |
| frontmatter 추출 실패 | 빈 값으로 생성 + 유저 검토 권고 |

---

## 주의사항

1. **원본 보존**: inbox 원본은 절대 삭제하지 않음 → `_processed/`로 이동
2. **대용량 파일**: 50MB 초과 파일은 경고 후 유저 확인 요청
3. **스캔 PDF**: OCR 품질이 낮으면 유저 검토 권고
4. **기존 파일 보호**: 이미 `library/sources/`에 있는 동일 slug 파일은 덮어쓰지 않음
5. **계약서 템플릿 구분**: 참조 소스가 아닌 계약서 템플릿은 기존 10단계 파이프라인으로 라우팅
