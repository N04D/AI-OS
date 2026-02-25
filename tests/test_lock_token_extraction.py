from supervisor.pr_gate.evaluator import _extract_lock_tokens


def test_extract_lock_token_preserves_trailing_slash():
    assert _extract_lock_tokens("LOCK:supervisor/") == ["LOCK:supervisor/"]


def test_extract_lock_token_without_trailing_slash():
    assert _extract_lock_tokens("LOCK:supervisor") == ["LOCK:supervisor"]


def test_extract_multiple_tokens():
    text = "LOCK:supervisor/ LOCK:governance"
    assert _extract_lock_tokens(text) == ["LOCK:supervisor/", "LOCK:governance"]


def test_extract_tokens_with_adversarial_punctuation():
    text = "(LOCK:supervisor/) > LOCK:governance\n`LOCK:executor/`"
    assert _extract_lock_tokens(text) == ["LOCK:supervisor/", "LOCK:governance", "LOCK:executor/"]


def test_embedded_token_without_boundary_is_rejected():
    assert _extract_lock_tokens("prefixXLOCK:supervisor/") == []
