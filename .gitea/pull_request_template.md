
### Subsystem
<!-- Example: openclaw/cli, supervisor, executor, governance -->

### Risk Level
<!-- low | medium | high -->

### Determinism Impact
<!-- Describe whether this can change outputs, ordering, timing, or state evolution. -->

### Lock Required?
<!-- If touching high-risk paths, include exactly one: LOCK:supervisor/ | LOCK:governance/ | LOCK:executor/ | LOCK:orchestrator/ | LOCK:environment/ -->
<!-- If not required, write: none -->

### Tests Executed
<!-- CI checks must pass. If you run locally, include exact commands. -->
- lint:
- unit-tests:
- smoke-test:
- determinism-check (if SYSTEM_EVOLUTION):

### Rollback Plan
<!-- How to revert safely. Provide specific steps/commands. -->

### Issue
<!-- Must include an issue reference like #42 -->
#<id>
