{ pkgs }:
{
  git = pkgs.git.overrideAttrs (old: {
    patches = (old.patches or []) ++ [ ./patches/git-session.patch ];
  });
  jj = pkgs.jujutsu.overrideAttrs (old: {
    patches = (old.patches or []) ++ [ ./patches/jj-session.patch ];
    doCheck = false;
  });
}
