# Environment World Model

This document defines the canonical world model for the autonomous AI engineering system. All agents must reference this document as the single source of truth for environment-specific knowledge.

## Infrastructure Overview

The system operates within a local, self-hosted infrastructure. It does not rely on public cloud services unless explicitly configured to do so.

## Git Hosting

- **Provider:** Local Gitea Instance
- **Access Protocol:** SSH
- **Example Remote URL:** `ssh://git@localhost:2222/Don/dev.git`

## API Endpoints

- **Gitea API Base:** `/api/v1`
- **Issues Endpoint:** `/repos/{owner}/{repo}/issues`

The full API URL for a repository is constructed dynamically based on the Git remote URL. For example, for the remote `ssh://git@localhost:2222/Don/dev.git`, the API would be accessed at `http://localhost:3000/api/v1/repos/Don/dev/issues`. Note the assumed standard Gitea HTTP port of `3000`.

## Execution Constraints

- **Execution Model:** Local, autonomous Python processes.
- **User Interaction:** No UI-based approval loops are required for execution. Agents operate with a high degree of autonomy.
- **Network Scope:** Agents operate within a local network and should not assume access to the public internet.

## Agent Roles

- **Gemini (Planner):** The planning and supervision agent, responsible for analyzing the repository, selecting tasks, and providing high-level guidance.
- **Codex (Builder):** The implementation agent, responsible for writing, testing, and committing code based on the planner's instructions.
