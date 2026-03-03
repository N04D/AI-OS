# Secrets Policy Context v1

Policy model is default-deny by context.

Rules:
- All retrievals should provide an explicit context.
- Unknown context must be denied.
- Context-to-key allowlists live in `aios/secrets/policy.py`.

Current known contexts include:
- `interactive_cli`
- `ui.test_connection`
- `supervisor.autonomy_promotion_gate`
- `supervisor.autonomy_review_intake_gate`
- `supervisor.autonomy_task_materializer`
- `supervisor.agent_workspace.push_pr`
- `supervisor.cli.night_run`
- `supervisor.supervisor.auth_headers`

Contract notes:
- Context identifiers are API contract strings and should be treated as stable.
- New contexts must be added with tests.
