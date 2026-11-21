{ pkgs, inputs, ... }:
let
  patched = import ./packages.nix { inherit pkgs; };
  legacy = import inputs.minio-pkgs { system = pkgs.stdenv.hostPlatform.system; };
in {
  packages = [ patched.git patched.jj pkgs.duckdb legacy.minio legacy.minio-client
    (pkgs.python3.withPackages (p: [ p.boto3 p.duckdb ])) ];
  env.AGENT_ANALYTICS_DB = "${builtins.toString ./.}/.state/sessions.duckdb";
  processes.minio.exec = "minio server .state/minio --address 127.0.0.1:9000 --console-address 127.0.0.1:9001";
}
