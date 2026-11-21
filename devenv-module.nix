# Reusable devenv module for agent session provenance.
# Import with a pinned fetchTarball/fetchFromGitHub from project devenv.nix.
{ pkgs, lib, config, ... }:
let
  patched = import ./packages.nix { inherit pkgs; };
  python = pkgs.python3.withPackages (p: [ p.boto3 p.duckdb ]);
  sessionSync = pkgs.writeShellApplication {
    name = "agent-session-sync";
    runtimeInputs = [ python pkgs.jujutsu ];
    text = ''
      exec ${python}/bin/python ${./sync.py} "$@"
    '';
  };
in
{
  packages = [ patched.git patched.jj python sessionSync ];

  env.AGENT_SESSION_SYNC_COMMAND = lib.getExe sessionSync;
  env.AGENT_ANALYTICS_DB = "$PWD/.devenv/state/agent-sessions.duckdb";

  enterShell = ''
    # Company/project ingest is configured by environment, never by committing secrets.
    # Preferred names are company-specific; AGENT_* remains the extension contract.
    if [ -n "''${COMPANYOS_AGENT_SESSION_INGEST_URL:-}" ] && [ -z "''${AGENT_SESSION_INGEST_URL:-}" ]; then
      export AGENT_SESSION_INGEST_URL="$COMPANYOS_AGENT_SESSION_INGEST_URL"
    fi
    if [ -n "''${COMPANYOS_AGENT_SESSION_INGEST_BEARER_FILE:-}" ] && [ -z "''${AGENT_SESSION_INGEST_BEARER_FILE:-}" ]; then
      export AGENT_SESSION_INGEST_BEARER_FILE="$COMPANYOS_AGENT_SESSION_INGEST_BEARER_FILE"
    fi
    if [ -n "''${COMPANYOS_AGENT_SESSION_INGEST_BEARER:-}" ] && [ -z "''${AGENT_SESSION_INGEST_BEARER:-}" ]; then
      export AGENT_SESSION_INGEST_BEARER="$COMPANYOS_AGENT_SESSION_INGEST_BEARER"
    fi
  '';
}
