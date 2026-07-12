## Highlights

Security review follow-up + pipeline performance improvements. Update recommended for all users.

```bash
git pull origin main
```

## 🔒 Security
* Add `<untrusted_contract_content>` framing protocol for review-agent & ingestion-agent
* Sanitize prompt-injection tokens in redline extraction + audit log (EN·KO)
* Review workflow safety and reliability updates (#1)

## ⚡ Performance
* Pre-Pipeline 0.5 document size check with manual-split warning
* Redline plumbing — explicit schema references + fail-loud guard
* compile-report.js `validateClauseCompleteness` assertion

**Tests:** 144 / 144 ✅  ·  **Migration:** not required  ·  **policies/ customizations:** preserved

---

<details>
<summary><b>🇰🇷 한국어</b></summary>

## 주요 변경사항

보안 검토 후속 개선 + 파이프라인 성능 개선. 전체 사용자 업데이트 권장.

```bash
git pull origin main
```

### 🔒 보안
* review-agent · ingestion-agent에 `<untrusted_contract_content>` 프레이밍 프로토콜 추가
* Redline 추출 단계에서 프롬프트 인젝션 토큰 정화 + 감사 로그(한·영 양방향)
* 리뷰 워크플로 안전성 및 신뢰성 개선 (#1)

### ⚡ 성능
* Pre-Pipeline 0.5 문서 크기 사전 점검 + 수동 분할 안내
* Redline 파이프: 명시적 스키마 참조 + fail-loud 가드
* `compile-report.js` `validateClauseCompleteness` 단언문

**테스트:** 144 / 144 ✅  ·  **마이그레이션:** 불필요  ·  **`policies/` 커스터마이즈:** 보존

</details>
