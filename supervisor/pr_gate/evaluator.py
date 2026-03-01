import re

ALLOWED_COMMIT_SIGNING_MODES = {"all_commits", "merge_commit_only"}
SUPERVISOR_STATUS_CONTEXT = "supervisor/status"
# Primary failure is selected by MAX severity value.
# `high_risk_path_detection` is non-failing today; keep explicit lowest fallback.
GATE_SEVERITY = {
    "high_risk_path_detection": 0,
    "self_improvement_label_required": 5,
    "self_improvement_proposal_template": 6,
    "self_improvement_risk_tier": 7,
    "self_improvement_test_plan": 8,
    "self_improvement_checklist": 9,
    "self_improvement_supervisor_approval": 9,
    "self_improvement_allowed_change_boundary": 9,
    "self_improvement_governance_core_restriction": 9,
    "self_improvement_runtime_test_update": 9,
    "self_improvement_high_risk_token_required": 9,
    "self_improvement_determinism_evidence_required": 9,
    "self_improvement_pr_only_mutation": 9,
    "self_improvement_phase_acceptance_required": 9,
    "self_improvement_halt_discipline": 9,
    "self_improvement_post_proposal_authorization": 9,
    "base_branch_allowed": 10,
    "branch_name_regex": 20,
    "feature_to_develop_only": 30,
    "issue_reference_required": 40,
    "pr_template_sections": 50,
    "pr_template_placeholders": 60,
    "lock_required": 70,
    "lock_exclusive": 80,
    "required_status_checks": 90,
    "self_approval_forbidden": 100,
    "min_approvals_met": 110,
    "distinct_reviewer_required": 120,
    "human_approval_required": 130,
    "supervisor_status_required": 140,
    "system_evolution_escalation": 150,
    "commit_signing_mode": 160,
    "commit_signing_accepted_types": 170,
    "commit_signing_required": 180,
}


def _primary_failed_gate(failed_gates):
    if not failed_gates:
        return None
    return max(failed_gates, key=lambda gate: (GATE_SEVERITY.get(gate, -1), gate))


def _latest_approved_reviews(reviews):
    latest = {}
    for review in reviews:
        user = (review.get("user") or {}).get("login") or ""
        if not user:
            continue
        submitted = review.get("submitted_at") or ""
        state = str(review.get("state", "")).upper()
        current = latest.get(user)
        if current is None or submitted >= current["submitted_at"]:
            latest[user] = {
                "submitted_at": submitted,
                "state": state,
                "type": str((review.get("user") or {}).get("type", "")).lower(),
            }
    approved = []
    for user, meta in latest.items():
        if meta["state"] == "APPROVED":
            approved.append({"login": user, "type": meta["type"]})
    return approved


def _required_status_checks(policy, files):
    required = list(policy.get("ci", {}).get("required_checks", []))
    sys_evo = policy.get("system_evolution", {})
    detect_paths = tuple(sys_evo.get("detect_paths", []))
    is_system_evolution = any(
        any(path.startswith(prefix) for prefix in detect_paths)
        for path in files
    )
    if is_system_evolution:
        required = list(sys_evo.get("ci", {}).get("required_checks", required))
    return required, is_system_evolution


def _status_by_context(statuses):
    by_context = {}
    for status in statuses:
        context = status.get("context")
        if not context or context in by_context:
            continue
        by_context[context] = str(status.get("state", "")).lower()
    return by_context


def _extract_lock_tokens(text):
    return re.findall(r"(?<![A-Za-z0-9_])LOCK:[A-Za-z0-9_./-]+", text or "")


def _section_map(markdown_text):
    sections = {}
    current = None
    lines = (markdown_text or "").splitlines()
    for line in lines:
        heading = re.match(r"^(?:##|###)\s+(.+?)\s*$", line)
        if heading:
            current = heading.group(1)
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {key: "\n".join(val).strip() for key, val in sections.items()}


def _issue_ref_present(policy, text):
    issue_cfg = policy.get("issue_link") or {}
    if not issue_cfg.get("required", False):
        return True
    patterns = issue_cfg.get("patterns", [])
    for pattern in patterns:
        if re.search(pattern, text or ""):
            return True
    return False


def _branch_patterns(policy):
    patterns = ((policy.get("branch_rules") or {}).get("patterns") or {})
    compiled = {}
    for name, spec in patterns.items():
        regex = (spec or {}).get("regex")
        if regex:
            compiled[name] = re.compile(regex)
    return compiled


def _commit_signature_type(commit):
    verification = commit.get("verification") or (commit.get("commit") or {}).get("verification") or {}
    sig_type = verification.get("signature_type")
    if sig_type is None:
        sig_type = commit.get("signature_type")
    if not isinstance(sig_type, str) or not sig_type.strip():
        return None
    return sig_type.strip().lower()


def _check_commit_signing(policy, commits):
    signing = policy.get("commit_signing") or {}
    required = bool(signing.get("required", False))
    if not required:
        return [], [], [], [], "all_commits"

    mode = str(signing.get("mode", "all_commits"))
    scoped_commits = list(commits)
    if mode == "merge_commit_only" and scoped_commits:
        scoped_commits = [scoped_commits[-1]]

    accepted_types = {str(item).lower() for item in signing.get("accepted_types", [])}

    unverifiable = []
    unsigned = []
    unknown_signature_type = []
    disallowed_signature_type = []
    for commit in scoped_commits:
        sha = commit.get("sha") or "unknown"

        verification = commit.get("verification") or (commit.get("commit") or {}).get("verification") or None
        is_signed = False
        if verification is not None:
            if verification.get("verified") is True:
                is_signed = True
            else:
                unsigned.append(sha)
                continue

        if not is_signed:
            verifiable = commit.get("signature_verifiable")
            verified = commit.get("signature_verified")
            if verifiable is None or verified is None:
                unverifiable.append(sha)
                continue
            if not verifiable:
                unverifiable.append(sha)
                continue
            if not verified:
                unsigned.append(sha)
                continue

        if accepted_types:
            signature_type = _commit_signature_type(commit)
            if signature_type is None:
                unknown_signature_type.append(sha)
            elif signature_type not in accepted_types:
                disallowed_signature_type.append(sha)

    return unverifiable, unsigned, unknown_signature_type, disallowed_signature_type, mode


def _scan_self_improvement_boundary(files, declared_scope_prefixes, risk_tier):
    normalized_files = sorted(str(path) for path in files)
    declared = sorted(set(str(prefix) for prefix in declared_scope_prefixes))
    default_allowed = ["docs/", "tests/"]
    allowed_prefixes = sorted(set(default_allowed + declared))

    disallowed_paths = []
    for path in normalized_files:
        if not any(path.startswith(prefix) for prefix in allowed_prefixes):
            disallowed_paths.append(path)

    governance_core_prefixes = (
        "governance/",
        "docs/governance",
        "supervisor/pr_gate/",
    )
    touched_governance_core = sorted(
        path for path in normalized_files if any(path.startswith(prefix) for prefix in governance_core_prefixes)
    )

    runtime_changed = [
        path for path in normalized_files if not (path.startswith("docs/") or path.startswith("tests/"))
    ]
    tests_changed = any(path.startswith("tests/") for path in normalized_files)

    return {
        "allowed_prefixes": allowed_prefixes,
        "disallowed_paths": disallowed_paths,
        "touched_governance_core": touched_governance_core,
        "runtime_changed": runtime_changed,
        "tests_changed": tests_changed,
        "risk_tier": risk_tier,
    }


def evaluate_pr(policy, pr_data, commits, files, reviews, statuses):
    gate_events = []
    failed_gates = []

    def record(gate, passed, reason):
        gate_events.append(
            {
                "gate": gate,
                "result": "PASS" if passed else "FAIL",
                "reason": str(reason),
            }
        )
        if not passed:
            failed_gates.append(gate)

    base_branch = ((pr_data.get("base") or {}).get("ref") or "").strip()
    head_branch = ((pr_data.get("head") or {}).get("ref") or "").strip()
    pr_title = pr_data.get("title") or ""
    pr_body = pr_data.get("body") or ""
    pr_text = f"{pr_title}\n\n{pr_body}"
    pr_number = pr_data.get("number")
    pr_author = ((pr_data.get("user") or {}).get("login") or "").strip()
    open_prs = pr_data.get("_open_prs") or []
    labels_raw = pr_data.get("labels") or []
    label_names = set()
    if isinstance(labels_raw, list):
        for item in labels_raw:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    label_names.add(name.strip())
            elif isinstance(item, str) and item.strip():
                label_names.add(item.strip())

    approvals_cfg = policy.get("approvals") or {}
    required_cfg = approvals_cfg.get(base_branch) if isinstance(approvals_cfg, dict) else None
    if not isinstance(required_cfg, dict):
        required_cfg = {}

    allowed_base_branches = tuple((policy.get("targets") or {}).get("allowed_base_branches") or ())
    base_branch_ok = (not allowed_base_branches) or (base_branch in allowed_base_branches)
    record(
        "base_branch_allowed",
        base_branch_ok,
        "ALLOW_BASE_BRANCH_ALLOWED" if base_branch_ok else "DENY_BASE_BRANCH_NOT_ALLOWED",
    )

    branch_patterns = _branch_patterns(policy)
    feature_match = False
    any_match = False
    for name, pattern in branch_patterns.items():
        if pattern.match(head_branch):
            any_match = True
            if name == "feature":
                feature_match = True
    record("branch_name_regex", any_match, f"head_branch={head_branch}")

    feature_to_develop = (policy.get("branch_rules") or {}).get("feature_to_develop_only", False)
    feature_to_develop_ok = (not feature_to_develop) or (not feature_match) or (base_branch == "develop")
    record("feature_to_develop_only", feature_to_develop_ok, f"base_branch={base_branch}")

    issue_ref_ok = _issue_ref_present(policy, pr_text)
    record(
        "issue_reference_required",
        issue_ref_ok,
        "issue_ref_present" if issue_ref_ok else "missing_issue_ref",
    )

    template_cfg = policy.get("pr_template") or {}
    required_sections = template_cfg.get("required_sections", [])
    placeholders = [str(x).lower() for x in template_cfg.get("reject_placeholders", [])]
    min_len = int(template_cfg.get("min_section_length", 0) or 0)
    section_content = _section_map(pr_body)
    missing_sections = []
    placeholder_sections = []
    short_sections = []
    for section in required_sections:
        content = section_content.get(section)
        if content is None:
            missing_sections.append(section)
            continue
        low = content.lower()
        if any(tok in low for tok in placeholders):
            placeholder_sections.append(section)
        if len(content.strip()) < min_len:
            short_sections.append(section)

    sections_ok = not missing_sections and not short_sections
    record(
        "pr_template_sections",
        sections_ok,
        (
            f"missing={','.join(missing_sections)} short={','.join(short_sections)}"
            if not sections_ok
            else "ok"
        ),
    )

    placeholders_ok = not placeholder_sections
    record(
        "pr_template_placeholders",
        placeholders_ok,
        (
            f"sections={','.join(placeholder_sections)}"
            if not placeholders_ok
            else "ok"
        ),
    )

    self_improvement_intent = (
        "self-improvement" in (pr_title or "").lower()
        or "self-improvement" in (pr_body or "").lower()
        or "self-improvement" in label_names
        or head_branch.startswith("self-improvement/")
    )
    self_improvement_context = (
        "self-improvement" in label_names
        or head_branch.startswith("self-improvement/")
    )
    has_self_improvement_label = "self-improvement" in label_names
    record(
        "self_improvement_label_required",
        (not self_improvement_context) or has_self_improvement_label,
        (
            "inactive"
            if not self_improvement_context
            else ("ok" if has_self_improvement_label else "missing_label:self-improvement")
        ),
    )

    proposal_sections = _section_map(pr_body)
    proposal_required = [
        "Problem Statement",
        "Risk Tier",
        "Affected Components",
        "Determinism Impact",
        "Test Plan (Mandatory)",
        "Rollback Strategy",
    ]
    missing_proposal_sections = [name for name in proposal_required if not proposal_sections.get(name, "").strip()]
    proposal_ok = (not self_improvement_context) or (not missing_proposal_sections)
    record(
        "self_improvement_proposal_template",
        proposal_ok,
        (
            "inactive"
            if not self_improvement_context
            else ("ok" if proposal_ok else f"missing_sections={','.join(missing_proposal_sections)}")
        ),
    )

    risk_text = proposal_sections.get("Risk Tier", "").upper()
    risk_ok = (not self_improvement_context) or bool(re.search(r"\b(LOW|MED|HIGH)\b", risk_text))
    record(
        "self_improvement_risk_tier",
        risk_ok,
        (
            "inactive"
            if not self_improvement_context
            else ("ok" if risk_ok else "risk_tier_missing")
        ),
    )
    risk_match = re.search(r"\b(LOW|MED|HIGH)\b", risk_text)
    risk_tier = risk_match.group(1) if risk_match else ""

    determinism_evidence = proposal_sections.get("Determinism Evidence", "").strip()
    needs_determinism_evidence = risk_tier in {"MED", "HIGH"}
    determinism_evidence_ok = (not self_improvement_context) or (not needs_determinism_evidence) or bool(determinism_evidence)
    record(
        "self_improvement_determinism_evidence_required",
        determinism_evidence_ok,
        (
            "inactive"
            if not self_improvement_context
            else (
                "ok"
                if determinism_evidence_ok
                else f"determinism_evidence_required_for_tier={risk_tier or 'UNKNOWN'}"
            )
        ),
    )

    approval_token = proposal_sections.get("Approval Token", "").strip()
    high_risk_token_ok = (not self_improvement_context) or (risk_tier != "HIGH") or bool(approval_token)
    record(
        "self_improvement_high_risk_token_required",
        high_risk_token_ok,
        (
            "inactive"
            if not self_improvement_context
            else (
                "ok"
                if high_risk_token_ok
                else "high_risk_requires_approval_token"
            )
        ),
    )

    test_plan_text = proposal_sections.get("Test Plan (Mandatory)", "")
    test_plan_ok = (not self_improvement_context) or bool(test_plan_text.strip())
    record(
        "self_improvement_test_plan",
        test_plan_ok,
        (
            "inactive"
            if not self_improvement_context
            else ("ok" if test_plan_ok else "test_plan_missing")
        ),
    )

    checklist_required_tokens = [
        "proposal template",
        "risk tier",
        "test plan",
    ]
    body_low = pr_body.lower()
    checklist_ok = (not self_improvement_context) or all(
        (f"- [x] {token}" in body_low) or (f"- [X] {token}" in pr_body)
        for token in checklist_required_tokens
    )
    record(
        "self_improvement_checklist",
        checklist_ok,
        (
            "inactive"
            if not self_improvement_context
            else ("ok" if checklist_ok else "required_checklist_items_missing")
        ),
    )

    status_state_by_context = _status_by_context(statuses)
    supervisor_si_ok = (not self_improvement_context) or (status_state_by_context.get(SUPERVISOR_STATUS_CONTEXT) == "success")
    record(
        "self_improvement_supervisor_approval",
        supervisor_si_ok,
        (
            "inactive"
            if not self_improvement_context
            else ("ok" if supervisor_si_ok else "supervisor_status_missing_or_non_success")
        ),
    )

    proposal_allow_scope = proposal_sections.get("Allowed Mutation Scope", "")
    declared_scope_prefixes = []
    for line in proposal_allow_scope.splitlines():
        raw = line.strip().lstrip("-* ").strip().strip("`")
        if not raw:
            continue
        if raw.endswith("/"):
            declared_scope_prefixes.append(raw)
        else:
            declared_scope_prefixes.append(raw + "/")
    declared_scope_prefixes = sorted(set(declared_scope_prefixes))
    boundary_scan = _scan_self_improvement_boundary(files, declared_scope_prefixes, risk_tier)
    disallowed_paths = boundary_scan["disallowed_paths"]
    boundary_ok = (not self_improvement_context) or (not disallowed_paths)
    record(
        "self_improvement_allowed_change_boundary",
        boundary_ok,
        (
            "inactive"
            if not self_improvement_context
            else ("ok" if boundary_ok else f"disallowed_paths={','.join(disallowed_paths)}")
        ),
    )

    touched_governance_core = boundary_scan["touched_governance_core"]
    governance_core_ok = (not self_improvement_context) or (not touched_governance_core) or (risk_tier == "HIGH")
    record(
        "self_improvement_governance_core_restriction",
        governance_core_ok,
        (
            "inactive"
            if not self_improvement_context
            else (
                "ok"
                if governance_core_ok
                else f"governance_core_requires_high_tier:{','.join(touched_governance_core)}"
            )
        ),
    )

    runtime_changed = boundary_scan["runtime_changed"]
    tests_changed = boundary_scan["tests_changed"]
    runtime_test_update_ok = (not self_improvement_context) or (not runtime_changed) or tests_changed
    record(
        "self_improvement_runtime_test_update",
        runtime_test_update_ok,
        (
            "inactive"
            if not self_improvement_context
            else (
                "ok"
                if runtime_test_update_ok
                else f"runtime_changes_require_tests:{','.join(runtime_changed)}"
            )
        ),
    )

    pr_only_mutation_ok = (not runtime_changed) or (not self_improvement_intent) or self_improvement_context
    record(
        "self_improvement_pr_only_mutation",
        pr_only_mutation_ok,
        (
            "inactive"
            if (not runtime_changed and not self_improvement_intent)
            else (
                "ok"
                if pr_only_mutation_ok
                else "runtime_mutation_requires_governed_self_improvement_pr"
            )
        ),
    )

    phase_acceptance_text = proposal_sections.get("Phase Acceptance Evidence", "").lower()
    phase_acceptance_required_tokens = [
        "0 failed",
        "skip justifications",
        "roadmap update",
        "progress update",
        "halt",
    ]
    phase_acceptance_ok = (not self_improvement_context) or all(
        token in phase_acceptance_text for token in phase_acceptance_required_tokens
    )
    record(
        "self_improvement_phase_acceptance_required",
        phase_acceptance_ok,
        (
            "inactive"
            if not self_improvement_context
            else ("ok" if phase_acceptance_ok else "phase_acceptance_evidence_incomplete")
        ),
    )

    halt_discipline_text = proposal_sections.get("HALT Discipline", "").lower()
    halt_discipline_ok = (not self_improvement_context) or (
        ("halt entered" in halt_discipline_text)
        and ("authorization required" in halt_discipline_text)
        and ("awaiting approval" in halt_discipline_text)
        and ("no commits beyond proposal" in halt_discipline_text)
    )
    record(
        "self_improvement_halt_discipline",
        halt_discipline_ok,
        (
            "inactive"
            if not self_improvement_context
            else ("ok" if halt_discipline_ok else "halt_discipline_evidence_missing")
        ),
    )

    commits_count = len(commits)
    post_proposal_authorization_ok = (not self_improvement_context) or (commits_count <= 1) or bool(approval_token)
    record(
        "self_improvement_post_proposal_authorization",
        post_proposal_authorization_ok,
        (
            "inactive"
            if not self_improvement_context
            else (
                "ok"
                if post_proposal_authorization_ok
                else "commits_beyond_proposal_require_authorization"
            )
        ),
    )

    high_risk_paths = tuple(policy.get("high_risk_paths", []))
    touched_high_risk = []
    for path in files:
        for prefix in high_risk_paths:
            if path.startswith(prefix):
                touched_high_risk.append(prefix)
                break
    touches_high_risk = bool(touched_high_risk)
    record(
        "high_risk_path_detection",
        True,
        (
            f"touched={','.join(sorted(set(touched_high_risk)))}"
            if touches_high_risk
            else "none"
        ),
    )

    lock_cfg = policy.get("locks") or {}
    lock_required = touches_high_risk and bool(lock_cfg.get("required_on_high_risk", False))
    allowed_locks = set(lock_cfg.get("allowed", []))
    lock_tokens = _extract_lock_tokens(pr_text)
    selected_locks = sorted([tok for tok in lock_tokens if tok in allowed_locks])
    lock_token = selected_locks[0] if selected_locks else None
    lock_required_ok = (not lock_required) or bool(lock_token)
    record(
        "lock_required",
        lock_required_ok,
        (
            f"missing {next(iter(sorted(allowed_locks)), 'LOCK:<required>')}"
            if not lock_required_ok
            else "ok"
        ),
    )

    lock_conflict_prs = []
    if lock_token and bool(lock_cfg.get("exclusive", False)):
        for other in open_prs:
            other_num = other.get("number")
            if other_num == pr_number:
                continue
            other_text = f"{other.get('title') or ''}\n\n{other.get('body') or ''}"
            if lock_token in _extract_lock_tokens(other_text):
                lock_conflict_prs.append(other_num)
    lock_exclusive_ok = len(selected_locks) <= 1 and not lock_conflict_prs
    lock_reason = "ok"
    if len(selected_locks) > 1:
        lock_reason = f"multiple_tokens={','.join(selected_locks)}"
    elif lock_conflict_prs:
        lock_reason = f"conflicts={','.join(str(x) for x in sorted(lock_conflict_prs))}"
    record("lock_exclusive", lock_exclusive_ok, lock_reason)

    required_checks, is_system_evolution = _required_status_checks(policy, files)
    ci_required = bool((policy.get("ci") or {}).get("required", True))
    checks = []
    if ci_required:
        for ctx in required_checks:
            state = status_state_by_context.get(ctx, "missing")
            checks.append({"context": ctx, "state": state, "ok": state == "success"})
        checks_ok = all(c["ok"] for c in checks)
        checks_reason = "ALLOW_REQUIRED_STATUS_CHECKS_SUCCESS" if checks_ok else "DENY_REQUIRED_STATUS_CHECKS"
    else:
        checks_ok = True
        checks_reason = "ALLOW_CI_NOT_REQUIRED"
    record(
        "required_status_checks",
        checks_ok,
        checks_reason,
    )

    approved = _latest_approved_reviews(reviews)
    approved_users = sorted({entry["login"] for entry in approved})
    author_approved = pr_author in approved_users if pr_author else False
    disallow_self = bool(approvals_cfg.get("disallow_self_approval", False))
    self_approval_ok = (not disallow_self) or (not author_approved)
    record(
        "self_approval_forbidden",
        self_approval_ok,
        f"author={pr_author} author_approved={author_approved}",
    )

    effective_approvers = sorted([u for u in approved_users if u != pr_author])
    min_approvals = int(required_cfg.get("min_approvals", 0) or 0)
    require_human = bool(required_cfg.get("require_human_approval", False))
    require_distinct = bool(required_cfg.get("require_distinct_reviewer", False))

    if is_system_evolution:
        sys_approvals = (policy.get("system_evolution") or {}).get("approvals", {})
        min_approvals = max(min_approvals, int(sys_approvals.get("min_approvals", 0) or 0))
        require_human = require_human or bool(sys_approvals.get("require_human_approval", False))

    min_approvals_met = len(effective_approvers) >= min_approvals
    record(
        "min_approvals_met",
        min_approvals_met,
        f"have={len(effective_approvers)} need={min_approvals}",
    )

    distinct_gate_ok = (not require_distinct) or bool(effective_approvers)
    record(
        "distinct_reviewer_required",
        distinct_gate_ok,
        (
            f"approvers={','.join(effective_approvers)}"
            if not distinct_gate_ok
            else "ok"
        ),
    )

    if require_human:
        human_found = False
        for review in approved:
            if review["login"] == pr_author:
                continue
            if review["type"] != "bot":
                human_found = True
                break
    else:
        human_found = True
    human_ok = human_found
    record("human_approval_required", human_ok, f"required={require_human}")

    require_supervisor_status = bool(required_cfg.get("require_supervisor_status", False))
    supervisor_status = status_state_by_context.get(SUPERVISOR_STATUS_CONTEXT, "missing")
    supervisor_status_ok = (not require_supervisor_status) or (supervisor_status == "success")
    if not require_supervisor_status:
        supervisor_reason = "ALLOW_SUPERVISOR_STATUS_NOT_REQUIRED"
    else:
        supervisor_reason = (
            "ALLOW_SUPERVISOR_STATUS_PRESENT"
            if supervisor_status_ok
            else "DENY_SUPERVISOR_STATUS_REQUIRED"
        )
    record("supervisor_status_required", supervisor_status_ok, supervisor_reason)

    if not is_system_evolution:
        record("system_evolution_escalation", True, "inactive")
    else:
        system_evolution_ok = min_approvals_met and human_ok and checks_ok
        record(
            "system_evolution_escalation",
            system_evolution_ok,
            (
                "requirements_met"
                if system_evolution_ok
                else (
                    f"min_approvals_met={min_approvals_met} "
                    f"human_approval_required={human_ok} "
                    f"required_status_checks={checks_ok}"
                )
            ),
        )

    (
        unverifiable_commits,
        unsigned_commits,
        unknown_signature_type_commits,
        disallowed_signature_type_commits,
        signing_mode,
    ) = _check_commit_signing(policy, commits)
    signing_required = bool((policy.get("commit_signing") or {}).get("required", False))
    signing_mode_valid = signing_mode in ALLOWED_COMMIT_SIGNING_MODES
    if not signing_required:
        signing_mode_ok = True
        signing_mode_reason = "ALLOW_COMMIT_SIGNING_NOT_REQUIRED"
    elif not signing_mode_valid:
        signing_mode_ok = False
        signing_mode_reason = "DENY_COMMIT_SIGNING_MODE_INVALID"
    else:
        signing_mode_ok = True
        signing_mode_reason = (
            "ALLOW_COMMIT_SIGNING_MODE_MERGE_COMMIT_ONLY"
            if signing_mode == "merge_commit_only"
            else "ALLOW_COMMIT_SIGNING_MODE_ALL_COMMITS"
        )
    record("commit_signing_mode", signing_mode_ok, signing_mode_reason)

    if not signing_required:
        signing_types_ok = True
        signing_types_reason = "ALLOW_COMMIT_SIGNING_NOT_REQUIRED"
    else:
        signing_types_ok = not unknown_signature_type_commits and not disallowed_signature_type_commits
        if signing_types_ok:
            signing_types_reason = "ALLOW_COMMIT_SIGNING_TYPE_ACCEPTED"
        elif disallowed_signature_type_commits:
            signing_types_reason = "DENY_COMMIT_SIGNING_TYPE_UNACCEPTED"
        else:
            signing_types_reason = "DENY_COMMIT_SIGNING_TYPE_UNKNOWN"
    record("commit_signing_accepted_types", signing_types_ok, signing_types_reason)

    signing_ok = (
        signing_mode_ok
        and signing_types_ok
        and not unverifiable_commits
        and not unsigned_commits
    )
    if not signing_required:
        signing_reason = "ALLOW_COMMIT_SIGNING_NOT_REQUIRED"
    elif not signing_mode_ok:
        signing_reason = "DENY_COMMIT_SIGNING_MODE_INVALID"
    elif unverifiable_commits:
        signing_reason = "DENY_COMMIT_UNVERIFIABLE"
    elif unsigned_commits:
        signing_reason = "DENY_COMMIT_UNSIGNED"
    elif not signing_types_ok:
        signing_reason = signing_types_reason
    else:
        signing_reason = "ALLOW_COMMIT_SIGNING_VERIFIED"
    record(
        "commit_signing_required",
        signing_ok,
        signing_reason,
    )

    failed_gates = sorted(set(failed_gates))
    passed = not failed_gates
    primary_failed_gate = _primary_failed_gate(failed_gates)

    self_improvement_failed = [
        gate
        for gate in failed_gates
        if gate.startswith("self_improvement_")
    ]
    self_improvement_audit = {
        "context_active": self_improvement_context,
        "risk_tier": risk_tier if self_improvement_context else "",
        "decision": (
            "allow"
            if (self_improvement_context and not self_improvement_failed)
            else ("deny" if self_improvement_context else "inactive")
        ),
        "halt_state": (
            "inactive"
            if not self_improvement_context
            else (
                "awaiting_approval"
                if commits_count <= 1
                else (
                    "authorized_execution"
                    if post_proposal_authorization_ok
                    else "unauthorized_post_proposal_commits"
                )
            )
        ),
        "awaiting_approval_logged": bool(self_improvement_context and commits_count <= 1),
        "failed_gates": self_improvement_failed,
    }

    return {
        "passed": passed,
        "base_branch": base_branch,
        "head_branch": head_branch,
        "system_evolution": is_system_evolution,
        "failed_gates": failed_gates,
        "primary_failed_gate": primary_failed_gate,
        "failed_reasons": [
            event["reason"] for event in gate_events if event["result"] == "FAIL"
        ],
        "gate_events": gate_events,
        "self_improvement_audit": self_improvement_audit,
        "policy_requirements": {
            "min_approvals": min_approvals,
            "require_human_approval": require_human,
            "require_distinct_reviewer": require_distinct,
            "require_supervisor_status": require_supervisor_status,
            "required_checks": required_checks,
            "ci_required": ci_required,
            "lock_required": lock_required,
            "disallow_self_approval": disallow_self,
            "allowed_base_branches": list(allowed_base_branches),
        },
        "observed": {
            "approvals": len(effective_approvers),
            "approvers": effective_approvers,
            "author": pr_author,
            "author_approved": author_approved,
            "checks": checks,
            "touches_high_risk": touches_high_risk,
            "lock_token": lock_token,
            "lock_conflict_prs": sorted(lock_conflict_prs),
            "missing_sections": missing_sections,
            "placeholder_sections": placeholder_sections,
            "short_sections": short_sections,
            "unverifiable_commits": unverifiable_commits,
            "unsigned_commits": unsigned_commits,
            "unknown_signature_type_commits": unknown_signature_type_commits,
            "disallowed_signature_type_commits": disallowed_signature_type_commits,
            "supervisor_status_context": SUPERVISOR_STATUS_CONTEXT,
            "supervisor_status_state": supervisor_status,
            "files_count": len(files),
        },
    }
