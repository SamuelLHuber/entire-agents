---
name: agent-session-provenance
description: Use before creating commits or rewriting history in Prime Agent sessions. Verifies patched Git/Jujutsu and explains the native-hook requirement for automatic Agent-Session attribution.
---

# Agent Session Provenance

Use before any Prime Agent task that creates or rewrites commits.

## Contract

Patched Git/Jujutsu append exactly one trailer when `AGENT_SESSION_ID` is present:

```text
Agent-Session: <session-id>
```

Do not put model, provider, harness, endpoint, token, or user metadata in commit
messages.

## Prime-specific status

Prime Agent's documented package surface provides skills/prompts/themes. That is
a native Prime package, but it is not a lifecycle extension and cannot by itself
prove mutation of the environment for every future shell command.

Prime stores active session lease metadata under `~/.prime/agent/session-leases`;
a Prime-native lifecycle hook or source patch should set `AGENT_SESSION_ID` from
the active session before shell tools run. Do not use a `prime-agent` command
launch wrapper as the durable solution.

## Checks

```sh
command -v jj
jj --version
command -v git
git --version
test -n "${AGENT_SESSION_ID:-}" && printf 'AGENT_SESSION_ID=%s\n' "$AGENT_SESSION_ID"
```

If `AGENT_SESSION_ID` is missing, stop before committing and ask for the native
Prime hook/source patch to be enabled, or for the session to be restarted from an
environment that already contains the intended session ID.
