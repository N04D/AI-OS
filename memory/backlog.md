# Backlog - Cognitive Archive

## Current Issues:

### 1. openclaw agent command hangs (related to heartbeat change)
**Status:** Blocked (needs investigation by sub-agent)
**Description:** The `openclaw agent` command, when executed, consistently fails to return output to the `exec` tool, appearing to hang indefinitely. This prevents obtaining a token payload trace for optimization. This issue may be related to recent heartbeat changes or interactions with the Gateway, Gemini API key configuration, or the `google-gemini-cli` provider.
**Goal for Investigation:** Determine the root cause of the `openclaw agent` command's failure to return output and propose a solution to enable reliable execution and token payload tracing.
