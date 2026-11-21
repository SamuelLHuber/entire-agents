"""Run inside `devenv shell -- python prove.py`. Uses configured Pi credentials.
Only synthetic test transcripts are published to the loopback MinIO server.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

import boto3
import duckdb

ROOT = Path(__file__).resolve().parent


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs)


def main():
    state = ROOT / ".state" / ("proof-" + str(uuid.uuid4()))
    state.mkdir(parents=True)
    env = dict(os.environ, MINIO_ROOT_USER="proof-user", MINIO_ROOT_PASSWORD="local-proof-only",
               AWS_ACCESS_KEY_ID="proof-user", AWS_SECRET_ACCESS_KEY="local-proof-only",
               AWS_DEFAULT_REGION="us-east-1", AGENT_S3_BUCKET="agent-proof",
               AGENT_S3_ENDPOINT="http://127.0.0.1:19000",
               AGENT_ANALYTICS_DB=str(state / "sessions.duckdb"))
    log = (state / "minio.log").open("w")
    server = subprocess.Popen(["minio", "server", str(state / "objects"), "--address", "127.0.0.1:19000",
                               "--console-address", "127.0.0.1:19001"], env=env, stdout=log, stderr=log)
    try:
        client = boto3.client("s3", endpoint_url=env["AGENT_S3_ENDPOINT"],
                              aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
                              aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"], region_name="us-east-1")
        for attempt in range(60):
            try:
                client.create_bucket(Bucket=env["AGENT_S3_BUCKET"])
                break
            except Exception:
                if server.poll() is not None or attempt == 59:
                    raise
                time.sleep(.5)
        repo = state / "repo"
        run("jj", "git", "init", str(repo), env=env)
        session_id = str(uuid.uuid4())
        test_env = dict(env, AGENT_SESSION_ID=session_id)
        run("jj", "describe", "-m", "First\n\nAgent-Session: forged", cwd=repo, env=test_env)
        first = run("jj", "log", "--no-graph", "-r", "@", "-T", "description", cwd=repo, env=test_env)
        assert first.count("Agent-Session:") == 1 and session_id in first and "forged" not in first, first
        run("jj", "describe", "-m", first, cwd=repo, env=test_env)
        assert run("jj", "log", "--no-graph", "-r", "@", "-T", "description", cwd=repo, env=test_env) == first
        # Real Pi must call the shell and create a revision; no attribution in prompt.
        transcript = (state / "pi-output.jsonl").open("w")
        agent = subprocess.Popen([
            "pi", "--no-extensions", "--no-skills", "--no-mcp", "--no-context-files",
            "--extension", str(ROOT / "extension/index.ts"), "--session-dir", str(state / "pi-sessions"),
            "--tools", "bash,write,read", "--mode", "json", "--print", "--thinking", "off",
            "Use bash to run: printf 'hello provenance\\n' > hello.txt; jj describe -m 'Agent proof'; "
            "jj new -m 'Next revision'; sleep 5. Then reply done. Use jj, never git.",
        ], cwd=repo, env=env, stdout=transcript, stderr=subprocess.STDOUT)
        # Observe remote objects AND a readable query store while Pi is still running.
        live = False
        for _ in range(240):
            if agent.poll() is not None:
                break
            try:
                objects = client.list_objects_v2(Bucket=env["AGENT_S3_BUCKET"]).get("Contents", [])
                with duckdb.connect(env["AGENT_ANALYTICS_DB"], read_only=True) as db:
                    count = db.execute("SELECT count(*) FROM entries").fetchone()[0]
                if objects and count:
                    live = True
            except Exception:
                pass
            time.sleep(1)
        if agent.poll() is None:
            agent.terminate()
        assert agent.wait(timeout=20) == 0, f"Pi failed: {state}"
        assert live, "no live observation"
        sessions = list((state / "pi-sessions").glob("*.jsonl"))
        assert len(sessions) == 1, sessions
        raw = sessions[0].read_bytes()
        sid = json.loads(raw.splitlines()[0])["id"]
        pointer = json.loads(client.get_object(Bucket=env["AGENT_S3_BUCKET"], Key=f"sessions/{sid}/latest.json")["Body"].read())
        remote = client.get_object(Bucket=env["AGENT_S3_BUCKET"], Key=pointer["key"])["Body"].read()
        assert remote == raw, "final S3 snapshot differs from Pi transcript"
        with duckdb.connect(env["AGENT_ANALYTICS_DB"], read_only=True) as db:
            mappings = db.execute("SELECT commit_id, session_id FROM commits WHERE session_id = ?", [sid]).fetchall()
            assert mappings, "no Pi session-to-commit mapping"
        evidence = {"live_observed": live, "session_id": sid, "sha256": hashlib.sha256(raw).hexdigest(),
                    "s3_key": pointer["key"], "commit_mappings": mappings,
                    "jj_version": run("jj", "--version").strip(), "state": str(state)}
        (state / "evidence.json").write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence, indent=2))
    finally:
        server.terminate()
        server.wait(timeout=20)
        log.close()


if __name__ == "__main__":
    main()
