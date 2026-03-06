"""Batch Steps 4-10: classify, structural parse, metadata, validation, publish for all ingested docs."""
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parent.parent
RUNS_DIR = BASE / "contract-review" / "library" / "runs" / "ingestion"
APPROVED_DIR = BASE / "contract-review" / "library" / "approved"
INDEXES_DIR = BASE / "contract-review" / "library" / "indexes"
SUMMARY_FILE = sorted(RUNS_DIR.glob("*_batch-summary.json"))[-1]

NOW = datetime.now(timezone.utc)

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
    term_re = re.compile(r'"([^"]{2,30})"')
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

        # Defined terms ("...")
        for tm in term_re.finditer(text):
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
    "definitions": ["용어의 뜻은 다음과 같다", "정의"],
    "purchase_price": ["신주의 발행 사항", "발행가액", "인수가액", "투자금의 지급"],
    "conditions_precedent": ["선행조건", "투자의 선행조건"],
    "reps_warranties_seller": ["진술과 보장", "진술하고 보장한다"],
    "closing_mechanics": ["거래의 완결", "거래완결일"],
    "termination_for_cause": ["거래완결일 전 해제", "해제"],
    "obligations_general": ["투자금의 용도", "사용용도"],
    "non_compete": ["기술의 이전", "겸업", "경업금지", "신회사 설립 제한"],
    "information_rights": ["보고 및 자료 제출", "경영사항에 대한"],
    "audit_rights": ["회계 및 업무감사", "시정조치"],
    "lock_up": ["이해관계인의 주식 처분", "주식처분"],
    "right_of_first_refusal": ["우선매수권", "공동매도참여권"],
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
    "board_composition": ["이사 선임", "관찰자"],
    "employee_matters": ["주식매수선택권의 부여"],
    "exhibits_schedules": ["별지", "부록", "첨부"],
    "signature_block": ["서명 또는 날인", "서명날인"],
    "board_composition": ["임원의 선임", "이사 선임", "관찰자 파견", "이사회 구성"],
    "drag_along": ["동반매도청구권", "동반매각청구권"],
    "obligations_general": ["투자금의 용도", "사용용도", "구조조정", "M&A에 관한 사항", "이해관계인의 책임"],
    "definitions": ["용어의 뜻은 다음과 같다", "정의"],
}

# Chapter headings (제N장) map to a generic structural marker, not unmapped
CHAPTER_PATTERN = re.compile(r"^제\d+장")
GOVERNANCE_PATTERNS = ["주주총회", "이사회 의결 요구", "이사회 결의 요구"]


def segment_clauses(md_path: Path) -> list:
    """Segment document into clause units by matching patterns."""
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    clauses = []
    article_re = re.compile(r"^\((.+?)\)")
    chapter_re = re.compile(r"^제(\d+)장\s+(.+)")
    exhibit_re = re.compile(r"^(별지|부록|첨부)")

    # Find article boundaries
    boundaries = []
    for i, line in enumerate(lines):
        text = line.strip()
        if not text:
            continue
        if article_re.match(text) and len(text) < 40:
            boundaries.append((i, text))
        elif chapter_re.match(text):
            boundaries.append((i, text))
        elif exhibit_re.match(text):
            boundaries.append((i, text))

    # Create clause segments
    for idx, (line_num, header) in enumerate(boundaries):
        end_line = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(lines)
        segment_text = "\n".join(lines[line_num:end_line]).strip()

        # Classify clause type
        clause_type = "unmapped"

        # Chapter headings are structural markers, not unmapped
        if CHAPTER_PATTERN.match(header.strip()):
            clause_type = "recitals"  # chapter header → structural
        else:
            # Check governance patterns first
            for gpat in GOVERNANCE_PATTERNS:
                if gpat in header or gpat in segment_text[:200]:
                    clause_type = "board_composition"
                    break

            if clause_type == "unmapped":
                for ctype, patterns in CLAUSE_PATTERNS.items():
                    for pat in patterns:
                        if pat in header or pat in segment_text[:200]:
                            clause_type = ctype
                            break
                    if clause_type != "unmapped":
                        break

        clauses.append({
            "clause_id": f"clause-{idx+1:03d}",
            "header": header,
            "start_line": line_num + 1,
            "end_line": end_line,
            "clause_type": clause_type,
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


# ── Main pipeline ──

def main():
    with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
        summary = json.load(f)

    results = [r for r in summary["results"] if r["status"] == "normalized"]
    print(f"Processing {len(results)} documents through Steps 4-10.\n")

    all_manifests = []
    all_clauses_index = []
    all_terms_index = []
    all_documents_index = []
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
        clauses = segment_clauses(md_path)
        for ci, clause in enumerate(clauses):
            with open(run_dir / "clauses" / f"{clause['clause_id']}.json", "w", encoding="utf-8") as f:
                json.dump(clause, f, ensure_ascii=False, indent=2)

        # Step 7: Metadata enrichment
        manifest = generate_manifest(doc_id, r["file"], r["sha256"], classification, clauses, structure)
        with open(run_dir / "manifest.yaml", "w", encoding="utf-8") as f:
            yaml.dump(manifest, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # Step 8: Validation
        hard_fails, soft_fails = validate_manifest(manifest)
        validation_report = {
            "doc_id": doc_id,
            "hard_fails": hard_fails,
            "soft_fails": soft_fails,
            "schema_valid": len(hard_fails) == 0,
            "timestamp": NOW.isoformat(),
        }
        (run_dir / "quality").mkdir(exist_ok=True)
        with open(run_dir / "quality" / "validation-report.json", "w", encoding="utf-8") as f:
            json.dump(validation_report, f, ensure_ascii=False, indent=2)

        # Step 9: Approval gate
        if hard_fails:
            manifest["approval_state"] = "quarantined"
            quarantined.append({"doc_id": doc_id, "reasons": hard_fails})
            print(f"  QUARANTINED: {hard_fails}")
        elif soft_fails:
            manifest["approval_state"] = "staging"
            staged.append({"doc_id": doc_id, "reasons": soft_fails})
            print(f"  STAGED: {soft_fails}")
        else:
            # Auto-approval: template + high confidence + 0 soft fails
            manifest["approval_state"] = "approved"
            approved_list.append(doc_id)
            print(f"  AUTO-APPROVED ({manifest['stats']['total_clauses']} clauses, "
                  f"{manifest['stats']['defined_terms']} terms, "
                  f"{manifest['stats']['unmapped_ratio']:.0%} unmapped)")

        # Update manifest with approval state
        with open(run_dir / "manifest.yaml", "w", encoding="utf-8") as f:
            yaml.dump(manifest, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        all_manifests.append(manifest)

        # Step 10: Publish approved
        if manifest["approval_state"] == "approved":
            family = manifest["contract_family"]
            dest = APPROVED_DIR / "templates" / family / doc_id
            dest.mkdir(parents=True, exist_ok=True)

            # Copy normalized files
            shutil.copy2(md_path, dest / "clean.md")
            txt_path = run_dir / "normalized" / "plain.txt"
            if txt_path.exists():
                shutil.copy2(txt_path, dest / "plain.txt")
            shutil.copy2(run_dir / "manifest.yaml", dest / "manifest.yaml")

            # Copy structure
            (dest / "structure").mkdir(exist_ok=True)
            for sfile in (run_dir / "structure").glob("*.json"):
                shutil.copy2(sfile, dest / "structure" / sfile.name)

            # Copy clauses
            (dest / "clauses").mkdir(exist_ok=True)
            for cfile in (run_dir / "clauses").glob("*.json"):
                shutil.copy2(cfile, dest / "clauses" / cfile.name)

            # Build index entries
            all_documents_index.append({
                "doc_id": doc_id,
                "title": manifest["title"],
                "doc_class": manifest["doc_class"],
                "contract_family": family,
                "subtype": manifest.get("subtype", ""),
                "paper_role": manifest["paper_role"],
                "jurisdiction": manifest["jurisdiction"],
                "language": manifest["language"],
                "authority_level": manifest.get("authority_level", "preferred"),
                "approval_state": "approved",
                "status": "active",
                "sha256": manifest["sha256"],
                "source_file": manifest["source_file"],
                "path": f"approved/templates/{family}/{doc_id}/",
                "created_at": manifest["created_at"],
            })

            for clause in clauses:
                all_clauses_index.append({
                    "doc_id": doc_id,
                    "clause_id": clause["clause_id"],
                    "clause_type": clause["clause_type"],
                    "header": clause["header"],
                    "contract_family": family,
                })

            for term in structure["defined_terms"]:
                all_terms_index.append({
                    "doc_id": doc_id,
                    "term": term["term"],
                    "first_line": term["first_line"],
                })

    # Write indexes
    docs_index = {
        "version": 1,
        "updated_at": NOW.isoformat(),
        "documents": all_documents_index,
    }
    with open(INDEXES_DIR / "documents.json", "w", encoding="utf-8") as f:
        json.dump(docs_index, f, ensure_ascii=False, indent=2)

    clauses_index = {
        "version": 1,
        "updated_at": NOW.isoformat(),
        "clauses": all_clauses_index,
    }
    with open(INDEXES_DIR / "clauses.json", "w", encoding="utf-8") as f:
        json.dump(clauses_index, f, ensure_ascii=False, indent=2)

    terms_index = {
        "version": 1,
        "updated_at": NOW.isoformat(),
        "terms": all_terms_index,
    }
    with open(INDEXES_DIR / "terms.json", "w", encoding="utf-8") as f:
        json.dump(terms_index, f, ensure_ascii=False, indent=2)

    # Retrieval map
    retrieval_map = {"version": 1, "updated_at": NOW.isoformat(), "entries": []}
    for doc in all_documents_index:
        retrieval_map["entries"].append({
            "doc_id": doc["doc_id"],
            "contract_family": doc["contract_family"],
            "subtype": doc.get("subtype", ""),
            "authority_level": doc.get("authority_level", "preferred"),
            "path": doc["path"],
        })
    with open(INDEXES_DIR / "retrieval-map.json", "w", encoding="utf-8") as f:
        json.dump(retrieval_map, f, ensure_ascii=False, indent=2)

    # Supersession (empty — all new)
    supersession = {"version": 1, "updated_at": NOW.isoformat(), "entries": []}
    with open(INDEXES_DIR / "supersession.json", "w", encoding="utf-8") as f:
        json.dump(supersession, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'='*60}")
    print(f"INGESTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Processed:   {len(results)}")
    print(f"  Approved:    {len(approved_list)}")
    print(f"  Staged:      {len(staged)}")
    print(f"  Quarantined: {len(quarantined)}")
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
