# 구현 노트

[English](../en/implementation-notes.md) | [한국어](./implementation-notes.md)

## 현재 단계: v1α

### 구현된 구성 요소

#### 기초 구성
- 설계 문서 §3.1에 따른 전체 폴더 구조
- 합리적인 기본값을 갖춘 정책 YAML 파일 6개
- 비어 있는 인덱스 JSON 파일 5개
- CLAUDE.md 오케스트레이터 (간결한 버전, §3.2 기준)

#### 스크립트 (총 13개)
| 스크립트 | 언어 | 용도 |
|----------|------|------|
| `detect-format.py` | Python | 파일 형식 감지 및 검증 |
| `fingerprint.py` | Python | SHA-256 해시 및 중복 감지 |
| `normalize.py` | Python | DOCX/PDF/MD/TXT/HTML → clean.md + plain.txt |
| `build-index.py` | Python | approved/ 기준 인덱스 생성 및 재구축 |
| `query-index.py` | Python | 검색용 2단계 결정적 필터링 |
| `supersession.py` | Python | supersession 체인 관리 |
| `validate-manifest.py` | Python | manifest 스키마 검증 |
| `validate-package.py` | Python | 패키지 무결성 검사 |
| `check-privilege-leak.py` | Python | 특권 정보 누출 패턴 탐지 |
| `save-state.py` | Python | 파이프라인 상태 저장 |
| `load-state.py` | Python | 상태 로딩 및 재개 감지 |
| `diff-rounds.py` | Python | 라운드 간 조항 단위 diff |
| `map-clauses-to-docx.py` | Python | MD 조항 → DOCX 문단 매핑 |
| `apply-redlines.py` | Python | 추적 변경 XML 삽입 |
| `apply-comments.py` | Python | 코멘트 XML 삽입 |
| `strip-internal-comments.py` | Python | 외부 공유용을 위해 [INTERNAL] 코멘트 제거 |
| `compile-report.js` | Node.js | 분석 보고서 DOCX 생성 |
| `compile-delta-report.js` | Node.js | 델타 보고서 DOCX 생성 |

#### 스킬 파일 (7개 SKILL.md)
- doc-parser, clause-segmenter, index-manager, metadata-validator
- report-compiler, docx-redliner, pipeline-state, contract-review

#### 에이전트 파일 (3개 AGENT.md)
- ingestion-agent (WF1)
- review-agent (WF2 + WF4)
- drafting-agent (WF5)

#### 참고 문서 (4개)
- domain-policy.md, review-guide.md, audience-firewall.md, segmentation-guide.md

#### 설정
- 디렉터리 보호를 위한 PreToolUse hook이 포함된 .claude/settings.json

### 의존성
- Python 3.14+ 와 PyYAML
- Node.js 24+ 와 `docx` npm 패키지
- 선택 사항: PDF 지원용 pdftotext, pymupdf, 또는 pypdf
- 선택 사항: 향상된 DOCX 변환용 pandoc

### 테스트 방법

1. **Ingestion test**: `contract-review/library/inbox/raw/`에 DOCX/MD 계약서를 넣고 `/ingest` 실행
2. **Review test**: 검토할 계약서를 넣고 `/contract-review` 실행
3. **Library test**: `/library list` 또는 `/library search` 실행

### 알려진 한계 (v1α)
- PDF 추출에는 외부 도구(pdftotext/pymupdf/pypdf)가 필요함
- DOCX 정규화는 기본 XML 파싱을 사용함 (pandoc 없음)
- 보고서 출력은 JSON+MD만 지원함 (DOCX 보고서는 v1β)
- DOCX 레드라이닝은 아직 없음 (v1β)
