---
name: agent-session-provenance
description: Use before creating commits or rewriting history in Codex workspaces. Verifies that patched Git/Jujutsu are available and that AGENT_SESSION_ID is present so commit messages receive exactly one Agent-Session trailer.
---

# Agent Session Provenance

Use this skill before any Codex task that will create or rewrite Git/Jujutsu
commits.

## Contract

Commit messages must contain exactly one trailer:

```text
Agent-Session: <session-id>
```

Do not add model, provider, harness, token, endpoint, or user metadata to commit
messages. Those belong in session analytics/ingest.

## Checks

1. Verify patched tools are on `PATH`:

   ```sh
   command -v jj
   jj --version
   command -v git
   git --version
   ```

2. Verify the session env is present before committing:

   ```sh
   test -n "${AGENT_SESSION_ID:-}" && printf 'AGENT_SESSION_ID=%s\n' "$AGENT_SESSION_ID"
   ```

3. If `AGENT_SESSION_ID` is missing, stop before committing. A Codex plugin/skill
   cannot prove it can mutate the already-running host process environment for
   all future shell commands. Use a Codex-native session-start env hook/source
   patch when available, or ask the user to start Codex from an environment that
   already exports the session ID.

4. If `AGENT_SESSION_INGEST_URL` or `AGENT_S3_BUCKET` is configured, verify the
   sync command is available:

   ```sh
   command -v agent-session-sync || test -n "${AGENT_SESSION_SYNC_COMMAND:-}"
   ```

## Do not

- Do not use `--no-verify` or bypass hooks.
- Do not rewrite commit messages by hand to include model/provider metadata.
- Do not install a launch wrapper as the durable Codex integration.
- Do not commit secrets such as bearer tokens or ingest URLs with credentials.
