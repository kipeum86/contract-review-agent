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
