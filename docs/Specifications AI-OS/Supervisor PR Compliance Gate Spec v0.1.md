# Supervisor PR Compliance Gate Spec v0.1

**Automatic blocking of non-compliant PRs (Gitea-focused)**

**Status:** Draft
**Goal:** The Supervisor acts as a deterministic governance gate that **prevents merges** unless PRs satisfy Agent Git Governance v0.2 rules.
**Mechanism:** Supervisor produces a required **status check** (or required **approval gate**) on every PR. If non-compliant → status = **failure** → merge blocked by branch protection.

---

## 1. Scope

### In-scope

* Enforce governance rules on PRs targeting `develop` or `main`
* Produce machine-verifiable pass/fail signal
* Provide an auditable “why” report (comment + artifact log)

### Out-of-scope

* Writing code directly into your repo here
* Human policy decisions beyond the rule set (those live in config)

---

## 2. Assumptions

* Git server: **Gitea**
* Protected branches: `main`, `develop`
* Branch protection requires **status checks** to pass (recommended), optionally also **minimum approvals**
* Supervisor has:

  * read access to PR metadata
  * read access to commits/diffs
  * write access to

    * PR status/check-run (preferred)
    * PR comments (optional but recommended)
    * labels (optional)

---

## 3. High-Level Architecture

### 3.1 Components

1. **Supervisor Gatekeeper Service**
   Deterministic loop; evaluates PR compliance; outputs PASS/FAIL.
2. **Gitea Integration Layer**
   Fetch PR data; set status; optionally comment/label.
3. **Policy Pack**
   Versioned ruleset (YAML/JSON) aligned with Governance v0.2.
4. **Evidence Store**
   Local logs + serialized “compliance report” artifacts for audit.

### 3.2 Trigger Modes (choose 1 or run both)

* **Webhook-driven** (recommended): reacts to PR events (opened, synchronize, edited, labeled, review submitted).
* **Polling** (fallback): checks open PRs every N minutes.

Determinism rule: each evaluation must be reproducible from:

* PR number
* commit SHA
* policy version hash

---

## 4. Enforcement Strategy

### 4.1 Hard Block (preferred)

Use a **required status check** on protected branches:

* Check name: `supervisor/governance`
* States:

  * `success` → merge allowed (subject to other checks)
  * `failure` → merge blocked
  * `pending` → merge blocked (if branch protection requires it)

### 4.2 Soft Block (optional layer)

If status checks are not available/usable:

* Supervisor posts a “DO NOT MERGE” label and requires a human rule to respect it
  (This is weaker; avoid if possible.)

---

## 5. Policy Model

Policy file lives in repo, versioned:

`governance/policy/pr-governance.v0.2.yaml`

Key idea: Supervisor reads the policy from the PR head SHA (not from `main`) so the policy itself can be updated via governed PRs, but:

* Policy changes are **SYSTEM_EVOLUTION**
* Require stricter approvals (see §9)

---

## 6. Compliance Rules (Minimum Set)

Supervisor must evaluate the following gates. Any failure ⇒ status = `failure`.

### Gate A — Target Branch Rules

* PR target must be `develop` or `main`
* Feature work must target `develop`
* Only `hotfix/*` may target `main` (unless release PR type)

**Fail examples**

* `agent/*` PR targeting `main`
* random branch targeting `main`

---

### Gate B — Branch Naming (Strict)

Branch must match one of:

1. Feature branches
   `^agent\/[a-z0-9_-]+\/(feat|fix|chore|docs|test)\/[0-9]+-[a-z0-9-]+$`

2. Hotfix branches
   `^hotfix\/[0-9]+-[a-z0-9-]+$`

---

### Gate C — Issue Link Presence

PR title or body must include an issue reference: `#<id>` (configurable patterns)

Examples:

* `[#42]` or `#42`

---

### Gate D — Required PR Template Fields (Hard)

PR body must include (case-insensitive headings acceptable):

* `Subsystem`
* `Risk Level`
* `Determinism Impact`
* `Lock Required?`
* `Tests Executed`
* `Rollback Plan`

Supervisor parses and validates non-empty content. Empty “TBD” can be treated as failure by policy.

---

### Gate E — Commit Signing (Agents)

All commits in PR must be signed **OR** the merge commit must be signed (policy decision).

Strict mode (recommended): **all commits signed**.

Supervisor checks:

* `git log --show-signature <base>..<head>`
* or via Gitea API commit signature metadata if available

---

### Gate F — Review Separation

* PR author (agent) cannot approve own PR
* Minimum approvals:

  * `develop`: ≥1 approval by *different principal* (agent or human)
  * `main`: human approval required
* Optional: require Supervisor “governed” approval as a formal review

---

### Gate G — High-Risk Path Locking

If diff touches any high-risk path:

* `supervisor/`
* `governance/`
* `executor/`
* `orchestrator/`
* `environment/`

then:

1. PR must include lock declaration: `LOCK:<path>` in body or issue label
2. No competing open PR may hold the same lock
3. Human approval required
4. Risk level cannot be `low`

---

### Gate H — Determinism Checks (Evidence)

PR must contain evidence of:

* unit tests
* smoke test

Supervisor validates evidence by either:

* CI status checks present and successful, **or**
* PR body contains a “Tests Executed” block with command lines + exit code markers

Strict mode: require CI checks, and reject “manual only”.

---

## 7. Data Flow

### 7.1 Input

From Gitea per PR:

* PR metadata: title, body, author, base branch, head branch
* Commit list + SHAs
* Changed files list (diff)
* Reviews: approvals, rejections, reviewers
* Status checks / CI results (if any)
* Labels (optional)

### 7.2 Output

Supervisor sets:

* Status: `supervisor/governance` = success/failure/pending
* Description: short reason
* Details URL: points to an internal audit log page or artifact location (optional)
* Optional: comment with full compliance report
* Optional: labels (`governed`, `risk:*`, `LOCK:*`)

---

## 8. Deterministic Evaluation Contract

Each run emits a JSON report:

`artifacts/governance/pr-<num>-<headsha>.json`

Minimum schema:

```json
{
  "policy_version": "v0.2",
  "policy_hash": "sha256:...",
  "repo": "owner/name",
  "pr_number": 42,
  "base_branch": "develop",
  "head_sha": "abcd...",
  "result": "PASS|FAIL",
  "failed_gates": [
    {"gate":"Gate D", "reason":"Missing 'Rollback Plan' section"}
  ],
  "signals": {
    "approvals": 1,
    "human_approval": false,
    "signed_commits_ratio": 1.0,
    "high_risk_paths_touched": ["supervisor/"]
  },
  "timestamp_utc": "2026-02-15T..."
}
```

Determinism requirement: same inputs + same policy => identical gate decisions.

---

## 9. SYSTEM_EVOLUTION Handling (Meta-governance)

If PR modifies:

* `governance/policy/*`
* Supervisor gate code/config
* branch protection configuration docs (optional)

Then classify as `SYSTEM_EVOLUTION` and require:

* 2 approvals (1 other agent + 1 human)
* mandatory “Determinism Impact” = explicit
* extended test suite evidence

Supervisor enforces this classification automatically based on changed paths.

---

## 10. Failure Modes and Safe Defaults

* If Gitea API unreachable → set status `pending` (or `failure`) so merge is blocked
* If diff retrieval fails → `failure`
* If policy file missing → `failure`
* If signature verification cannot run → `failure` (strict) or `pending` (lenient)

Safety posture: **fail closed**.

---

## 11. Gitea Configuration Requirements (to make blocking real)

On `main` and `develop`:

* Require status check: `supervisor/governance`
* Require at least 1 approval (optional; Supervisor already checks this)
* Disallow force-push
* Disallow direct push

This turns Supervisor output into an actual merge barrier.

---

## 12. Operational Notes (Your ecosystem)

* The Supervisor should derive `owner/repo` dynamically from `environment.json` or git remote (aligns with your backlog item: remove hard-coded owner/repo).
* Run Supervisor on a stable node (e.g., sentinel) with:

  * read-only deploy key to clone repo
  * token to read PR metadata + set statuses
* Rate-limits: batch PR evaluations per cycle; cache PR head SHAs to avoid re-evaluating unchanged PRs.

---

## 13. Minimal API Surface (abstract)

Supervisor needs functions:

* `list_open_prs(base_branch in {develop, main})`
* `get_pr(pr_number)`
* `get_pr_commits(pr_number)`
* `get_pr_files(pr_number)`
* `get_pr_reviews(pr_number)`
* `set_commit_status(sha, context, state, description, target_url)`
* `(optional) comment_on_pr(pr_number, body)`
* `(optional) set_labels(pr_number, labels)`

---

## 14. Example Status Messages

* **FAIL:** `Missing required PR template fields: Rollback Plan, Determinism Impact`
* **FAIL:** `High-risk path touched (supervisor/). LOCK:supervisor/ missing.`
* **FAIL:** `Unsigned commit detected: <sha>`
* **PASS:** `All governance gates satisfied (policy v0.2, hash …)`

---

## 15. Implementation Checklist

1. Enable branch protections (`main`, `develop`) with required check `supervisor/governance`
2. Create policy file `governance/policy/pr-governance.v0.2.yaml`
3. Add PR template in `.gitea/pull_request_template.md` (or repo equivalent)
4. Deploy Supervisor gatekeeper service + credentials
5. Validate end-to-end with a deliberately non-compliant PR (expect merge blocked)
6. Validate compliant PR (expect merge allowed)

---

If you want the next step to be concrete: I can produce the **policy YAML**, a **PR template**, and a **reference implementation outline** (module layout + deterministic evaluation pseudocode) that matches your existing Supervisor loop structure and your “no hard-coded owner/repo” constraint.
