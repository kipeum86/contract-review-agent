"""Batch Steps 4-10: classify, structural parse, metadata, validation, publish for all ingested docs."""
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parent.parent
RUNS_DIR = BASE / "contract-review" / "library" / "runs" / "ingestion"
APPROVED_DIR = BASE / "contract-review" / "library" / "approved"
STAGING_DIR = BASE / "contract-review" / "library" / "staging"
QUARANTINE_DIR = BASE / "contract-review" / "library" / "quarantine"
INDEXES_DIR = BASE / "contract-review" / "library" / "indexes"
APPROVAL_RULES_PATH = BASE / "contract-review" / "library" / "policies" / "approval-rules.yaml"


def latest_summary_file() -> Path:
    """Return the newest batch summary, failing loudly when none exists."""
    candidates = sorted(RUNS_DIR.glob("*_batch-summary.json"))
    if not candidates:
        raise SystemExit(
            "ERROR: no *_batch-summary.json under "
            "contract-review/library/runs/ingestion/ — run scripts/batch_ingest.py "
            "first to produce a batch summary."
        )
    return candidates[-1]

NOW = datetime.now(timezone.utc)

QUOTED_TERM_RE = re.compile(r'[“"]([^“”"]{2,50})[”"]')
SECTION_REF_RE = re.compile(r'(제\s*\d+\s*(?:장|조)(?:의\s*\d+)?|별지[\s.]*(?:\d+)?|부록[\s.]*(?:\d+)?|첨부[\s.]*(?:\d+)?)')
PACKAGE_FILES = ("manifest.yaml", "classification.json")
PACKAGE_DIRS = ("normalized", "structure", "clauses", "quality")

# ── Step 4: Classification rules based on doc_id patterns ──

def classify_doc(doc_id: str, source_file: str) -> dict:
    """Classify based on structured filename patterns of KVCA standard templates."""
    c = {
        "doc_class": "template",
        "paper_role": "neutral",
        "jurisdiction": "KR",
        "governing_law": "대한민국 법률 (Korean law)",
        "language": "ko",
        "classification_confidence": "high",
    }

    # Determine stage tag for title
    if "early" in doc_id:
        stage = "초기"
        stage_en = "Early-stage"
    elif "mid" in doc_id:
        stage = "중기"
        stage_en = "Mid-stage"
    elif "late" in doc_id:
        stage = "후기"
        stage_en = "Late-stage"
    else:
        stage = ""
        stage_en = ""

    # Determine contract family and subtype
    if "sha-separated" in doc_id:
        c["contract_family"] = "sha"
        c["subtype"] = "investor_sha"
        c["title"] = f"[{stage}] 주주간계약서 (분리형)" if stage else "주주간계약서"
        c["title_en"] = f"[{stage_en}] Shareholders Agreement (Separated)" if stage_en else "Shareholders Agreement"
    elif "safe-conditional-equity" in doc_id:
        c["contract_family"] = "safe"
        c["subtype"] = "safe_standard"
        c["title"] = "조건부지분전환계약서"
        c["title_en"] = "Conditional Equity Conversion Agreement (SAFE)"
    elif "convertible-bond" in doc_id:
        c["contract_family"] = "ssa"
        c["subtype"] = "convertible_note"
        fmt = "통합형" if "integrated" in doc_id else ""
        c["title"] = f"[{stage}] 투자계약서 — 전환사채" if stage else "투자계약서 — 전환사채"
        c["title_en"] = f"[{stage_en}] Investment Agreement — Convertible Bond" if stage_en else "Investment Agreement — Convertible Bond"
    elif "bond-with-warrants" in doc_id:
        c["contract_family"] = "ssa"
        c["subtype"] = "convertible_note"
        c["title"] = f"[{stage}] 투자계약서 — 신주인수권부사채" if stage else "투자계약서 — 신주인수권부사채"
        c["title_en"] = f"[{stage_en}] Investment Agreement — Bond with Warrants" if stage_en else "Investment Agreement — Bond with Warrants"
    elif "rcps" in doc_id:
        c["contract_family"] = "ssa"
        c["subtype"] = "preferred_share_subscription"
        fmt = "통합형" if "integrated" in doc_id else "분리형"
        c["title"] = f"[{stage}] 투자계약서 — 상환전환우선주식 ({fmt})"
        c["title_en"] = f"[{stage_en}] Investment Agreement — RCPS ({'Integrated' if fmt == '통합형' else 'Separated'})"
    elif "convertible-preferred" in doc_id:
        c["contract_family"] = "ssa"
        c["subtype"] = "preferred_share_subscription"
        fmt = "통합형" if "integrated" in doc_id else "분리형"
        c["title"] = f"[{stage}] 투자계약서 — 전환우선주식 ({fmt})"
        c["title_en"] = f"[{stage_en}] Investment Agreement — Convertible Preferred ({fmt})"
    elif "common" in doc_id:
        c["contract_family"] = "ssa"
        c["subtype"] = "common_share_subscription"
        fmt = "통합형" if "integrated" in doc_id else "분리형"
        c["title"] = f"[{stage}] 투자계약서 — 보통주식 ({fmt})"
        c["title_en"] = f"[{stage_en}] Investment Agreement — Common Stock ({fmt})"
    else:
        c["contract_family"] = "other"
        c["subtype"] = "general"
        c["title"] = source_file
        c["classification_confidence"] = "low"

    return c


# ── Step 5: Structural parse from markdown ──

def parse_structure(md_path: Path) -> dict:
    """Extract headings, defined terms, and cross-references from clean.md."""
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    outline = []
    defined_terms = []
    crossrefs = []
    exhibits = []

    heading_re = re.compile(r"^(#{1,4})\s+(.+)")
    chapter_re = re.compile(r"^제(\d+)장\s+(.+)")
    article_re = re.compile(r"^\((.+?)\)")
    ref_re = re.compile(r"제(\d+)조")
    exhibit_re = re.compile(r"^(별지|부록|첨부)[\s.]*(\d*)")

    section_num = 0
    for i, line in enumerate(lines, 1):
        text = line.strip()
        if not text:
            continue

        # Headings
        hm = heading_re.match(text)
        if hm:
            level = len(hm.group(1))
            outline.append({"line": i, "level": level, "text": hm.group(2)})
            continue

        # Chapters (제N장)
        cm = chapter_re.match(text)
        if cm:
            section_num += 1
            outline.append({"line": i, "level": 1, "text": f"제{cm.group(1)}장 {cm.group(2)}", "section": f"ch{cm.group(1)}"})
            continue

        # Articles (조문 headers in parentheses)
        am = article_re.match(text)
        if am and len(text) < 40:
            section_num += 1
            outline.append({"line": i, "level": 2, "text": am.group(1), "section": f"art{section_num}"})

        # Defined terms ("..." or “...”)
        for tm in QUOTED_TERM_RE.finditer(text):
            term = tm.group(1)
            if term not in [t["term"] for t in defined_terms]:
                defined_terms.append({"term": term, "first_line": i})

        # Cross-references (제N조)
        for rm in ref_re.finditer(text):
            crossrefs.append({"from_line": i, "ref": f"제{rm.group(1)}조"})

        # Exhibits
        em = exhibit_re.match(text)
        if em:
            label = em.group(1) + (" " + em.group(2) if em.group(2) else "")
            exhibits.append({"line": i, "label": label.strip()})

    return {
        "outline": outline,
        "defined_terms": defined_terms,
        "crossrefs": crossrefs,
        "exhibits": exhibits,
    }


# ── Step 6: Clause segmentation (simplified for batch) ──

CLAUSE_PATTERNS = {
    "recitals": ["본 계약서는", "본 투자계약서", "아래 당사자들 사이에서"],
    "purpose": ["목적"],
    "definitions": ["용어의 뜻은 다음과 같다", "정의"],
    "purchase_price": ["신주의 발행 사항", "발행가액", "인수가액", "투자금의 지급"],
    "debt_security_issuance": ["사채의 발행 사항", "전환사채의 발행 사항", "신주인수권부사채의 발행 사항"],
    "conditions_precedent": ["선행조건", "투자의 선행조건"],
    "reps_warranties_seller": ["진술과 보장", "진술하고 보장한다"],
    "closing_mechanics": ["거래의 완결", "거래완결일"],
    "termination_for_cause": ["거래완결일 전 해제", "해제"],
    "obligations_general": ["투자금의 용도", "사용용도", "구조조정", "M&A에 관한 사항", "이해관계인의 책임", "회사 등의 의무"],
    "non_compete": ["기술의 이전", "겸업", "경업금지", "신회사 설립 제한"],
    "information_rights": ["보고 및 자료 제출", "경영사항에 대한"],
    "audit_rights": ["회계 및 업무감사", "시정조치"],
    "lock_up": ["이해관계인의 주식 처분", "주식처분"],
    "right_of_first_refusal": ["우선매수권", "매수우선권"],
    "tag_along": ["공동매도참여권"],
    "put_call_option": ["주식매수청구권"],
    "liquidated_damages": ["손해배상 및 위약벌", "위약벌"],
    "late_payment": ["지연배상금", "지연손해금"],
    "assignment": ["양도금지", "권리 및 의무의 양도"],
    "confidentiality": ["비밀유지"],
    "notices": ["통지"],
    "taxes": ["세금"],
    "severability": ["일부 무효", "가분성"],
    "governing_law": ["준거법", "관할법원", "분쟁해결"],
    "entire_agreement": ["본 계약의 효력"],
    "amendment": ["계약의 내용 변경", "계약의 변경"],
    "term_duration": ["계약의 종료", "계약기간"],
    "conversion_rights": ["전환에 관한 사항", "전환사채의 전환"],
    "liquidation_preference": ["잔여재산 분배"],
    "dividend_distribution": ["배당에 있어서 우선권"],
    "preemptive_rights": ["신주인수권"],
    "board_composition": ["임원의 선임", "이사 선임", "관찰자", "관찰자 파견", "이사회 구성"],
    "employee_matters": ["주식매수선택권의 부여"],
    "exhibits_schedules": ["별지", "부록", "첨부"],
    "signature_block": ["서명 또는 날인", "서명날인"],
    "drag_along": ["동반매도청구권", "동반매각청구권"],
    "indebtedness_liens": ["부채에 관한 사항", "담보제공 및 입보", "차입금", "담보종류"],
    "affiliates_subsidiaries": ["관계회사에 관한 사항", "관계회사"],
    "litigation_regulatory_matters": ["법령 위반, 소송 등에 관한 사항", "소송 등에 관한 사항", "법령 위반", "인허가", "행정처분"],
    "disclosure_accuracy": ["실사관련 자문사", "제공한 주주명부", "모든 면에서 진실되고 거짓이 없", "중요한 사항을 생략하지 않았"],
}

FAMILY_SPECIFIC_CLAUSE_PATTERNS = {
    "employment": {
        "employee_duties": ["직무", "업무내용", "담당업무", "근무장소"],
        "compensation_benefits": ["급여", "보수", "상여", "복리후생"],
        "working_hours_overtime": ["근로시간", "연장근로", "초과근로", "휴게시간"],
        "leave_holidays": ["휴가", "휴일", "연차"],
        "probation_period": ["수습", "시용기간"],
        "severance_retirement": ["퇴직금", "퇴직급여"],
        "confidentiality": ["비밀유지"],
        "non_compete": ["경업금지"],
        "termination_for_cause": ["해고", "계약 해지", "징계"],
    },
    "lease": {
        "premises_description": ["임대차 목적물", "임차목적물", "목적물의 표시"],
        "security_deposit_return": ["보증금 반환"],
        "rent_deposit": ["차임", "보증금", "임대료"],
        "permitted_use": ["사용 목적", "임대 목적", "용도"],
        "maintenance_repairs": ["수선의무", "유지보수", "수리"],
        "restoration_surrender": ["원상복구", "명도", "반환"],
        "term_duration": ["임대차 기간", "존속기간", "계약기간"],
    },
    "nda": {
        "confidentiality": ["비밀정보", "비밀유지의무"],
        "confidentiality_exceptions": ["예외사항", "허용된 공개", "비밀유지의 예외"],
        "confidentiality_duration": ["비밀유지 기간", "존속기간"],
        "effects_of_termination": ["반환 또는 파기", "자료의 반환", "파기 의무"],
        "injunctive_relief": ["가처분", "금지명령", "구제수단"],
    },
    "services": {
        "scope_of_services": ["용역의 범위", "업무 범위", "서비스 범위"],
        "deliverables": ["산출물", "결과물"],
        "fees_payment": ["대금", "수수료", "보수"],
        "service_levels": ["서비스 수준", "SLA", "가용성"],
        "acceptance": ["검수", "승인 기준"],
        "subcontracting": ["재위탁", "하도급"],
        "ip_ownership": ["결과물의 귀속", "지식재산권의 귀속"],
    },
}

# Chapter headings (제N장) map to a generic structural marker, not unmapped
CHAPTER_PATTERN = re.compile(r"^제\d+장")
GOVERNANCE_PATTERNS = ["주주총회", "이사회 의결 요구", "이사회 결의 요구"]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _normalize_heading_text(raw_heading: str) -> str:
    stripped = raw_heading.strip()
    if stripped.startswith("(") and stripped.endswith(")"):
        return stripped[1:-1].strip()
    return stripped


def _extract_defined_terms_used(segment_text: str, known_terms: list[str]) -> list[str]:
    used_terms = []

    for term in known_terms:
        if term and term in segment_text:
            used_terms.append(term)

    for match in QUOTED_TERM_RE.finditer(segment_text):
        used_terms.append(match.group(1))

    return _dedupe_preserve_order(used_terms)


def _extract_cross_refs(segment_text: str) -> list[str]:
    return _dedupe_preserve_order([match.group(1).strip() for match in SECTION_REF_RE.finditer(segment_text)])


def _count_paragraphs(segment_text: str) -> int:
    paragraphs = [block for block in re.split(r"\n\s*\n", segment_text) if block.strip()]
    return len(paragraphs)


def _iter_clause_patterns(contract_family: str | None = None):
    merged: dict[str, list[str]] = {}

    if contract_family:
        for ctype, patterns in FAMILY_SPECIFIC_CLAUSE_PATTERNS.get(contract_family, {}).items():
            merged.setdefault(ctype, []).extend(patterns)

    for ctype, patterns in CLAUSE_PATTERNS.items():
        merged.setdefault(ctype, []).extend(patterns)

    return merged.items()


def segment_clauses(md_path: Path, structure: dict | None = None, contract_family: str | None = None) -> list:
    """Segment document into clause units by matching patterns."""
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    clauses = []
    article_re = re.compile(r"^\((.+?)\)")
    numbered_article_re = re.compile(r"^제\s*(\d+)\s*조(?:의\s*(\d+))?\s*(?:\((.+?)\))?$")
    chapter_re = re.compile(r"^제(\d+)장\s+(.+)")
    exhibit_re = re.compile(r"^(별지|부록|첨부)")
    known_terms = []

    if structure and isinstance(structure.get("defined_terms"), list):
        known_terms = [
            term["term"]
            for term in structure["defined_terms"]
            if isinstance(term, dict) and isinstance(term.get("term"), str)
        ]

    # Find article boundaries. Prefer the parsed outline so segmentation stays aligned
    # with the structural parse and does not misclassify parenthetical preamble text.
    boundaries = []

    if structure and isinstance(structure.get("outline"), list) and structure["outline"]:
        next_article_number = 1

        for entry in structure["outline"]:
            if not isinstance(entry, dict):
                continue

            line_value = entry.get("line")
            heading_text = str(entry.get("text", "")).strip()
            if not heading_text or not isinstance(line_value, int):
                continue

            if CHAPTER_PATTERN.match(heading_text):
                chapter_match = chapter_re.match(heading_text)
                section_no = f"제{chapter_match.group(1)}장" if chapter_match else heading_text
                boundaries.append({
                    "line_index": max(line_value - 1, 0),
                    "raw_header": heading_text,
                    "heading": heading_text,
                    "section_no": section_no,
                    "kind": "chapter",
                })
                continue

            boundaries.append({
                "line_index": max(line_value - 1, 0),
                "raw_header": f"({heading_text})",
                "heading": heading_text,
                "section_no": f"제{next_article_number}조",
                "kind": "article",
            })
            next_article_number += 1

        for exhibit in structure.get("exhibits", []):
            if not isinstance(exhibit, dict):
                continue
            line_value = exhibit.get("line")
            label = str(exhibit.get("label", "")).strip()
            if not label or not isinstance(line_value, int):
                continue
            boundaries.append({
                "line_index": max(line_value - 1, 0),
                "raw_header": label,
                "heading": label,
                "section_no": label,
                "kind": "exhibit",
            })

        boundaries.sort(key=lambda item: item["line_index"])

    if not boundaries:
        next_article_number = 1
        for i, line in enumerate(lines):
            text = line.strip()
            if not text:
                continue

            numbered_article = numbered_article_re.match(text)
            if numbered_article:
                article_no = numbered_article.group(1)
                sub_no = numbered_article.group(2)
                next_article_number = max(next_article_number, int(article_no) + 1)
                section_no = f"제{article_no}조"
                if sub_no:
                    section_no = f"{section_no}의{sub_no}"
                heading = numbered_article.group(3).strip() if numbered_article.group(3) else text
                boundaries.append({
                    "line_index": i,
                    "raw_header": text,
                    "heading": heading,
                    "section_no": section_no,
                    "kind": "article",
                })
                continue

            article_match = article_re.match(text)
            if article_match and len(text) < 80:
                section_no = f"제{next_article_number}조"
                next_article_number += 1
                boundaries.append({
                    "line_index": i,
                    "raw_header": text,
                    "heading": article_match.group(1).strip(),
                    "section_no": section_no,
                    "kind": "article",
                })
                continue

            chapter_match = chapter_re.match(text)
            if chapter_match:
                boundaries.append({
                    "line_index": i,
                    "raw_header": text,
                    "heading": text,
                    "section_no": f"제{chapter_match.group(1)}장",
                    "kind": "chapter",
                })
                continue

            exhibit_match = exhibit_re.match(text)
            if exhibit_match:
                label = text
                boundaries.append({
                    "line_index": i,
                    "raw_header": text,
                    "heading": label,
                    "section_no": label,
                    "kind": "exhibit",
                })

    # Create clause segments
    for idx, boundary in enumerate(boundaries):
        line_num = boundary["line_index"]
        raw_header = boundary["raw_header"]
        heading = boundary["heading"]
        section_no = boundary["section_no"]
        end_line = boundaries[idx + 1]["line_index"] if idx + 1 < len(boundaries) else len(lines)
        segment_text = "\n".join(lines[line_num:end_line]).strip()

        # Classify clause type
        clause_type = "unmapped"

        # Chapter headings are structural markers, not unmapped
        if CHAPTER_PATTERN.match(raw_header.strip()):
            clause_type = "recitals"  # chapter header → structural
        else:
            # Check governance patterns first
            for gpat in GOVERNANCE_PATTERNS:
                if gpat in raw_header or gpat in segment_text[:200]:
                    clause_type = "board_composition"
                    break

            if clause_type == "unmapped":
                pattern_items = list(_iter_clause_patterns(contract_family))

                for ctype, patterns in pattern_items:
                    for pat in patterns:
                        if pat in raw_header:
                            clause_type = ctype
                            break
                    if clause_type != "unmapped":
                        break

                if clause_type == "unmapped":
                    for ctype, patterns in pattern_items:
                        for pat in patterns:
                            if pat in segment_text[:200]:
                                clause_type = ctype
                                break
                        if clause_type != "unmapped":
                            break

        clauses.append({
            "clause_id": f"clause-{idx+1:03d}",
            "section_no": section_no,
            "heading": _normalize_heading_text(heading),
            "header": raw_header,
            "start_line": line_num + 1,
            "end_line": end_line,
            "clause_type": clause_type,
            "text": segment_text,
            "defined_terms_used": _extract_defined_terms_used(segment_text, known_terms),
            "cross_refs": _extract_cross_refs(segment_text),
            "paragraph_count": _count_paragraphs(segment_text),
            "char_count": len(segment_text),
        })

    return clauses


# ── Step 7-8: Manifest generation & validation ──

def generate_manifest(doc_id: str, source_file: str, sha256: str, classification: dict, clauses: list, structure: dict) -> dict:
    total = len(clauses)
    unmapped = sum(1 for c in clauses if c["clause_type"] == "unmapped")
    unmapped_ratio = unmapped / total if total > 0 else 0

    manifest = {
        "doc_id": doc_id,
        "title": classification["title"],
        "title_en": classification.get("title_en", ""),
        "doc_class": classification["doc_class"],
        "contract_family": classification["contract_family"],
        "subtype": classification.get("subtype", ""),
        "paper_role": classification["paper_role"],
        "jurisdiction": classification["jurisdiction"],
        "governing_law": classification["governing_law"],
        "language": classification["language"],
        "approval_state": "pending",
        "status": "active",
        "sha256": sha256,
        "source_file": source_file,
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
        "classification_confidence": classification["classification_confidence"],
        "authority_level": "preferred",
        "external_safe": False,
        "freshness_sensitive": False,
        "tags": [
            "KVCA-standard",
            "2023-09-revision",
            "중소벤처기업부",
            "벤처투자",
        ],
        "notes": "한국벤처캐피탈협회(KVCA)/중소벤처기업부 표준투자계약서 (2023.9 개정)",
        "industry": "venture-capital",
        "stats": {
            "total_clauses": total,
            "unmapped_clauses": unmapped,
            "unmapped_ratio": round(unmapped_ratio, 3),
            "defined_terms": len(structure["defined_terms"]),
            "sections": len(structure["outline"]),
            "exhibits": len(structure["exhibits"]),
        },
    }
    return manifest


def validate_manifest(manifest: dict) -> tuple:
    """Returns (hard_fails, soft_fails)."""
    hard_fails = []
    soft_fails = []

    required = ["doc_id", "title", "doc_class", "contract_family", "paper_role",
                 "approval_state", "status", "sha256", "source_file", "created_at"]
    for field in required:
        if not manifest.get(field):
            hard_fails.append(f"Missing required field: {field}")

    if not re.match(r"^[a-z0-9\-]+$", manifest.get("doc_id", "")):
        hard_fails.append(f"Invalid doc_id format: {manifest.get('doc_id')}")

    if not re.match(r"^[a-f0-9]{64}$", manifest.get("sha256", "")):
        hard_fails.append(f"Invalid sha256 format")

    if manifest.get("stats", {}).get("unmapped_ratio", 0) > 0.3:
        soft_fails.append(f"Unmapped clause ratio {manifest['stats']['unmapped_ratio']:.1%} exceeds 30%")

    if manifest.get("classification_confidence") == "low":
        soft_fails.append("Low classification confidence")

    if manifest.get("stats", {}).get("total_clauses", 0) < 5:
        soft_fails.append(f"Only {manifest['stats']['total_clauses']} clauses detected")

    return hard_fails, soft_fails


def load_yaml_file(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_yaml_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(payload, handle, allow_unicode=True, default_flow_style=False, sort_keys=False)


def load_approval_rules() -> dict:
    """Load approval policy. Fail safe to manual review if the policy is missing or malformed."""
    rules = {
        "auto_approval": {
            "enabled": False,
            "conditions": [],
        },
        "per_asset_type": {},
        "approval_decisions": {"valid_values": []},
        "staging_retention": {},
        "_policy_errors": [],
    }

    try:
        raw = load_yaml_file(APPROVAL_RULES_PATH)
    except yaml.YAMLError as exc:
        rules["_policy_errors"].append(f"approval_rules_yaml_error:{exc}")
        return rules
    except OSError as exc:
        rules["_policy_errors"].append(f"approval_rules_io_error:{exc}")
        return rules

    if raw is None:
        rules["_policy_errors"].append("approval_rules_missing")
        return rules

    if not isinstance(raw, dict):
        rules["_policy_errors"].append("approval_rules_invalid_shape")
        return rules

    for key in ("auto_approval", "per_asset_type", "approval_decisions", "staging_retention"):
        value = raw.get(key)
        if isinstance(value, dict):
            rules[key] = value

    auto_approval = rules.get("auto_approval", {})
    if not isinstance(auto_approval.get("conditions"), list):
        auto_approval["conditions"] = []
        rules["_policy_errors"].append("approval_rules_conditions_invalid_shape")

    return rules


def get_asset_policy(approval_rules: dict, doc_class: str) -> dict:
    per_asset_type = approval_rules.get("per_asset_type", {})
    if not isinstance(per_asset_type, dict):
        return {}
    asset_policy = per_asset_type.get(doc_class, {})
    return asset_policy if isinstance(asset_policy, dict) else {}


def apply_asset_policy_defaults(manifest: dict, asset_policy: dict) -> None:
    default_authority = asset_policy.get("default_authority_level")
    if default_authority is not None:
        manifest["authority_level"] = default_authority

    if "default_external_safe" in asset_policy:
        manifest["external_safe"] = bool(asset_policy["default_external_safe"])


def evaluate_auto_approval_conditions(manifest: dict, validation_report: dict, approval_rules: dict) -> list[str]:
    unmet_conditions = []
    conditions = approval_rules.get("auto_approval", {}).get("conditions", [])

    for condition in conditions:
        if not isinstance(condition, dict) or len(condition) != 1:
            unmet_conditions.append("invalid_policy_condition")
            continue

        field, expected_value = next(iter(condition.items()))
        if field == "classification_confidence":
            actual_value = manifest.get("classification_confidence")
        elif field == "soft_fail_count":
            actual_value = len(validation_report.get("soft_fails", []))
        elif field == "hard_fail_count":
            actual_value = len(validation_report.get("hard_fails", []))
        elif field == "schema_validation":
            actual_value = "passed" if validation_report.get("schema_valid") else "failed"
        else:
            actual_value = manifest.get(field)

        if actual_value != expected_value:
            unmet_conditions.append(
                f"auto_approval_condition_failed:{field}:expected={expected_value}:actual={actual_value}"
            )

    return unmet_conditions


def resolve_approved_destination(manifest: dict) -> Path | None:
    doc_id = manifest.get("doc_id")
    doc_class = manifest.get("doc_class")

    if not doc_id or not doc_class:
        return None

    if doc_class == "template":
        contract_family = manifest.get("contract_family")
        if not contract_family:
            return None
        return APPROVED_DIR / "templates" / contract_family / doc_id

    if doc_class == "precedent":
        if manifest.get("authority_level") == "reference_only":
            return APPROVED_DIR / "precedents" / "reference-only" / doc_id
        return APPROVED_DIR / "precedents" / doc_id

    return None


def resolve_publication_destination(manifest: dict, publication_target: str) -> Path | None:
    doc_id = manifest.get("doc_id")
    if not doc_id:
        return None

    if publication_target == "approved":
        return resolve_approved_destination(manifest)
    if publication_target == "staging":
        return STAGING_DIR / doc_id
    if publication_target == "quarantine":
        return QUARANTINE_DIR / doc_id
    return None


def determine_publication_target(manifest: dict, validation_report: dict, approval_rules: dict) -> dict:
    asset_policy = get_asset_policy(approval_rules, manifest.get("doc_class", ""))
    apply_asset_policy_defaults(manifest, asset_policy)

    publication = {
        "approval_state": "staging",
        "publication_target": "staging",
        "reason_file": "staging-reason.json",
        "reasons": _dedupe_preserve_order(validation_report.get("soft_fails", [])),
        "policy_errors": approval_rules.get("_policy_errors", []),
        "unmet_conditions": [],
        "auto_approval_enabled": bool(approval_rules.get("auto_approval", {}).get("enabled", False)),
        "asset_auto_approvable": bool(asset_policy.get("auto_approvable", False)),
        "doc_class": manifest.get("doc_class"),
    }

    if validation_report.get("hard_fails"):
        publication["approval_state"] = "quarantined"
        publication["publication_target"] = "quarantine"
        publication["reason_file"] = "quarantine-reason.json"
        publication["reasons"] = _dedupe_preserve_order(validation_report["hard_fails"])
        return publication

    if not asset_policy:
        publication["reasons"] = _dedupe_preserve_order(
            publication["reasons"] + [f"missing_asset_policy:{manifest.get('doc_class', 'unknown')}"]
        )
        return publication

    if approval_rules.get("_policy_errors"):
        publication["reasons"] = _dedupe_preserve_order(
            publication["reasons"] + approval_rules["_policy_errors"]
        )
        return publication

    if not publication["auto_approval_enabled"]:
        publication["reasons"] = _dedupe_preserve_order(publication["reasons"] + ["auto_approval_disabled"])
        return publication

    if not publication["asset_auto_approvable"]:
        publication["reasons"] = _dedupe_preserve_order(
            publication["reasons"] + [f"manual_review_required_for_doc_class:{manifest.get('doc_class')}"]
        )
        return publication

    approved_destination = resolve_approved_destination(manifest)
    if approved_destination is None:
        publication["reasons"] = _dedupe_preserve_order(
            publication["reasons"] + [f"unsupported_publish_target:{manifest.get('doc_class')}"]
        )
        return publication

    publication["unmet_conditions"] = evaluate_auto_approval_conditions(
        manifest,
        validation_report,
        approval_rules,
    )
    if publication["unmet_conditions"]:
        publication["reasons"] = _dedupe_preserve_order(
            publication["reasons"] + publication["unmet_conditions"]
        )
        return publication

    publication["approval_state"] = "approved"
    publication["publication_target"] = "approved"
    publication["reason_file"] = None
    publication["reasons"] = []
    return publication


def find_existing_package_dirs(doc_id: str) -> list[Path]:
    found_paths = []
    seen_paths = set()

    for root in (APPROVED_DIR, STAGING_DIR, QUARANTINE_DIR):
        if not root.exists():
            continue
        for candidate in root.glob(f"**/{doc_id}"):
            resolved = candidate.resolve()
            if candidate.is_dir() and resolved not in seen_paths:
                found_paths.append(candidate)
                seen_paths.add(resolved)

    return found_paths


def copy_package_artifacts(run_dir: Path, dest_dir: Path) -> None:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)

    for file_name in PACKAGE_FILES:
        source_path = run_dir / file_name
        if source_path.exists():
            shutil.copy2(source_path, dest_dir / file_name)

    for dir_name in PACKAGE_DIRS:
        source_dir = run_dir / dir_name
        if source_dir.exists():
            shutil.copytree(source_dir, dest_dir / dir_name, dirs_exist_ok=True)


def sync_package_to_publication_target(
    run_dir: Path,
    manifest: dict,
    validation_report: dict,
    publication: dict,
) -> Path:
    doc_id = manifest["doc_id"]
    destination = resolve_publication_destination(manifest, publication["publication_target"])
    if destination is None:
        raise RuntimeError(f"Cannot resolve destination for {doc_id}: {publication['publication_target']}")

    destination_resolved = destination.resolve()
    for existing_dir in find_existing_package_dirs(doc_id):
        if existing_dir.resolve() != destination_resolved:
            shutil.rmtree(existing_dir)

    copy_package_artifacts(run_dir, destination)

    if publication.get("reason_file"):
        reason_payload = {
            "doc_id": doc_id,
            "approval_state": publication["approval_state"],
            "publication_target": publication["publication_target"],
            "reasons": publication.get("reasons", []),
            "hard_fails": validation_report.get("hard_fails", []),
            "soft_fails": validation_report.get("soft_fails", []),
            "unmet_conditions": publication.get("unmet_conditions", []),
            "policy_errors": publication.get("policy_errors", []),
            "auto_approval_enabled": publication.get("auto_approval_enabled", False),
            "asset_auto_approvable": publication.get("asset_auto_approvable", False),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        write_json_file(destination / publication["reason_file"], reason_payload)

    return destination


def rebuild_indexes_from_approved() -> dict:
    """Rebuild indexes from approved/ to keep retrieval state aligned with published artifacts."""
    build_index_script = BASE / ".claude" / "skills" / "index-manager" / "scripts" / "build-index.py"
    completed = subprocess.run(
        ["python3", str(build_index_script), "rebuild"],
        check=False,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"Index rebuild failed with code {completed.returncode}: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )

    return json.loads(completed.stdout)


# ── Main pipeline ──

def main():
    approval_rules = load_approval_rules()

    with open(latest_summary_file(), "r", encoding="utf-8") as f:
        summary = json.load(f)

    results = [r for r in summary["results"] if r["status"] == "normalized"]
    print(f"Processing {len(results)} documents through Steps 4-10.\n")

    quarantined = []
    staged = []
    approved_list = []

    for i, r in enumerate(results, 1):
        doc_id = r["doc_id"]
        run_dir = BASE / r["run_dir"].replace("\\", "/")
        md_path = run_dir / "normalized" / "clean.md"

        print(f"[{i}/{len(results)}] {doc_id}")

        # Step 4: Classification
        classification = classify_doc(doc_id, r["file"])
        with open(run_dir / "classification.json", "w", encoding="utf-8") as f:
            json.dump(classification, f, ensure_ascii=False, indent=2)

        # Step 5: Structural parse
        structure = parse_structure(md_path)
        for key in ["outline", "defined_terms", "crossrefs", "exhibits"]:
            fname = {"outline": "outline.json", "defined_terms": "defined_terms.json",
                     "crossrefs": "crossrefs.json", "exhibits": "exhibits.json"}[key]
            with open(run_dir / "structure" / fname, "w", encoding="utf-8") as f:
                json.dump(structure[key], f, ensure_ascii=False, indent=2)

        # Step 6: Clause segmentation
        clauses = segment_clauses(md_path, structure, classification["contract_family"])
        for ci, clause in enumerate(clauses):
            with open(run_dir / "clauses" / f"{clause['clause_id']}.json", "w", encoding="utf-8") as f:
                json.dump(clause, f, ensure_ascii=False, indent=2)

        # Step 7: Metadata enrichment
        manifest = generate_manifest(doc_id, r["file"], r["sha256"], classification, clauses, structure)

        # Step 8: Validation
        hard_fails, soft_fails = validate_manifest(manifest)
        validation_report = {
            "doc_id": doc_id,
            "hard_fails": hard_fails,
            "soft_fails": soft_fails,
            "schema_valid": len(hard_fails) == 0,
            "timestamp": NOW.isoformat(),
        }

        # Step 9: Approval gate
        publication = determine_publication_target(manifest, validation_report, approval_rules)
        manifest["approval_state"] = publication["approval_state"]
        manifest["updated_at"] = NOW.isoformat()
        validation_report["approval_gate"] = publication

        # Update manifest with approval state
        write_yaml_file(run_dir / "manifest.yaml", manifest)
        write_json_file(run_dir / "quality" / "validation-report.json", validation_report)

        # Step 10: Publish approved
        destination = sync_package_to_publication_target(run_dir, manifest, validation_report, publication)
        if manifest["approval_state"] == "approved":
            approved_list.append(doc_id)
            print(f"  AUTO-APPROVED ({manifest['stats']['total_clauses']} clauses, "
                  f"{manifest['stats']['defined_terms']} terms, "
                  f"{manifest['stats']['unmapped_ratio']:.0%} unmapped) -> {destination}")
        elif manifest["approval_state"] == "staging":
            staged.append({"doc_id": doc_id, "reasons": publication["reasons"]})
            print(f"  STAGED -> {destination}: {publication['reasons']}")
        else:
            quarantined.append({"doc_id": doc_id, "reasons": publication["reasons"]})
            print(f"  QUARANTINED -> {destination}: {publication['reasons']}")

    rebuild_result = rebuild_indexes_from_approved()

    # Summary
    print(f"\n{'='*60}")
    print(f"INGESTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Processed:   {len(results)}")
    print(f"  Approved:    {len(approved_list)}")
    print(f"  Staged:      {len(staged)}")
    print(f"  Quarantined: {len(quarantined)}")
    print(
        f"  Indexed:     {rebuild_result.get('documents_count', 0)} docs / "
        f"{rebuild_result.get('clauses_count', 0)} clauses"
    )
    print(f"{'='*60}")

    if staged:
        print(f"\nSTAGED documents (require human review):")
        for s in staged:
            print(f"  - {s['doc_id']}: {', '.join(s['reasons'])}")

    if quarantined:
        print(f"\nQUARANTINED documents (hard failures):")
        for q in quarantined:
            print(f"  - {q['doc_id']}: {', '.join(q['reasons'])}")


if __name__ == "__main__":
    main()
