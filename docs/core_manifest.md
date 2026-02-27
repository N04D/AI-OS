# Core Documentation Manifest

Manifest Version: v1.0
Status: LOCKED
Last Reviewed: static

## Purpose
This manifest defines the canonical documentation set for governance and operational control.
Only listed artifacts are treated as canonical core. This manifest is LOCKED and must be updated explicitly.

## Canonical Core Set

| Domain | Canonical Artifact | Version | Lock |
|---|---|---|---|
| Agent Git Governance | `docs/Specifications AI-OS/Agent Git Governance Spec v0.2.md` | v0.2 | LOCKED |
| PR Governance Policy | `governance/policy/pr-governance.v0.2.yaml` | v0.2 | LOCKED |
| Self-Improvement Risk Tiers | `docs/specs/self_improvement_risk_tiers.v0.1.md` | v0.1 | LOCKED |
| Determinism Evidence Schema | `docs/specs/determinism_evidence.schema.v0.1.json` | v0.1 | LOCKED |
| Scheduler Job Schema | `governance/schema/scheduler/job.v0.1.json` | v0.1 | LOCKED |
| Plugin Manifest Schema | `governance/schema/plugins/plugin-manifest.v0.1.yaml` | v0.1 | LOCKED |
| Capability Mapping Contract | `docs/specs/policy-to-capability-deterministic-mapping-contract-v0.1.md` | v0.1 | LOCKED |

## Archived/Obsolete Governance Versions

- `docs/archive/governance_versions/Agent Git Governance Spec v0.1.md` (superseded by v0.2)
- `docs/archive/governance_versions/governance-invariants.v0.1.md` (superseded by v0.2)

## Canonical Core Integrity Rule

Canonical core documents must have zero missing file references in `docs/index/spec_inventory.json`.
