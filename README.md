# entire-agents (experimental)

Source-level Git and Jujutsu attribution for coding-agent sessions, with S3/HTTP
session ingest and DuckDB analytics. Pi and Oh My Pi use native session lifecycle
extensions; other agents need native plugin/hooks or source patches rather than
command launch wrappers.

Latest local proof run passed on this machine:

- proof state: `.state/proof-a89651cd-7122-4b34-a8a4-bff310cd63b4`
- Pi session: `01a1fe99-a80b-754b-8dcf-3f1b1954a437`
- transcript SHA-256: `2f9f8984b46f1feeabbe158d498e5da41e63ed2d689776363518238848bc444e`
- S3 key: `sessions/01a1fe99-a80b-754b-8dcf-3f1b1954a437/2f9f8984b46f1feeabbe158d498e5da41e63ed2d689776363518238848bc444e.jsonl`
- observed mapped commits: `96305d6f74645718ee2e8c28b01bb5ede2347dd6`, `7ef2f69bc398f62a24c9e43b321c959055afb53c`
- `live_observed: true` while Pi was still running

The raw proof artifacts are intentionally ignored because they contain session
transcripts. Re-run `devenv shell -- python prove.py` to regenerate them.

## Contract

When `AGENT_SESSION_ID` is present, the patched binaries replace any existing
`Agent-Session:` lines and append exactly one current session ID before signing.
No model, provider, or harness name is put in the commit message. Without that
environment variable, normal human operation is unchanged.

The Pi/OMP extension sets the variable in the agent process at native
`session_start` time so shell descendants inherit it. The Jujutsu patch acts at
`CommitBuilder`'s store-writing boundary: it covers new revisions, snapshots, and
rewrites, not just `jj describe`. A rewritten commit is attributed to the session
doing the rewrite. Git's patch acts in `commit_tree_extended`, covering ordinary
commits and commit-tree callers.

**Scope:** this is attribution, not adversarial enforcement. An unrestricted
shell can unset the variable, run an unpatched binary, or write objects directly.
Imported commits are not rewritten. Low-level Git object writes are not covered.
Jujutsu operations that synthesize commits directly through a backend rather than
CommitBuilder also require separate review. No stronger guarantee is claimed.

## Native agent integrations

See [`extensions.md`](./extensions.md) for agent-specific support.

Current status:

- **Pi:** native extension via `package.json` `pi.extensions`.
- **Oh My Pi / OMP:** native extension via `package.json` `omp.extensions` or
  `omp --extension ./extension/index.ts`.
- **Prime Agent:** native package/skill artifact under `prime-package/` for checks
  and guidance. No documented public lifecycle extension hook was observed in the
  installed release; automatic attribution still needs a Prime-native hook/source
  patch. A wrapper is intentionally not provided.
- **Codex:** plugin/skill artifact under `codex-plugin/` for checks and guidance;
  automatic attribution still needs a Codex-native session-start env hook/source
  patch.
- **Cursor:** VS Code/Cursor extension skeleton under `cursor-extension/` can seed
  integrated terminals; full Cursor Agent worker attribution requires a Cursor
  worker hook/source patch.

## Run

Requires Nix and [devenv](https://devenv.sh). `devenv.lock` pins the inputs.

```sh
devenv shell
# In one terminal, start a loopback-only development S3 server:
export MINIO_ROOT_USER=local-agent
export MINIO_ROOT_PASSWORD=local-development-only
minio server .state/minio --address 127.0.0.1:9000
```

In another devenv shell:

```sh
export AWS_ACCESS_KEY_ID=local-agent
export AWS_SECRET_ACCESS_KEY=local-development-only
export AWS_DEFAULT_REGION=us-east-1
export AGENT_S3_ENDPOINT=http://127.0.0.1:9000
export AGENT_S3_BUCKET=agent-sessions
mc alias set local "$AGENT_S3_ENDPOINT" "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY"
mc mb --ignore-existing local/agent-sessions
pi --extension ./extension/index.ts
```

Use only synthetic sessions until you've reviewed transcript privacy and your
bucket access policy. Session JSONL includes prompts, code, tool results, and
potentially secrets. This does not upload Pi's credential/config files, but it
does **not** redact secrets already present in transcripts.

## Reproduce the proof

```sh
devenv shell -- python prove.py
```

This builds the patched tools, starts isolated loopback MinIO, verifies native
Jujutsu replacement/idempotency, runs **your configured Pi model** with a synthetic
coding task, observes S3 and SQL while Pi is alive, compares downloaded transcript
bytes with the local session, and checks session-to-commit mappings. It uses your
existing Pi login and may incur provider charges. Raw proof artifacts stay ignored
under `.state/`. It does not test direct Git CLI operations while the agent's
no-Git policy is active.

## Query

```sh
duckdb .state/sessions.duckdb 'SELECT * FROM sessions'
duckdb .state/sessions.duckdb 'SELECT * FROM models ORDER BY session_id, ordinal'
duckdb .state/sessions.duckdb 'SELECT * FROM commits'
```

`entries` retains raw complete JSONL records, indexed by session ID and ordinal.
`models` contains the model-change timeline, not a misleading single-model label.
`commits` retains observed commit hashes even after revisions are rewritten.

The worker polls once per second, retries failed uploads, and publishes a latest
pointer only after its immutable SHA-256-keyed snapshot succeeds. Connections to
DuckDB close between polls so other processes can query it; transient lock
conflicts retry on the next poll. This is a small local analytical index, not a
multi-writer database server. S3 snapshots are durable history; local DuckDB is
not itself remotely backed up. Indexing currently requires a Jujutsu repository.

## Source pins

`packages.nix` overrides the Git 2.56.0 and Jujutsu 0.46.0 derivations in pinned
nixpkgs. Patches are tracked, and upstream sources remain Nix fixed-output inputs.
The patched Nix store outputs from the latest proof were:

- Git: `/nix/store/2f074mkbhc7qpmy858nv473wvz3xj255-git-2.56.0`
- Jujutsu: `/nix/store/07mfpqq5q6c74magfmbfxd563kx3l8rv-jujutsu-0.46.0`
Current nixpkgs removed MinIO; a separately locked older nixpkgs provides only the
local MinIO test tools. Do not expose that legacy test server to the internet.
