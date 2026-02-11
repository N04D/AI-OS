# Task {{TASK_ID}} — {{TITLE}}

## Context
Briefly describe the background or trigger for this task.
No assumptions. No implicit knowledge.

## Objective
What must be achieved?
Formulate this in a testable, verifiable way.

## Scope
What is explicitly **in scope**?
What is explicitly **out of scope**?

## Inputs
- Files / paths involved
- Relevant modules
- Existing code that may be modified

## Constraints
- Follow all system principles and decisions
- Do not modify anything outside the defined scope
- No refactoring unless explicitly requested
- All work must be local and reproducible

## Deliverables
- Files to be created or modified
- Tests to be added or updated

## Acceptance Criteria (Eval Gate)
- All relevant tests pass
- No regressions introduced
- Output matches the stated objective and constraints

## Failure Handling
On FAIL:
- Analyze the eval log
- Fix only what caused the failure
- Record the root cause briefly in agent memory

## Notes
Optional. Factual only. No interpretation.