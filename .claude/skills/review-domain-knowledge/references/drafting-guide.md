# Contract Drafting Guide

Domain knowledge for contract generation: structure, family checklists, statutory baselines, and self-review methodology.

---

## Standard Contract Structure

All contracts should follow this structural skeleton. Include or omit sections as appropriate for the contract type.

```
1.  Title & Date / 계약서 제목 및 날짜
2.  Parties / 당사자 (full legal names, registration numbers, addresses)
3.  Recitals / 전문 (배경)
4.  Definitions / 정의
5.  [Operative Clauses — varies by contract type]
6.  Representations & Warranties / 진술 및 보증
7.  Liability & Indemnification / 책임 및 면책
8.  Confidentiality / 비밀유지
9.  Term & Termination / 기간 및 해지
10. Dispute Resolution / 분쟁해결
11. General Provisions / 일반조항
    (Entire Agreement, Amendment, Assignment, Notices, Severability,
     Waiver, Force Majeure, Governing Language, Counterparts)
12. Signature Blocks / 서명란
```

---

## Contract-Family-Specific Checklists

Essential clauses for each family. If any is missing from the draft, flag it in self-review.

### NDA / 비밀유지계약

- Definition of Confidential Information (비밀정보의 정의)
- Obligations of Receiving Party (수신자의 의무)
- Permitted Disclosures / Exceptions (예외사항)
- Term of Confidentiality Obligation (비밀유지 기간) — minimum 2 years post-termination for Korean-law NDAs
- Return or Destruction of Materials (자료 반환/파기)
- Remedies / Injunctive Relief (구제수단)
- Mutual vs. One-Way obligation (상호 vs. 일방)

### License Agreement / 라이선스계약

- Grant of License (이용허락)
- License Scope: territory, exclusivity, sublicensing (영역, 독점성, 재허락)
- License Fee / Royalties (대가 / 로열티)
- IP Ownership (지식재산권 귀속)
- Restrictions on Use (사용 제한)
- Warranties & Indemnification for IP Infringement (IP 침해 면책)
- Term & Termination with license survival (존속 조항)
- Audit Rights (감사권)

### SPA / SSA / 주식양수도계약 · 주식인수계약

- Purchase/Subscription Price & Payment (대금 및 지급)
- Conditions Precedent to Closing (선행조건)
- Representations & Warranties — Seller and Buyer (진술 및 보증)
- Pre-Closing Covenants (선행의무)
- Material Adverse Change (MAC) Clause
- Indemnification: basket, cap, survival period (면책: 기준금액, 상한, 존속기간)
- Disclosure Schedules (공시 별지)
- Closing Mechanics (거래종결 절차)
- Post-Closing Covenants: non-compete, transition (사후의무)

### SHA / 주주간계약

- Board Composition & Governance (이사회 구성)
- Information Rights / Reporting (정보접근권)
- Tag-Along Rights (동반매도참여권)
- Drag-Along Rights (동반매도청구권) — require minimum threshold
- Preemptive Rights / Anti-Dilution (선매권 / 희석방지)
- Right of First Refusal (우선매수권)
- Transfer Restrictions / Lock-Up (양도제한)
- Dividend / Distribution Policy (배당정책)
- Liquidation Preference (잔여재산분배 우선권)
- Deadlock Resolution (교착상태 해결)

### SAFE / 조건부지분전환계약

- Investment Amount (투자금액)
- Valuation Cap & Discount Rate (기업가치 상한 / 할인율)
- Conversion Mechanics: triggering events, conversion formula (전환 조건 및 산식)
- Anti-Dilution Protection (희석방지)
- Investor Information Rights (투자자 정보권)
- MFN (Most Favored Nation) Clause, if applicable
- Dissolution / Liquidity Event Provisions (해산 / 유동성 이벤트)

### Service Agreement / 용역계약 (MSA)

- Scope of Services / Deliverables (용역 범위 / 산출물)
- Service Levels / SLA (서비스 수준)
- Fees & Payment Terms (대금 및 지급조건)
- IP Ownership of Work Product (결과물 귀속)
- Acceptance Criteria (검수 기준)
- Limitation of Liability / Liability Cap (책임 제한)
- Exclusion of Consequential Damages (간접손해 배제)
- Confidentiality (비밀유지)
- Subcontracting restrictions (재위탁 제한)

### SaaS / 소프트웨어 구독계약

- Subscription Scope & Access (구독 범위 및 접근권한)
- SLA / Uptime Commitment (가용성 보장)
- Data Ownership & Portability (데이터 소유권 및 이전)
- Data Security & Processing (데이터 보안 및 처리)
- Limitation of Liability (책임의 제한)
- Auto-Renewal & Opt-Out (자동갱신 및 해지)
- Suspension / Termination Rights (이용 정지 / 해지)
- Warranty Disclaimer (보증의 배제)

### Employment / 근로계약

- Position & Duties (직위 및 업무)
- Compensation: salary, bonuses, benefits (급여, 상여, 복리후생)
- Working Hours & Overtime Framework (근로시간 및 초과근로)
- Term & Probation (기간 및 수습)
- Retirement Pay / Severance (퇴직금) — mandatory for employment ≥ 1 year under Korean law
- Confidentiality & Non-Compete (비밀유지 및 경업금지)
- IP Assignment / Work-for-Hire (직무발명 / 업무상저작물)
- Termination & Notice (해고 및 통지)

### Publishing / 출판계약

- Grant of Rights: scope, territory, format (권리 부여)
- Royalties / Advance (인세 / 선급금)
- Delivery of Manuscript (원고 납품)
- Editorial Rights & Author Approval (편집권 및 저자 승인)
- Publication Schedule (출간 일정)
- Adaptation / Derivative Work Rights (2차 저작물 권리)
- Reversion of Rights (권리 복귀)
- Out-of-Print Clause (절판 조항)
- Moral Rights (저작인격권)

### Game Development / 게임개발계약

- Development Milestones & Acceptance (개발 마일스톤 및 검수)
- Creative Control / Approval Rights (크리에이티브 승인권)
- IP Ownership: engine, assets, game IP (IP 귀속)
- Revenue Share / Royalties (수익배분)
- Platform Requirements / Certification (플랫폼 요구사항)
- Live Operations / Post-Launch Obligations (운영의무)
- Source Code Escrow (소스코드 에스크로)
- Localization (현지화)
- User Data Ownership (이용자 데이터 귀속)

### Lease / 임대차계약

- Premises Description (임대목적물)
- Rent & Deposit (차임 및 보증금)
- Term & Renewal (기간 및 갱신)
- Permitted Use (사용 용도)
- Maintenance & Repair Obligations (수선의무)
- Termination & Early Exit (해지 및 중도 퇴거)
- Security Deposit Return (보증금 반환)
- Assignment & Subletting (양도 및 전대)

---

## Korean Law Statutory Baselines

When drafting Korean-law contracts, ensure compliance with these statutory minimums. Violations must be flagged as Critical risk in self-review.

### Investment Contracts (투자 계약)

- SAFE without conversion mechanism, discount rate, or valuation cap → **Critical** (투자자 전환 이익 없음)
- SHA without anti-dilution protection (가중평균/완전희석 미포함) → **High**
- SHA drag-along without minimum threshold or founder carve-out → **Critical**
- SHA without tag-along for minority shareholders → **High**
- SPA/SSA without MAC clause → **High**
- SPA/SSA indemnification cap below purchase price → **High**

### Employment (근로기준법 기준)

- Salary below minimum wage (최저임금 미달) → **Critical** (위법)
- Working hours exceeding 52 hours/week without lawful overtime framework → **Critical**
- No retirement pay for employment ≥ 1 year (퇴직금 미적립) → **Critical** (근로기준법 제34조)
- Non-compete exceeding 2 years without separate compensation → **High**

### Data Protection (개인정보보호법 / PIPA)

- Personal information collection without consent mechanism → **Critical**
- No purpose limitation (수집 목적 미특정) → **High**
- Third-party transfer without data subject consent framework → **High**
- No security measures obligation → **High**
- Retention period unspecified → **Medium**

### NDA (비밀유지계약)

- Confidentiality period less than 2 years post-termination → **Medium**
- No mutual obligation in bilateral NDA → **Medium**
- No return/destruction obligation → **Low**

### Service / SaaS

- No liability cap (책임 한도 없음) → **Critical**
- No consequential damages exclusion → **High**
- Work product IP ownership unspecified → **High**
- No SLA/uptime commitment for SaaS → **Medium**

---

## Leverage-Based Tier Selection

The client's negotiation leverage determines which clause tiers to draw from the library:

| Leverage | Core Clauses | Secondary Clauses | Stance |
|----------|-------------|-------------------|--------|
| **High** (우위) | Preferred only | Preferred | Push for ideal terms; flag any deviation from house standard |
| **Moderate** (대등) | Preferred | Acceptable | Balanced; preferred for critical clauses, acceptable for others |
| **Low** (열위) | Acceptable | Selective fallback | Pragmatic; focus must-haves on Critical-risk items only |

---

## Generation Rules

### Defined Terms
- **Bold** on first use in the contract body
- Define all bolded terms in the Definitions section
- Use consistently throughout — never switch between a defined term and its plain-language equivalent

### Cross-References
- All internal references (e.g., "본 계약 제3조에 따라" / "pursuant to Article 3") must point to correct sections
- Verify after any section reordering or insertion

### Numbering
- Sequential, no gaps, no duplicates
- Korean-style: 제1조 (목적), 제2조 (정의), ... 제1항, 제2항, 제1호, 제2호
- English-style: Article 1. (Purpose), Article 2. (Definitions), ... Section 1.1, 1.2, (a), (b)

### Placeholders
- No TBD, $____, [●], or unfilled brackets in the final draft
- If a value is unavailable, mark with `[REVIEW NOTE: 확인 필요 — description]`
- All `[REVIEW NOTE]` items must appear in the self-review summary

### Signature Blocks
- Include: name, title, date, seal/signature for each party
- Korean contracts: include 법인인감 (corporate seal) or 서명 (signature) lines
- Bilingual contracts: parallel signature blocks in both languages

### Bilingual Contracts (국영문 병기)
- Draft both language versions with consistent section numbering
- Include a governing language clause (국문/영문 우선 조항) specifying which version prevails

---

## Self-Review Methodology

### Five-Point Checklist

| # | Check | What to Verify |
|---|-------|----------------|
| 1 | **Completeness** (완전성) | All sections from the family checklist are present |
| 2 | **Internal Consistency** (내부 정합성) | Defined terms consistent, cross-refs correct, numbering sequential, party names consistent |
| 3 | **Placeholders** (미완성 항목) | No TBD, [●], or unfilled brackets. All `[REVIEW NOTE]` items documented |
| 4 | **Risk Assessment** (위험 평가) | Apply four-lens framework below |
| 5 | **Missing Protections** (누락된 보호조항) | Standard clauses absent. Cross-check Korean law baselines for Korean-law contracts |

### Four-Lens Framework

Apply all four lenses to the generated draft:

1. **Asymmetries (비대칭성)** — Does any provision apply to one party differently? In a client-favorable draft, asymmetries favoring the client are by design; favoring the counterparty should be flagged.

2. **Overbroad Qualifiers (과도한 제한)** — Are knowledge qualifiers, materiality thresholds, or carve-outs used to hollow out protections? (e.g., "material breach" making termination impossible)

3. **Missing Protections (보호조항 누락)** — What standard provisions are absent? A missing clause is more dangerous than a bad one.

4. **Structural Traps (구조적 함정)** — Do individually neutral provisions combine for a one-sided outcome? (e.g., basket = cap making indemnification illusory)

### Risk Grading

| Grade | Symbol | Meaning |
|-------|--------|---------|
| Critical | 🔴 | Unacceptable exposure. Must revise. Statutory violation, unlimited liability, prohibited position. |
| High | 🟠 | Significant deviation. Should address. Unreasonable caps, missing exclusions, overbroad restrictions. |
| Medium | 🟡 | Notable deviation. May be acceptable in context. |
| Low | 🔵 | Minor deviation. Generally acceptable. |
| Acceptable | ✅ | Aligned with market standard. |

### Annotation Rules

- **Auto-fix**: numbering gaps, cross-reference errors, minor inconsistencies
- **Flag with `[REVIEW NOTE]`**: substantive issues inline in the draft
- `[REVIEW NOTE]` annotations are **internal-only** — strip when producing counterparty-facing clean version
