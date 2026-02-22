import re


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
    return re.findall(r"\bLOCK:[A-Za-z0-9_./-]+\b", text or "")


def _section_map(markdown_text):
    sections = {}
    current = None
    lines = (markdown_text or "").splitlines()
    for line in lines:
        heading = re.match(r"^###\s+(.+?)\s*$", line)
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


def _check_commit_signing(policy, commits):
    signing = policy.get("commit_signing") or {}
    required = bool(signing.get("required", False))
    if not required:
        return [], []

    unverifiable = []
    unsigned = []
    for commit in commits:
        sha = commit.get("sha") or "unknown"

        verification = commit.get("verification") or (commit.get("commit") or {}).get("verification") or None
        if verification is not None:
            if verification.get("verified") is True:
                continue
            unsigned.append(sha)
            continue

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

    return unverifiable, unsigned


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

    approvals_cfg = policy.get("approvals") or {}
    required_cfg = approvals_cfg.get(base_branch) if isinstance(approvals_cfg, dict) else None
    if not isinstance(required_cfg, dict):
        required_cfg = {}

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
    status_state_by_context = _status_by_context(statuses)
    checks = []
    for ctx in required_checks:
        state = status_state_by_context.get(ctx, "missing")
        checks.append({"context": ctx, "state": state, "ok": state == "success"})
    checks_ok = all(c["ok"] for c in checks)
    record(
        "required_status_checks",
        checks_ok,
        (
            "missing_or_failed_checks"
            if not checks_ok
            else "all_required_checks_success"
        ),
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

    unverifiable_commits, unsigned_commits = _check_commit_signing(policy, commits)
    signing_ok = not unverifiable_commits and not unsigned_commits
    record(
        "commit_signing_required",
        signing_ok,
        (
            f"unverifiable={len(unverifiable_commits)} unsigned={len(unsigned_commits)}"
            if not signing_ok
            else "all_commits_signed"
        ),
    )

    failed_gates = sorted(set(failed_gates))
    passed = not failed_gates

    return {
        "passed": passed,
        "base_branch": base_branch,
        "head_branch": head_branch,
        "system_evolution": is_system_evolution,
        "failed_gates": failed_gates,
        "failed_reasons": [
            event["reason"] for event in gate_events if event["result"] == "FAIL"
        ],
        "gate_events": gate_events,
        "policy_requirements": {
            "min_approvals": min_approvals,
            "require_human_approval": require_human,
            "require_distinct_reviewer": require_distinct,
            "required_checks": required_checks,
            "lock_required": lock_required,
            "disallow_self_approval": disallow_self,
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
            "files_count": len(files),
        },
    }
