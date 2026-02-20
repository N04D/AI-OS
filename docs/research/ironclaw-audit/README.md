# IronClaw Audit for AI-OS

Status: Complete (research only)
Scope: External codebase audit (`/tmp/ironclaw`) mapped onto AI-OS governance/runtime
Date: 2026-02-20
Owner: Codex
Reviewer: Supervisor

## Confirmed Repo Paths
- IronClaw audited path: `/tmp/ironclaw`
- AI-OS target path: `/home/infra/AI-OS`

## Method
1. Indexed security-relevant modules in IronClaw (`wasm`, `sandbox`, `policy`, `secrets`, `registry`, `audit`).
2. Read source files with line numbers for evidence.
3. Extracted reusable security patterns.
4. Mapped patterns to AI-OS placement (Kernel / Supervisor / Executor / Userland).
5. Drafted AI-OS extension spec + roadmap + policy schemas.

## Deliverables
- `docs/research/ironclaw-audit/pattern-inventory.md`
- `docs/research/ironclaw-audit/trust-boundaries.md`
- `docs/research/ironclaw-audit/threat-model.md`
- `docs/specs/ai-os-security-extension-v0.1.md`
- `roadmap/ironclaw-extract-into-ai-os.md`
- `governance/policy/security/capabilities.schema.json`
- `governance/policy/security/network-egress.schema.json`
- `governance/policy/security/secrets-boundary.schema.json`

## AI-OS Alignment Baseline (evidence)
- AI-OS requires versioned, reconstructable state and no hidden runtime mutation (`docs/architecture/ARCHITECTURE_CHARTER_v1.0.md:56`, `docs/architecture/ARCHITECTURE_CHARTER_v1.0.md:58`).
- Governance is kernel-level and fail-closed (`docs/architecture/ARCHITECTURE_CHARTER_v1.0.md:65`, `docs/architecture/ARCHITECTURE_CHARTER_v1.0.md:72`).
- Policy hashing/immutability is already enforced in supervisor (`supervisor/pr_gate/policy_loader.py:46`, `supervisor/supervisor.py:135`).

Evidence quote 1:
> "If a system state cannot be reconstructed from Git history, it is invalid."
(`docs/architecture/ARCHITECTURE_CHARTER_v1.0.md:61`)

Evidence quote 2:
> "Fails closed on violations"
(`docs/architecture/ARCHITECTURE_CHARTER_v1.0.md:72`)

## Constraints Observed
- No runtime implementation imported from IronClaw.
- No AI-OS refactor performed.
- Output is docs/specs/schemas only.

## UNVERIFIED Items
- Exact production deployment topology and trust boundaries for your future AI-OS executor mesh are not yet defined in this repo.
- Existing AI-OS runtime event taxonomy for tool/network/secrets is not formalized as a schema today (proposed here as new spec artifacts).
