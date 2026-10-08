#!/usr/bin/env bash
# Symlink agent-sudo into PATH and into each agent's skill directory.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)

chmod +x "$here/bin/agent-sudo" "$here/libexec/agent-sudo-dialog"
mkdir -p "$HOME/.local/bin"
ln -sfn "$here/bin/agent-sudo" "$HOME/.local/bin/agent-sudo"

for d in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.pi/agent/skills"; do
  [ -d "$d" ] || continue
  ln -sfn "$here/skill" "$d/agent-sudo"
  echo "skill -> $d/agent-sudo"
done
echo "bin   -> $HOME/.local/bin/agent-sudo"
