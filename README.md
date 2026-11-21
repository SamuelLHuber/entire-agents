# entire-agents (experimental)

Source-level Git and Jujutsu attribution for Pi sessions, with S3 snapshots and
DuckDB analytics. **Not yet a verified release.** See `.state/proof-*/evidence.json`
for successful local proof runs; absence of that file means no passing proof.

## Contract

When `AGENT_SESSION_ID` is present, the patched binaries replace any existing
`Agent-Session:` lines and append exactly one current session ID before signing.
No model, provider, or harness name is put in the commit message. Without that
environment variable, normal human operation is unchanged.

The Pi extension sets the variable in the Pi process so shell descendants inherit
it. The Jujutsu patch acts at `CommitBuilder`'s store-writing boundary: it covers
new revisions, snapshots, and rewrites, not just `jj describe`. A rewritten commit
is attributed to the session doing the rewrite. Git's patch acts in
`commit_tree_extended`, covering ordinary commits and commit-tree callers.

**Scope:** this is attribution, not adversarial enforcement. An unrestricted
shell can unset the variable, run an unpatched binary, or write objects directly.
Imported commits are not rewritten. Low-level Git object writes are not covered.
Jujutsu operations that synthesize commits directly through a backend rather than
CommitBuilder also require separate review. No stronger guarantee is claimed.

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
Current nixpkgs removed MinIO; a separately locked older nixpkgs provides only the
local MinIO test tools. Do not expose that legacy test server to the internet.
