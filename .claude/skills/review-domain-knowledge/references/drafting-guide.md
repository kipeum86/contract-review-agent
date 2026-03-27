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
- Debt Security Issuance Terms for CB/BW deals: amount, denomination, allocation, annexed terms, payment account (전환사채/신주인수권부사채 발행조건)
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

### APA / 영업양수도 · 자산양수도계약

- Transferred Assets / Excluded Assets (양수 자산 / 제외 자산)
- Assumed Liabilities / Retained Liabilities (승계 채무 / 유보 채무)
- Purchase Price and adjustment mechanics (양수대금 / 가격조정)
- Conditions precedent and third-party consents (선행조건 / 제3자 동의)
- Seller reps and warranties on title, contracts, tax, compliance (매도인 진술·보증)
- Employee transfer / labor allocation (인력 승계 / 고용 이슈)
- Transition assistance / handover (인수 후 전환지원)
- Indemnification and post-closing support (면책 / 사후지원)

### Joint Venture / 합작투자계약

- Purpose and business scope of the JV (JV 목적 / 사업범위)
- Capital contributions and funding obligations (출자 / 추가 자금조달)
- Board composition and reserved matters (이사회 구성 / 주요결의사항)
- Information rights and reporting (정보권 / 보고의무)
- Transfer restrictions and exit mechanics (지분양도 제한 / exit)
- Non-compete / exclusivity where needed (경업제한 / 독점)
- Dividend policy / profit distribution (배당정책 / 이익배분)
- Deadlock resolution mechanism (교착상태 해결)

### Merger / 합병계약

- Merger structure and merger consideration (합병 구조 / 합병대가)
- Conditions precedent and regulatory approvals (선행조건 / 인허가)
- Pre-closing covenants and ordinary-course conduct (선행의무 / 통상영업 유지)
- Closing / effective-time mechanics (거래종결 / 효력발생)
- Party representations and warranties (당사자 진술·보증)
- Employee and benefit continuity (임직원 / 복리후생 처리)
- Integration / post-closing cooperation (통합 / 사후협력)
- Indemnification or special risk allocation where negotiated (특별 위험배분 / 면책)

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

### Independent Contractor / 업무위탁계약

- Scope of Services / Statement of Work (업무 범위 / 개별 발주)
- Deliverables & Acceptance (산출물 / 검수)
- Fees, Expenses, and Invoicing (보수 / 비용 / 청구)
- Confidentiality (비밀유지)
- IP Assignment for Work Product (결과물 권리 이전)
- Independent Contractor Status (독립된 계약관계)
- Subcontracting restrictions (재위탁 제한)
- Term & Termination (기간 및 해지)

### Purchase & Sales / 물품매매 · 공급계약

- Product Description / Specifications (물품 설명 / 규격)
- Delivery Schedule & Acceptance (납품 일정 / 검수)
- Price & Payment Terms (대금 / 지급조건)
- Minimum Purchase / Supply Commitment (최소 발주 / 공급 의무)
- Quality Warranty / Replacement Remedy (품질보증 / 교환·수리)
- Compliance with Laws / Safety Standards (법규준수 / 안전기준)
- Indemnification for Product Defects / IP Claims (하자·권리침해 면책)
- Term & Termination (기간 및 해지)

### Statement of Work / 과업지시서

- Statement of Work hierarchy against master agreement (개별 과업지시서와 기본계약의 우선순위)
- Scope of Work / Deliverables (업무 범위 / 산출물)
- Milestones and Acceptance windows (마일스톤 / 검수 기간)
- Client Dependencies / Assumptions (발주인 협조사항 / 전제조건)
- Change Order mechanics (변경요청 절차)
- Fees, milestone payment, and expenses (대금 / 단계별 지급 / 실비)
- Background IP vs. Foreground IP (기존 IP / 신규 산출물 권리)
- Term & Termination for the project order (개별 과업 종료 / 해지)

### SaaS / 소프트웨어 구독계약

- Subscription Scope & Access (구독 범위 및 접근권한)
- SLA / Uptime Commitment (가용성 보장)
- Data Ownership & Portability (데이터 소유권 및 이전)
- Data Security & Processing (데이터 보안 및 처리)
- Limitation of Liability (책임의 제한)
- Auto-Renewal & Opt-Out (자동갱신 및 해지)
- Suspension / Termination Rights (이용 정지 / 해지)
- Warranty Disclaimer (보증의 배제)

### IP Transfer / 지식재산권 양도계약

- Assigned IP definition and schedule (양도 대상 IP 특정)
- Transfer timing and consideration (권리 이전 시점 / 대가)
- Moral Rights Waiver / Non-Assertion (저작인격권 불행사)
- Title, authority, and non-infringement representations (권리 보유 / 권한 / 비침해 진술)
- Further Assurances for registration and recordation (등록 / 신고 협력)
- Indemnity for title defects or third-party claims (권리하자 / 제3자 청구 면책)

### Content Distribution / 콘텐츠 유통 · 배급계약

- Grant of Distribution Rights (유통권 부여 범위)
- Territory, platform, and media scope (지역 / 플랫폼 / 매체)
- Launch schedule and takedown coordination (출시 일정 / 서비스 중단 절차)
- Revenue share, minimum guarantee, and statements (수익배분 / MG / 정산자료)
- Audit rights over statements (정산 감사권)
- Marketing / publicity approvals (홍보 / 표지 / 상호 사용)
- Compliance with copyright, youth, and advertising rules (저작권 / 청소년 / 광고 규제 준수)
- Reversion of rights on expiry or termination (종료 시 권리 복귀)

### Terms of Service / 이용약관

- Service description and eligibility (서비스 내용 / 가입 자격)
- Account security and user obligations (계정 보안 / 이용자 의무)
- Paid service pricing, billing, and refund disclosures (요금 / 결제 / 환불 고지)
- Withdrawal / cancellation rights where required (청약철회 / 해지권)
- User content license and IP notice (게시물 이용허락 / 권리 고지)
- Amendment notice windows for unfavorable changes (불리한 약관 변경 사전 공지)
- Privacy-policy linkage and data protection notice (개인정보처리방침 연계)
- Suspension / termination with notice and cure logic (이용제한 / 해지 / 통지)
- Liability limits and non-excludable statutory rights carve-out (책임제한 / 강행규정 carve-out)

### EULA / 최종사용자 사용권계약

- License grant and device / user scope (사용권 부여 / 설치 범위)
- Restrictions on transfer, reverse engineering, and circumvention (양도 / 역분석 / 우회 금지)
- Open-source and third-party component notices (오픈소스 / 제3자 구성요소 고지)
- IP ownership and reservation of rights (지식재산권 귀속 / 권리 유보)
- Warranty disclaimer and liability cap with statutory carve-outs (보증배제 / 책임한도)
- Termination and post-termination deletion duties (해지 / 사본 삭제)
- Export control / sanctions compliance if software is distributed cross-border (수출통제 / 제재 준수)

### Privacy Policy / 개인정보처리방침

- Processing purposes and data categories (처리 목적 / 처리 항목)
- Lawful basis or consent disclosures where required (동의 / 처리 근거)
- Retention periods and destruction method (보유기간 / 파기 절차)
- Third-party provision disclosure (제3자 제공 고지)
- Entrustment / processor disclosure (처리위탁 공개)
- Cross-border transfer disclosure and consent path (국외이전 고지 / 동의)
- Data-subject rights and exercise method (정보주체 권리 / 행사 방법)
- Security measures and breach response notice (안전조치 / 침해 대응)
- Privacy officer / complaint channel (보호책임자 / 민원 창구)

### Data Processing Agreement / 개인정보 처리위탁계약

- Documented processing instructions and purpose limitation (문서화된 처리지시 / 목적 제한)
- Security controls required of processor (수탁자 안전조치)
- Sub-processor approval and flow-down obligations (재위탁 승인 / 동일 의무 전가)
- Breach notification timing and cooperation (침해사고 통지 / 협조)
- Audit / inspection rights for controller (위탁자 점검 / 감사권)
- Assistance with data-subject requests and regulator inquiries (권리행사 / 감독기관 대응 협조)
- Cross-border transfer restrictions (국외이전 제한)
- Return / deletion at end of services (종료 시 반환 / 삭제)
- Liability allocation for processor fault (수탁자 책임 배분)

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

### Marketing / 마케팅 · 광고계약

- Campaign scope and channels (캠페인 범위 / 채널)
- Content deliverables and posting schedule (콘텐츠 산출물 / 게시 일정)
- Brand review and approval rights (브랜드 검토 / 승인권)
- Fee structure: fixed, milestone, performance-based (고정비 / 단계별 / 성과형 보수)
- Expense allocation (촬영비 / 매체비 / 소품비 등)
- Sponsorship / ad disclosure compliance (광고표시 / 협찬 고지 준수)
- IP / publicity rights in created content (콘텐츠 저작권 / 성명·초상 사용)
- Exclusivity / category restrictions (경쟁 브랜드 제한)
- Indemnity for false claims or infringement (허위광고 / 권리침해 면책)

### MOU / 양해각서

- Cooperation purpose and business scope (협력 목적 / 범위)
- Information sharing framework (정보교환 구조)
- Confidentiality (비밀유지)
- Cost allocation during discussions (협의 비용 분담)
- Escalation / meeting governance (협의체 / 대표자 협의)
- Term / expiry (유효기간)
- Binding vs. non-binding carve-outs (구속력 / 비구속력 구분)
- Governing law for binding sections (구속력 있는 조항의 준거법)

### LOI / 의향서

- Indicative transaction structure or pricing (예정 거래 구조 / 가격)
- Due diligence access (실사 접근권)
- Exclusivity / no-shop (독점교섭)
- Confidentiality (비밀유지)
- Expense allocation (비용 부담)
- Conditions precedent to final deal (최종 계약 선행조건)
- Expiry window (유효기간)
- Binding vs. non-binding clause split (구속력 / 비구속력 구분)
- Governing law / forum for binding terms (구속력 있는 조항의 준거법 / 관할)

### Settlement / 합의서

- Settlement payment mechanics (합의금 지급 구조)
- Release of claims (청구권 포기 / 해제)
- Covenant not to sue / dismissal cooperation (부제소 / 소취하 협력)
- No-admission language (책임 불인정)
- Confidentiality (비밀유지)
- Non-disparagement where commercially important (비방금지)
- Further assurances / closing actions (후속 문서 / 절차 협력)
- Governing law / jurisdiction (준거법 / 관할)

### Other / 기타 부속합의서

- Referenced base agreement and amendment scope (원계약 특정 / 변경범위)
- Effective date and retroactivity if needed (효력발생일 / 소급효)
- Clause replacement text or schedule-based amendment matrix (변경문안 / 조문대체표)
- Ratification of unchanged provisions (미변경 조항 유지 확인)
- Priority rule if the amendment conflicts with the base agreement (충돌 시 우선순위)
- Counterparts / e-signature mechanics where used operationally (사본 / 전자서명)

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
