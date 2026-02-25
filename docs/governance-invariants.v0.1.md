# Governance Invariants v0.1

Test Suite
- 316 passed / 0 failed / 0 errors (`/tmp/aios-m4-venv/bin/python -m pytest -q`)

PR Gate Guarantees
- Fail-closed behavior is enforced for required gate conditions.
- Evaluation order is deterministic.
- Failures are accumulated (`failed_gates` contains all failing gates).
- `primary_failed_gate` is selected by MAX-severity contract.
- `gate-verdict.json` is machine-readable.
- Workflow deny verdict literal includes `"allow": false`.

Commit Signing
- `commit_signing.mode` is enforced.
- `commit_signing.accepted_types` is enforced.
- Verified signing state is enforced.

Branch and Risk Controls
- Base branch allowlist is enforced.
- Lock required and lock exclusive controls are enforced.
- System evolution escalation is enforced.

Secure Execution Layer
- `KillSwitchError.code` compatibility contract is restored and covered by tests.
- Replay/permit/audit invalid conditions are enforced.

Dependency Contract
- `requirements.txt` is pinned.
- `requirements-dev.txt` is pinned.
- `httpx` is present for Starlette `TestClient`.
- `pytest` is pinned.

Policy SHA Anchor
- Effective policy SHA anchor is recorded in [docs/governance-policy-sha.txt](./governance-policy-sha.txt).
