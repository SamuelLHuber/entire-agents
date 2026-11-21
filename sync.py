"""Poll persisted Pi JSONL; publish immutable snapshots and a queryable local index.
Credentials use boto3's normal chain. Never copy ~/.pi/agent/auth.json.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import re
import sys
import time
import urllib.request

import boto3
import duckdb


def ingest(db, session_id, raw):
    # A writer may be midway through its last line; never index a partial record.
    records = []
    for line in raw.splitlines(keepends=True):
        if not line.endswith(b"\n"):
            break
        records.append(json.loads(line))
    db.execute("CREATE TABLE IF NOT EXISTS entries(session_id VARCHAR, ordinal BIGINT, entry JSON, PRIMARY KEY(session_id, ordinal))")
    db.execute("""CREATE OR REPLACE VIEW models AS
        SELECT session_id, ordinal,
               json_extract_string(entry, '$.provider') AS provider,
               json_extract_string(entry, '$.modelId') AS model
        FROM entries WHERE json_extract_string(entry, '$.type') = 'model_change'""")
    db.execute("""CREATE OR REPLACE VIEW sessions AS
        SELECT session_id, 'pi' AS harness, count(*) AS entries FROM entries GROUP BY session_id""")
    db.execute("BEGIN")
    try:
        for ordinal, record in enumerate(records):
            db.execute("INSERT OR REPLACE INTO entries VALUES (?, ?, ?)", [session_id, ordinal, json.dumps(record)])
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    return len(records)


def index_commits(db):
    result = subprocess.run([
        "jj", "--ignore-working-copy", "log", "--no-graph", "-r", "all()",
        "-T", 'json({"commit_id" => commit_id, "description" => description}) ++ "\\n"',
    ], capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr)
    db.execute("CREATE TABLE IF NOT EXISTS commits(commit_id VARCHAR PRIMARY KEY, session_id VARCHAR, description VARCHAR)")
    for line in result.stdout.splitlines():
        commit = json.loads(line)
        match = re.search(r"(?mi)^Agent-Session: ([A-Za-z0-9_.-]+)$", commit["description"])
        if match:
            db.execute("INSERT OR REPLACE INTO commits VALUES (?, ?, ?)",
                       [commit["commit_id"], match[1], commit["description"]])


def main():
    source, session_id = sys.argv[1:]
    database = Path(os.environ.get("AGENT_ANALYTICS_DB", ".state/sessions.duckdb"))
    database.parent.mkdir(parents=True, exist_ok=True)
    bucket = os.environ.get("AGENT_S3_BUCKET")
    ingest_url = os.environ.get("AGENT_SESSION_INGEST_URL")
    if not bucket and not ingest_url:
        raise SystemExit("set AGENT_S3_BUCKET or AGENT_SESSION_INGEST_URL")
    client = boto3.client("s3", endpoint_url=os.environ.get("AGENT_S3_ENDPOINT"),
                          config=boto3.session.Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 1})) if bucket else None

    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    previous = None
    while True:
        try:
            raw = Path(source).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            with duckdb.connect(str(database)) as db:
                ingest(db, session_id, raw)
                index_commits(db)
            if digest != previous:
                # Close connection between polls so independent readers can query live.
                key = f"sessions/{session_id}/{digest}.jsonl"
                if client:
                    client.put_object(Bucket=bucket, Key=key, Body=raw)
                    # Publish latest only after the immutable object is durable.
                    client.put_object(Bucket=bucket, Key=f"sessions/{session_id}/latest.json",
                                      Body=json.dumps({"key": key, "sha256": digest, "bytes": len(raw)}).encode())
                if ingest_url:
                    headers = {"Content-Type": "application/json"}
                    bearer = os.environ.get("AGENT_SESSION_INGEST_BEARER")
                    bearer_file = os.environ.get("AGENT_SESSION_INGEST_BEARER_FILE")
                    if bearer_file:
                        bearer = Path(bearer_file).read_text().strip()
                    if bearer:
                        headers["Authorization"] = f"Bearer {bearer}"
                    body = json.dumps({
                        "harness": "pi",
                        "session_id": session_id,
                        "sha256": digest,
                        "bytes": len(raw),
                        "key": key,
                        "transcript_jsonl": raw.decode("utf-8", "replace"),
                    }).encode()
                    request = urllib.request.Request(ingest_url, data=body, headers=headers, method="POST")
                    with urllib.request.urlopen(request, timeout=10) as response:
                        if response.status < 200 or response.status >= 300:
                            raise RuntimeError(f"ingest returned HTTP {response.status}")
                previous = digest
        except Exception as error:
            print(f"session sync failed (will retry): {error}", file=sys.stderr, flush=True)
        if stopping:
            break
        time.sleep(1)


if __name__ == "__main__":
    main()
