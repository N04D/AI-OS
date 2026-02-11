# Context — Workflow and Memory

## Purpose of this File
This document serves as the **collective memory and operating manual** of this project.  
Any AI operating within this project directory must **always read this file first** and act accordingly.

The contents of this file take precedence over assumptions, default behavior, or prior interactions.

---

## General Principles

- This project is **local**. All context lives in files.
- Browser-based chats are not authoritative and not binding.
- AI operates as an **executing assistant**, not as the owner of the project.
- The user determines direction, goals, and boundaries.

---

## Way of Working

### Sessions
- Work is done in **clearly bounded sessions**.
- Each session has:
  - a clear goal
  - a defined start
  - an explicit end
- The active session is described in `session.md`.

### Closing a Session
- Every session is closed with:
  - a summary of what was done
  - any decisions made
  - a short look ahead
- Closed sessions are stored in `sessions/YYYY-MM-DD.md HH:MM`.

**Start**: 2026-01-14 14:17  
**End**: 2026-01-14 18:42  
**Duration**: 4h 25m  

## Summary (EN)
...

## Summary (NL)  *(optional)*
...

## Work Completed
1. ...

## Decisions
- ...

## Repo Status
- ...

## Next Steps
- ...


---

## Language policy (hard rule)

System language is **English**.

Scope:
- All filenames, folder names, patterns, headers, rules, decisions, task instructions, scripts, commit messages, and logs are **English**.
- Conversations and operational instructions default to **English**.

Dutch is allowed only for:
- Explicitly requested end-user summaries, marked as **Summary (NL)**.
- Explicit translation outputs (source → Dutch), when requested.

Rules:
- Do not mix English and Dutch within the same section.
- If a Dutch summary is needed, place it under a dedicated heading: **Summary (NL)**.
- If unsure, default to English.

---

## Canonical Filenames (Hard Rule)

The following files have fixed, canonical names and must never be:
- renamed
- replaced
- split
- merged

Canonical:
- README.md
- context.md
- session.md
- decisions.md
- sessions/YYYY-MM-DD.md

AI may:
- modify content within these files **only with explicit instruction**

AI may not:
- create new variants
- use descriptive filenames as replacements

### Canonical Names (Exact)

The following filenames and patterns are binding:

- README.md  
- context.md  
- session.md  
- decisions.md  
- backlog.md  
- sessions/YYYY-MM-DD.md  

Rules:
- Filenames are **case-sensitive**
- Descriptive alternatives (such as “my conclusion.md”) are forbidden
- New variants of the above files are not allowed
- Deviations are considered errors and must be corrected immediately

---

## Rules for AI Behavior

AI must adhere to the following rules:

1. **Read First**
   - Always read `README.md` and this file before taking any action.

2. **Work with Files**
   - Write context, progress, and summaries to markdown files.
   - Avoid long conversations without persistent documentation.

3. **No Assumptions**
   - Do not rely on implicit knowledge.
   - What is not written in files must be asked or documented.

4. **Be Explicit**
   - State uncertainties.
   - State choices and alternatives.
   - Record final decisions in `decisions.md`.

5. **Structure Over Speed**
   - Working fast is subordinate to working clearly.
   - Slow and correct is preferred over fast and messy.

6. **No Autonomy Without Instruction**
   - Do not perform actions without explicit instruction.
   - Do not perform destructive actions without confirmation.

---

## Use of Tools

AI may:
- read and write files within this project directory
- execute scripts that are explicitly permitted
- propose automation ideas

AI may not:
- operate outside this directory
- perform network actions without explicit instruction
- modify systems that are outside the defined scope

---

## Decisions and Changes

- Final decisions are recorded in `decisions.md`.
- Temporary thoughts belong in `session.md`.
- After each session, it must be evaluated whether `context.md` requires updates.

This file may evolve, but only **deliberately**.

---

## Purpose of This System

This system is designed to:
- reduce cognitive load
- prevent context loss
- maintain focus and continuity
- enforce structure where humans cannot always do so

AI supports this process.  
The user remains responsible.

---

## Git & Remotes (Hard Rule)

This project uses **local git only**.

- There is **no remote**
- No pushes are performed
- Adding a remote is **not a default step**
- Adding a remote requires an explicit, deliberate decision by the user
- Decisions are recorded exclusively in `decisions.md`
- Filenames are canonical and must not vary

AI may not:
- propose remotes
- execute push commands
- suggest publication or hosting steps
