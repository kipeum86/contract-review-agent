# Seed Calibration Playbook

[English](./SEED-CALIBRATION-PLAYBOOK.md)

## Purpose

This playbook explains how to maintain and upgrade the project's synthetic seed templates over time without confusing:

- live matter review work
- library maintenance
- authority promotion

The short version is simple:

- We review real contracts case by case.
- We update seed calibration only when repeated real-world review evidence justifies it.
- We do not promote a seed to `preferred` unless a qualified external reviewer actually supports that decision.

This document is operational guidance. It is not legal advice and it does not replace lawyer judgment.

## What A Seed Is

A seed is a baseline library package under [`contract-review/library/approved/templates/`](../../contract-review/library/approved/templates/) created to give the retrieval system a usable starting point for a contract family that would otherwise have weak or zero coverage.

In the current system, synthetic seeds are intentionally conservative:

- they are allowed to be `acceptable`
- they are blocked from silently drifting into `preferred`
- they require explicit external review metadata before promotion

The control layer for that process lives in:

- [`seed-calibration-policy.yaml`](../../contract-review/library/policies.default/seed-calibration-policy.yaml)
- [`report_seed_calibration.py`](../../scripts/report_seed_calibration.py)
- [`build_seed_review_packets.py`](../../scripts/build_seed_review_packets.py)
- [`update_seed_calibration.py`](../../scripts/update_seed_calibration.py)

## What Calibration Is

Calibration is the process of deciding whether a seed should remain:

- a safe generic baseline
- a revised but still generic baseline
- split into narrower family variants
- or promoted to `preferred`

Calibration is not the same thing as editing one contract for one negotiation. A single matter can create useful evidence, but it should not automatically change the house baseline.

## Core Principles

### 1. Matter Review Comes First

The first job of the system is to review the contract in front of you. Seed maintenance is secondary.

If a live matter arrives, optimize for the live review outcome first:

- produce the review
- explain risk
- mark negotiation positions
- preserve work product

Only after that should you ask whether the matter revealed a reusable baseline improvement.

### 2. Calibration Must Be Evidence-Driven

A seed should move only because there is durable evidence that the baseline is market-usable or house-approved for that family.

Good evidence:

- repeated edits across multiple real matters
- stable guidance from external specialist counsel
- a partner-approved fallback position repeatedly used in practice
- a documented client policy that is meant to apply across deals in that family

Weak evidence:

- one-off counterparty markup
- one urgent compromise under time pressure
- aggressive ask from one client that is not the general house baseline
- stylistic preference without clear legal or operational significance

### 3. `Preferred` Is A High Bar

`preferred` should mean something close to:

- reliable as a house starting position
- legally and commercially coherent for the family
- externally reviewed by a qualified human
- unlikely to need immediate structural correction when reused

If there is any real doubt, keep the seed at `acceptable`.

### 4. Do Not Hide Uncertainty

If a family is broad or unstable, record that honestly.

Use:

- `keep_acceptable` when the seed is usable but not strong enough for `preferred`
- `needs_revision` when the wording is directionally right but still incomplete
- `needs_family_split` when one family label is masking materially different deal shapes

## When To Start A Calibration Pass

Start or continue seed calibration when one of these happens:

- the same family has been reviewed several times in live matters
- reviewers keep making the same edits to the same family baseline
- a family is high-frequency and operationally sensitive
- a family has regulatory disclosure risk or strong market-standard expectations
- a specialist reviewer has time to evaluate the baseline as a reusable form

Do not start a calibration pass just because:

- a matter exists
- one client wants unusual leverage
- the wording "looks nicer"

## Operational Separation: Matter Work vs Seed Work

### Matter Review Track

Use this when a real contract comes in.

Output:

- review report
- redlines
- negotiation recommendations
- matter-specific notes

Question:

- "What should we say about this draft right now?"

### Seed Calibration Track

Use this when you are deciding whether the library baseline itself should change.

Output:

- calibration metadata update
- optional baseline wording change
- optional authority promotion
- optional family split decision

Question:

- "Should the reusable library baseline change because of what we have now learned?"

## Recommended Review Cadence

Use a lightweight trigger and a heavier promotion threshold.

### Lightweight Trigger

Open a calibration question when:

- you have at least one meaningful real matter in the family
- the review generated reusable comments
- the issue is structural rather than deal-specific

### Promotion Threshold

Consider `preferred` only when most of the following are true:

- the family appears regularly enough to justify a house position
- the baseline has already survived real review use
- specialist review is completed
- major clause allocation is internally coherent
- no obvious structural gap remains
- the wording is broad enough for reuse but not so broad that it becomes misleading

## Default Workflow

### Step 1. Review The Live Matter

Perform the actual contract review first.

Capture:

- the incoming issue
- the proposed fix
- whether the fix is family-level or deal-level
- whether the issue was legal, operational, commercial, or drafting-related

### Step 2. Ask Whether The Learning Is Reusable

After the matter is done, ask:

- would we likely make this same edit again?
- is the issue caused by a weak family baseline?
- does the issue reflect house policy rather than one deal compromise?
- would future retrieval benefit if this seed were updated?

If the answer is mostly no, do not open a seed calibration action.

### Step 3. Generate The Current Queue And Packets

Run:

```bash
python3 scripts/report_seed_calibration.py
python3 scripts/build_seed_review_packets.py
```

Outputs:

- queue: [`output/seed-review-packets/queue.md`](../../output/seed-review-packets/queue.md)
- machine-readable queue: [`output/seed-review-packets/queue.json`](../../output/seed-review-packets/queue.json)
- one packet per family in `output/seed-review-packets/`

These outputs are local-only and gitignored under [`/output/*`](../../.gitignore).

### Step 4. Review The Packet With A Qualified Human

Open the family packet and review:

- family summary
- current blockers
- clause inventory
- cluster-specific checklist
- current authority level

The packet is a review aid, not the decision itself.

The reviewer should answer:

- is this family baseline structurally sound?
- is anything materially missing?
- is the family too broad and in need of splitting?
- is this reusable enough for `preferred`, or only safe enough for `acceptable`?

### Step 5. Choose The Right Calibration Outcome

Use one of the four recommendations.

#### `keep_acceptable`

Choose this when:

- the seed is usable
- the family baseline is directionally correct
- the wording is safe enough for retrieval and review assistance
- but you do not want to represent it as the firm's preferred starting paper

Typical result:

- external review status may be `completed`
- promotion blockers remain
- manifest authority stays `acceptable`

#### `promote_to_preferred`

Choose this only when:

- external review is actually completed
- the reviewer is comfortable endorsing the baseline as reusable starting paper
- the current wording does not depend on matter-specific assumptions
- no major structural change is still pending

Typical result:

- blockers become empty
- calibration metadata reflects completed review
- manifest may be promoted to `preferred`

#### `needs_revision`

Choose this when:

- the baseline is materially incomplete
- clause structure is usable but important wording needs revision
- the family is valid, but the current seed is not yet stable enough

Typical result:

- keep the seed at `acceptable`
- revise the seed text before reconsidering promotion

#### `needs_family_split`

Choose this when:

- the family label is too broad
- materially different deal shapes are being forced into one baseline
- a generic template would mislead retrieval or review

Examples:

- one data family needs separate B2B and consumer forms
- one IP family really contains assignment and license models with different risk logic
- one "other" pattern is being used for several unrelated side-letter structures

### Step 6. Record The Decision

Use the update script to write the calibration result.

Example: reviewed but still `acceptable`

```bash
python3 scripts/update_seed_calibration.py \
  --package-dir contract-review/library/approved/templates/nda/0-nda-mutual-seed \
  --external-status completed \
  --recommendation keep_acceptable \
  --reviewer-name "Reviewer Name" \
  --reviewer-role "External Counsel" \
  --approval-note "Usable generic baseline; keep as acceptable." \
  --review-note "Reviewed against recent mutual NDA matters; still too generic for preferred."
```

Example: promote to `preferred`

```bash
python3 scripts/update_seed_calibration.py \
  --package-dir contract-review/library/approved/templates/privacy_policy/0-privacy-policy-general-seed \
  --external-status completed \
  --recommendation promote_to_preferred \
  --reviewer-name "Reviewer Name" \
  --reviewer-role "Privacy Specialist Counsel" \
  --approval-note "Calibrated for preferred use." \
  --review-note "Consumer disclosure baseline now aligns with current practice." \
  --promote-manifest
```

The update script will reject promotion flows that do not satisfy the policy requirements.

### Step 7. Validate The Result

After any meaningful calibration update, run:

```bash
python3 .claude/skills/metadata-validator/scripts/validate-package.py contract-review/library/approved/templates/nda/0-nda-mutual-seed
python3 scripts/report_seed_calibration.py
```

If wording changed materially, also rerun:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

### Step 8. Sync Supporting Guidance When Needed

If calibration changed the real house view, update the surrounding knowledge base too:

- drafting guide
- review guide
- family-specific notes
- retrieval assumptions if family split or priority implications changed

Do not leave the seed upgraded while the human guidance still says something different.

## Decision Matrix

| Situation | Recommendation | Manifest authority |
|----------|----------------|-------------------|
| Usable baseline, still broad or generic | `keep_acceptable` | keep `acceptable` |
| Structurally sound, externally reviewed, safe as reusable starting point | `promote_to_preferred` | may promote to `preferred` |
| Family is right, wording is not ready | `needs_revision` | keep `acceptable` |
| One family label is hiding multiple real form types | `needs_family_split` | keep `acceptable` until split |

## Evidence Checklist For Promotion

Before promoting a seed to `preferred`, confirm all of the following:

- external review is truly complete
- reviewer identity and role are recorded
- the baseline is not just a synthetic placeholder anymore
- the core clause stack is internally coherent
- the wording does not depend on one specific client or one emergency compromise
- the baseline is broad enough for reuse within the family as currently defined
- no unresolved blocker remains in calibration metadata

If any of those are missing, do not promote.

## Anti-Patterns

Avoid these common mistakes.

### Promoting Because The Draft "Looks Good"

A clean-looking draft is not enough. Promotion is about reuse confidence, not drafting aesthetics.

### Treating One Negotiation Win As House Baseline

One favorable outcome does not necessarily represent your standard fallback or opening position.

### Hiding Deal-Specific Assumptions Inside A Family Seed

If a clause only makes sense for one client type, one regulated workflow, or one transaction structure, it probably does not belong in the general family baseline.

### Using `preferred` As A Reward Label

`Preferred` is not a compliment. It is an operational trust level.

### Updating Metadata Without Updating Wording

If the reviewer says a baseline needs real drafting changes, do not just change metadata and move on.

## Suggested First Families To Calibrate

If you are starting from scratch, use the current queue in this order:

1. `privacy_policy`
2. `dpa`
3. `employment`
4. `lease`
5. `nda`

Why these first:

- high practical usage
- clearer recurring clause patterns
- stronger compliance or market-standard sensitivity
- lower ambiguity than some broader transactional families

## Example: How A Real Matter Should Feed Calibration

Suppose you review three real NDAs over two months and repeatedly make the same changes:

- narrow the definition of confidential information
- tighten compelled-disclosure mechanics
- strengthen return-or-destroy language
- refine injunctive relief wording

That does not mean every reviewed NDA becomes the new seed.

It does mean you now have enough evidence to ask:

- are these recurring changes really our generic baseline?
- are they stable across matters?
- would future reviews be better if the seed reflected them?

If yes:

1. generate the family packet
2. review the seed with a qualified human
3. revise the seed if needed
4. record the recommendation
5. promote only if the reviewer is actually comfortable doing so

## Minimum Recordkeeping Standard

Every meaningful calibration action should leave a trace showing:

- who reviewed it
- when it was reviewed
- what decision was made
- whether blockers remain
- whether the seed stayed `acceptable` or was promoted

The system already stores that trace in `quality/calibration-review.json`.

## Bottom Line

Use live matters to generate evidence.

Use seed calibration to improve reusable baselines.

Use `preferred` sparingly.

When in doubt, keep the seed at `acceptable`, record the uncertainty honestly, and wait for stronger evidence.
