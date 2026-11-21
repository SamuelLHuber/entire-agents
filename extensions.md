# Native agent integrations

This repository's hard attribution point is the patched Git/Jujutsu commit writer.
Agents only need to put the current agent session ID in `AGENT_SESSION_ID` before
they run shell commands. The trailer remains exactly:

```text
Agent-Session: <session-id>
```

No model, harness, or provider metadata belongs in commit messages; that data is
kept in the session JSONL/analytics ingest.

## Pi

Pi uses the package metadata in `package.json`:

```json
{
  "pi": { "extensions": ["./extension/index.ts"] }
}
```

Install by adding the package directory or `extension/index.ts` to Pi's native
extension/package configuration. The extension listens for `session_start`, reads
Pi's native session ID and session file from the session manager, sets
`AGENT_SESSION_ID`, and starts `agent-session-sync` only when an S3 bucket or HTTP
ingest endpoint is configured.

## Oh My Pi / OMP

OMP exposes the same session lifecycle hook and package-style extension discovery.
This package advertises the same extension through:

```json
{
  "omp": { "extensions": ["./extension/index.ts"] }
}
```

Install by adding the package directory to `~/.omp/agent/config.yml`:

```yaml
extensions:
  - /path/to/entire-agents
```

or by passing the native OMP flag for a one-off session:

```sh
omp --extension /path/to/entire-agents/extension/index.ts
```

The OMP integration is not a launcher wrapper. OMP itself loads the extension at
session start, so shell tools spawned by the session inherit `AGENT_SESSION_ID`.

## Prime Agent

Prime Agent has durable packages for skills/prompts/themes and stores session
leases with `activeSessionId` and `sessionPath`, but the observed public package
surface does not document a lifecycle extension hook equivalent to Pi/OMP's
`session_start`. A skill-only package can verify provenance and ingest session
files after the fact, but it cannot reliably mutate the environment of future
shell commands unless Prime exposes a native hook or environment API.

Therefore Prime commit attribution should be implemented by one of these native
paths, in order:

1. a Prime lifecycle extension if/when supported by the installed release,
2. a Prime source patch that sets `AGENT_SESSION_ID` from its active session ID
   before running shell tools,
3. an explicit upstream Prime feature request for a session environment hook.

Do not substitute a `prime-agent` launch wrapper as the durable implementation.

## Codex

Codex plugins and skills are useful for provenance checks and operator guidance,
but the observed plugin format is a capability/skill surface. It does not by
itself prove that every shell command in the host process inherits a mutable
`AGENT_SESSION_ID` from the active Codex session.

The safe native Codex integration is:

- configure patched Git/Jujutsu on `PATH`,
- use Codex `shell_environment_policy.set` for stable provenance-related env
  such as ingest URL/token-file names, and
- add a Codex plugin/skill that checks whether `AGENT_SESSION_ID` is present
  before committing and reports the active session file when available.

If Codex exposes a session-start hook in a future release, wire this repository's
session-start logic there. Until then, do not claim automatic commit attribution
for Codex without a Codex-native env hook or source patch.

## Cursor Agent

Cursor supports VS Code/Cursor extensions. A Cursor extension can set environment
variables for integrated terminals through VS Code's environment variable
collection and can expose provenance checks. Cursor Agent workers, however, may
be spawned by Cursor's own agent worker service rather than by an integrated
terminal. Unless Cursor documents that agent workers inherit extension-provided
environment variables, the extension can only make terminal-launched commits
attributable.

For full Cursor Agent attribution, use a Cursor-native agent-worker hook or patch
the Cursor Agent worker launcher to set `AGENT_SESSION_ID` from Cursor's native
run/session identity before it runs Git/Jujutsu.
