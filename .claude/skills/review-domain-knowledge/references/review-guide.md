# Contract Review Judgment Guide

## Risk Grading Criteria

### Critical
The clause creates an **unacceptable** legal or commercial exposure. Immediate attention required.

Examples:
- Unlimited liability with no cap
- Unilateral termination rights without cure period
- Broad IP assignment without compensation
- Indemnification for counterparty's own negligence
- Prohibited position per playbook
- Governing law in hostile jurisdiction with no fallback

### High
The clause contains **significant** deviations from house position. Should be negotiated.

Examples:
- Liability cap set unreasonably low relative to contract value
- Overly broad non-compete or non-solicitation
- Missing limitation of consequential damages
- Unilateral amendment rights
- Data processing without adequate security requirements
- Auto-renewal without opt-out mechanism

### Medium
The clause contains **notable** deviations that may be acceptable depending on context.

Examples:
- Slightly narrower confidentiality exceptions than house standard
- Notice period shorter than preferred but within industry norms
- Force majeure clause narrower than house template
- Payment terms longer than preferred
- Assignment restriction without change-of-control exception

### Low
The clause contains **minor** deviations that are generally acceptable.

Examples:
- Stylistic differences in boilerplate
- Notice address format variations
- Counterparts provision wording differences
- Slightly different severability formulation
- Minor variations in defined terms structure

### Acceptable
The clause is **substantially aligned** with house position or industry standard.

## Analysis Methodology

### Four-Lens Analysis Framework

Before grading any clause, apply all four lenses:

1. **Asymmetries** — Does this provision apply to one party differently than the other? Any right, obligation, remedy, or restriction that is unilateral or applies on materially different terms warrants scrutiny.

2. **Overbroad Qualifiers** — Are knowledge qualifiers, materiality thresholds, or carve-outs used in ways that hollow out protections the client should have? (e.g., "to the best of Seller's knowledge" on a rep that should be absolute; a "material breach" threshold that effectively voids any termination right)

3. **Missing Protections** — What standard provisions for this contract type are absent entirely? A missing clause can be more dangerous than a bad one. (e.g., no limitation of liability clause, no IP ownership provision, no data breach notification obligation)

4. **Structural Traps** — Do provisions that appear neutral individually combine with other clauses to produce a one-sided outcome? (e.g., a basket equal to the indemnification cap, making indemnification illusory; a cure period that starts running before written notice is received)

### Per-Clause Procedure

For each clause:

1. **Read** the target clause text completely
2. **Apply the four lenses** above — note any asymmetry, overbroad qualifier, missing protection, or structural trap
3. **Compare** against the matched library clause (house position)
4. **Check** the playbook for this clause type (if available):
   - Is the clause within the preferred tier?
   - Does it match an acceptable alternative?
   - Has it fallen to fallback territory?
   - Does it hit a prohibited position?
5. **Assess** the risk in context:
   - What is the commercial impact?
   - What is the legal exposure?
   - Is this a standard market position?
   - What does the matter context suggest (leverage, priority areas)?
6. **Grade** the risk level
7. **Document** the reasoning using this structured format: `[deviation identified] → [legal/commercial impact] → [market standard reference] → [risk verdict]`

## Playbook Integration

When a playbook exists for the clause type:
- **preferred**: The ideal position. This is what we want.
- **acceptable**: We can live with this. No need to fight.
- **fallback**: Our bottom line. Accept only if necessary.
- **prohibited**: Never accept. If present, grade as Critical.

When no playbook exists:
- Use the matched template clause text as baseline
- Set `playbook_missing: true` in the analysis
- Apply general contract law principles for risk assessment

## Context-Sensitive Analysis

Matter context values from `matter-context.yaml` prescribe specific adjustments to default risk grading — they are not advisory.

### Leverage Rules

- **`leverage: high`**: For all `priority_areas` clause types, upgrade base risk by one tier (Medium → High, Low → Medium). For all other clauses, apply review mode at `strict` regardless of `review-mode.yaml` default.
- **`leverage: low`**: Restrict Must-have list to Critical only. Do not generate redlines for High items unless they are explicitly listed in `priority_areas`.
- **`leverage: moderate`**: Apply default review mode without adjustment.

### Priority Areas Rules

If a `clause_type` is in `priority_areas`:
- `leverage: high` → treat as High even if base grade is Medium or Low; always include in Key Issues list
- `leverage: moderate` → treat as Medium even if base grade is Low; include in Key Issues list
- `leverage: low` → treat as Medium; include in Key Issues list even when operating in loose mode
- **Priority area items are always included in the Key Issues list regardless of review mode threshold.**

### Party Role Rules

- **`party_role: house`** (우리 측 초안): Focus on counterparty's proposed deviations from our draft. Asymmetries that favor us are acceptable by design; do not flag them.
- **`party_role: counterparty`** (상대방 초안): Apply full four-lens analysis. Default assumption is the draft is counterparty-favorable; scrutinize every asymmetry.
- **`party_role: neutral`** (공동 협상): Flag asymmetries in both directions with no default favorability assumption.
- **`party_role: internal`** (내부 문서): Apply criteria appropriate for internal policies; audience firewall rules do not apply.

## Redline Suggestion Rules

1. Redline text must be in the **contract's original language**
2. Draw from the fallback ladder when available
3. Make the minimum change necessary to bring the clause to an acceptable position
4. Preserve the counterparty's structure and numbering where possible
5. Never introduce new obligations not present in the original

## General Review Mode

When the library is empty, or retrieval returns no usable library candidates:
- State clearly: "This review was performed in general review mode without house position comparison"
- Base analysis on general contract law principles only
- Focus on identifying one-sided provisions, missing protections, and ambiguities
- Omit house position comparison entirely
- Risk grading is still applicable — use market standards as the reference point

---

## Korean Contract Risk Reference

Use when reviewing Korean-law contracts or operating in general review mode. These reflect Korean statutory baselines and market practice as of 2026.

### Investment Contracts (투자 계약)

**SAFE / 조건부지분전환계약**
- No conversion mechanism, discount rate, or valuation cap → Critical (투자자 전환 이익 없음)
- No anti-dilution protection (가중평균 또는 완전희석 방식 미포함) → High
- No investor information rights → High

**SHA / 주주간계약**
- Drag-along right with no minimum threshold or founder carve-out → Critical
- Tag-along right absent for minority shareholders → High
- Information rights absent (financial statements, board minutes) → High
- Board seat or observer right unspecified for major investor (≥ 5%) → Medium

**주식인수계약 (SPA / SSA)**
- No MAC (Material Adverse Change) clause → High
- Indemnification cap below purchase price → High
- No disclosure schedule requirement for representations → Medium
- Convertible bond / bond-with-warrants issuance terms omit allocation, payment account, annexed conditions, or denomination mechanics (사채 발행조건 불명확) → High

### Asset Purchase Agreements (영업양수도 · 자산양수도계약)

- Transferred assets and excluded assets are not clearly scheduled (양수 자산 / 제외 자산 특정 불충분) → High
- Assumed liabilities are vague, shifting unknown obligations to buyer (승계채무 불명확) → High
- No third-party consent or permit transfer condition for key assets/contracts (승계 동의 / 인허가 조건 부재) → High
- Employee-transfer or transition-services arrangements are missing where the business must continue seamlessly (인력승계 / 전환지원 부재) → Medium
- Indemnification does not cover title defects, retained liabilities, or tax leakage (권리하자 / 유보채무 / 세무누수 면책 부재) → High

### Joint Venture Contracts (합작투자계약)

- Capital contributions or follow-on funding obligations are unclear (출자 / 추가 자금부담 불명확) → High
- Reserved matters or board-control mechanics create hidden deadlock risk (지배구조 / 주요결의사항 불명확) → High
- No deadlock-resolution mechanism for 50:50 or closely split ownership (교착상태 해결 부재) → High
- Exit / transfer restrictions trap parties without liquidity path (exit / 양도 메커니즘 부재) → Medium
- Dividend policy or related-party restrictions are absent, enabling value leakage (배당정책 / 관계자거래 통제 부재) → Medium

### Merger Agreements (합병계약)

- No merger conditions precedent or shareholder / regulatory approval framework (합병 선행조건 / 승인 절차 부재) → Critical
- Merger consideration or exchange ratio lacks objective mechanics (합병대가 / 교환비율 불명확) → High
- No pre-closing covenants preserving ordinary-course conduct (통상영업 유지 의무 부재) → High
- Closing / effective-time mechanics do not align with statutory merger steps (효력발생 / 종결 절차 불명확) → High
- Employee, benefit, or integration obligations are ignored where business continuity matters (인력 / 통합 의무 부재) → Medium

### NDA / 비밀유지계약

- 비밀유지 기간 less than 2 years post-termination, or no fixed end date → Medium
- No mutual confidentiality obligation in bilateral NDA → Medium
- No return or destruction of materials obligation on termination → Low

### Service / SaaS 계약

- No liability cap (책임 한도 없음) → Critical
- No consequential damages exclusion → High
- Work product IP ownership (용역 결과물 귀속) unspecified → High
- No SLA or uptime commitment for SaaS → Medium
- No data export / return mechanism at termination for SaaS → High
- Broad suspension right without notice or cure window → High

### License Contracts (라이선스계약)

- No clear license scope, territory, exclusivity, or sublicensing limits (이용범위 불명확) → High
- No IP infringement indemnity from licensor (권리침해 면책 부재) → High
- Exclusive or perpetual license without clear termination or performance guardrails → High
- No survival language for use restrictions, payment, or confidentiality after termination → Medium

### IP Transfer / Assignment Contracts (지식재산권 양도계약)

- Assigned IP not specifically identified or scheduled (양도 대상 특정 불충분) → High
- No consideration trigger or transfer timing clarity (대가 / 이전 시점 불명확) → High
- No moral-rights waiver / non-assertion for copyrighted works (저작인격권 불행사 부재) → Medium
- Assignor gives weak title / authority reps or broad knowledge qualifiers only (권리 보유 진술 약함) → High
- No further-assurances duty for registration or recordation (등록 협력 부재) → Medium

### Content Distribution Contracts (콘텐츠 유통 · 배급계약)

- No clear grant of rights, platform scope, or territory (유통권 범위 불명확) → High
- No royalty statement / reporting or audit right (정산자료 / 감사권 부재) → High
- Minimum guarantee, advance recoupment, or revenue-share waterfall is unclear (MG / 정산 구조 불명확) → High
- No launch / takedown coordination or reversion mechanics at termination (출시 / 종료 / 권리복귀 부재) → Medium
- Distributor receives broad publicity rights without creator approval guardrails (홍보권 남용 가능) → Medium

### Publishing Contracts (출판계약)

- Grant of rights, territory, or format scope is unclear (권리범위 / 지역 / 형식 불명확) → High
- Editorial rights allow material changes without author approval (편집권 과도) → High
- Royalties, advance recoupment, or accounting mechanics are vague (인세 / 선급금 / 정산 불명확) → High
- No publication deadline, out-of-print trigger, or reversion path (출간기한 / 절판 / 권리복귀 부재) → High
- Adaptation rights bundled by default without separate consideration (2차적 이용권 과도 포함) → Medium

### Game Development Contracts (게임개발계약)

- Milestone and acceptance standards are subjective or missing (마일스톤 / 검수 기준 부재) → High
- Creative-control rights let publisher override core game design without balance guardrails (크리에이티브 승인권 과도) → High
- IP ownership between base game, tools, updates, and live-ops assets is unclear (IP 귀속 불명확) → High
- No ratings / platform compliance allocation before launch (등급분류 / 플랫폼 규제 준수 부재) → High
- No live-operations or source-code escrow fallback where publisher dependency is high (라이브옵스 / 에스크로 부재) → Medium

### Independent Contractor Contracts (업무위탁계약)

- Contractor arrangement imposes employee-like control without employment protections (근로자성 오인 위험) → High
- No IP assignment for contractor work product (결과물 권리귀속 불명확) → High
- No confidentiality obligation on contractor → High
- Contractor treated as agent/employee for taxes or authority without clear allocation → Medium

### Purchase & Sales / Supply Contracts (물품매매 · 공급계약)

- No product specification or acceptance procedure (규격/검수 절차 부재) → High
- No quality warranty, replacement, or repair remedy (품질보증 부재) → High
- No delivery schedule or minimum supply commitment where continuity matters → Medium
- No compliance / safety allocation for supplied goods → Medium

### Marketing Contracts (마케팅 · 광고계약)

- No clear deliverable, posting schedule, or KPI baseline (산출물 / 게시일정 / KPI 부재) → High
- Advertiser approval rights allow false or non-compliant advertising demands (허위·과장 광고 위험) → High
- No sponsorship / ad-disclosure compliance allocation under advertising law or platform rules (광고표시 준수 부재) → High
- Publicity / content reuse rights are broader than the campaign purpose (콘텐츠 2차 활용 과도) → Medium
- Exclusivity or category restrictions are open-ended in scope or duration (경업제한 과도) → Medium

### Statement of Work / 과업지시서

- No milestone schedule or objective acceptance window (마일스톤 / 검수 기준 부재) → High
- No change-order process for scope creep (범위 변경 절차 부재) → High
- Client dependencies / assumptions omitted, shifting schedule risk silently (발주인 협조사항 부재) → Medium
- Background IP and foreground deliverable ownership not split (기존 IP / 산출물 권리 분리 부재) → High
- SOW conflicts with governing MSA and no order-of-precedence clause exists (기본계약과 충돌) → Medium

### Employment Contracts (근로계약)

- Salary below minimum wage (최저임금 미달) → Critical (근로기준법 위반)
- Working hours exceeding 52 hours/week without lawful overtime framework → Critical
- No retirement pay provision for employment ≥ 1 year (퇴직금 미적립) → Critical (근로기준법 제34조)
- Non-compete clause (경업금지) exceeding 2 years without separate compensation → High

### Lease Contracts (임대차계약)

- No clear premises description or ambiguous leased area (목적물 특정 불충분) → High
- No deposit return mechanics or landlord return deadline (보증금 반환 절차 부재) → High
- Repair obligations shifted entirely to tenant for structural defects (구조적 하자 수선의무 전가) → High
- Broad early termination / eviction right without cure or refund mechanism → High
- No permitted-use clause where zoning / building-use restrictions matter → Medium
- No restoration / surrender allocation at expiry (원상복구 범위 불명확) → Medium

### Data Protection (개인정보 보호법 / PIPA)

- Personal information collection without consent mechanism → Critical
- No purpose limitation clause (수집 목적 미특정) → High
- Third-party transfer without data subject consent framework → High
- Retention period unspecified → Medium
- No security measures obligation → High

### Terms of Service (이용약관)

- Broad unilateral amendment right without advance notice or withdrawal option (일방적 약관 변경) → High
- Paid-service terms omit refund / cancellation disclosures required by consumer law (환불 / 청약철회 고지 누락) → High
- Suspension / termination allows immediate permanent cutoff without notice or cure except emergencies (이용정지 남용) → High
- Liability disclaimer purports to exclude willful misconduct, gross negligence, or non-waivable consumer rights (강행규정 위반 가능) → Critical
- User-content license is broader than necessary for service operation (게시물 이용허락 과도) → Medium

### EULA (최종사용자 사용권계약)

- License restrictions are vague, but termination is immediate and one-sided (제한은 모호하고 해지는 과도) → High
- Reverse-engineering / transfer restrictions exceed statutory interoperability or fair-use allowances without carve-outs (과도한 사용제한) → Medium
- Warranty disclaimer or liability cap tries to waive non-excludable statutory rights (강행규정상 배제 불가 권리 침해) → High
- No deletion / cessation obligation at termination, leaving post-termination use ambiguity (종료 후 사용정리 부재) → Medium
- Open-source / third-party component notices absent despite bundled components (오픈소스 고지 부재) → Medium

### Privacy Policies (개인정보처리방침)

- No disclosure of processing purposes, retention periods, third-party provision, or entrustment baseline required by PIPA disclosure rules → Critical
- No data-subject rights section or exercise method (권리행사 방법 부재) → High
- Cross-border transfer disclosure omitted where overseas storage / support exists (국외이전 고지 누락) → High
- No security-measures disclosure or privacy-contact channel (안전조치 / 책임자 정보 부재) → High
- Breach response / complaint handling path absent (침해 대응 / 민원 창구 부재) → Medium

### Data Processing Agreements (개인정보 처리위탁계약)

- No written processing instructions or prohibition on out-of-scope processing (처리지시 / 목적외 처리금지 부재) → Critical
- No security-measures clause or breach-notification duty on processor (안전조치 / 침해사고 통지 부재) → High
- No controller approval for sub-processing / re-entrustment (재위탁 통제 부재) → High
- No audit / supervision right for controller (점검 / 감독권 부재) → High
- No return / deletion clause at termination or no processor fault allocation (종료 시 반환·삭제 / 책임 배분 부재) → High

### MOU (양해각서)

- The document is labeled “non-binding,” but binding carve-outs are not clearly isolated (비구속 / 구속 조항 혼재) → High
- No confidentiality or cost-allocation clause during collaboration talks (비밀유지 / 비용부담 부재) → Medium
- Cooperation scope is aspirational only and leaves key assumptions ambiguous (협력 범위 모호) → Medium
- No clear expiry date, causing stale obligations or negotiation drift (유효기간 부재) → Low

### LOI (의향서)

- Exclusivity / no-shop is binding but duration or scope is undefined (독점교섭 과도) → High
- Indicative price or structure reads like a final obligation without diligence carve-outs (예정 거래조건 과도한 확정성) → High
- Binding vs. non-binding sections are not separated clearly (구속력 구분 불명확) → High
- No confidentiality or expense allocation during deal negotiations (비밀유지 / 비용 분담 부재) → Medium
- No conditions precedent for final documentation or approvals (최종계약 선행조건 부재) → Medium

### Settlement Agreements (합의서)

- Release language is too narrow, leaving related claims unresolved, or too broad without carve-outs (청구권 포기 범위 불명확) → High
- No covenant not to sue / dismissal cooperation for pending disputes (부제소 / 소취하 협력 부재) → High
- No-admission, confidentiality, or non-disparagement terms are missing where reputation matters (책임불인정 / 비밀유지 / 비방금지 부재) → Medium
- Payment default has no acceleration or remedy mechanics (합의금 미지급 대응 부재) → High
- Settlement tries to waive non-waivable statutory rights or claims of third parties (강행규정 / 제3자 권리 침해) → Critical

### Other / Amendments / Side Letters (기타 변경계약 · 부속합의)

- Amendment does not identify the base agreement or target provisions precisely (원계약 / 변경 조문 특정 불충분) → High
- Amendment text conflicts with the base agreement and no priority rule resolves the inconsistency (충돌우선 규칙 부재) → High
- Effective date, retroactivity, or dependency on closing events is unclear (효력발생 시점 불명확) → Medium
- Unchanged provisions are not expressly ratified, creating avoidable interpretive disputes (미변경 조항 유지 확인 부재) → Medium
- Side letter grants selective waivers or bespoke economics without clear scope or sunset (부속합의 특혜 / 예외 범위 불명확) → Medium

---

## Executive Summary Template

When generating the Executive Summary for the analysis report (WF2 Step 10), always use this structure:

### Section 1 — Contract Overview (2–3 sentences)
- Contract type, parties, and principal transaction structure
- Contract language, jurisdiction, and governing law

### Section 2 — Overall Risk Assessment
- Overall risk level: **Critical** | **High** | **Medium** | **Low**
  - Critical: one or more Critical-grade issues present
  - High: no Critical issues, but High-grade issues present
  - Medium / Low: graded accordingly
- Risk distribution table:

| Risk Level | Count |
|------------|-------|
| 🔴 Critical | N |
| 🟠 High | N |
| 🟡 Medium | N |
| 🔵 Low | N |
| ✅ Acceptable | N |

### Section 3 — Key Issues (ordered Critical → High → Medium)

List each issue as:
`[Section No.] [Issue Title] — [1–2 sentence description of the problem and its impact on the client]`

Include: all Critical issues + top 3 High issues. If Critical+High total is fewer than 5, include Medium issues to reach 5.

### Section 4 — Negotiation Priority
- **Must-haves** (Critical): Items that must be revised for the deal to be acceptable
- **Should-haves** (High): Items to negotiate; not individual dealbreakers but significant
- **Nice-to-haves** (Medium): Items worth raising if leverage and negotiating capital permit

### Section 5 — Review Notes
- Library mode: "House position comparison active" or "General review mode — no library match"
- Any review limitations (bilingual discrepancies, exhibits not analyzed, large-document chunking applied, etc.)
- Review date

### JSON Field Mapping for compile-report.js

When populating the `executive_summary` object in the review data JSON at Step 10, map the five template sections to the existing schema fields as follows:

| Template Section | JSON Field | Format |
|---|---|---|
| Section 1 — Contract Overview | Opening lines of `recommendation` | 2–3 sentences of prose |
| Section 2 — Overall Risk Assessment | `overall_risk` (string) + `risk_distribution` (object) | `"high"` / `{"critical":1,"high":3,...}` |
| Section 3 — Key Issues | `key_issues` (array) | Each item: `"[§No.] [Title] — [description]"` |
| Section 4 — Negotiation Priority | Middle paragraph of `recommendation` | Must-haves / Should-haves / Nice-to-haves prose |
| Section 5 — Review Notes | Final lines of `recommendation` | One line per note |

The `recommendation` field therefore carries Sections 1, 4, and 5 in sequence. The script renders it as a continuous narrative block; the three sections are separated by blank lines within the field.
