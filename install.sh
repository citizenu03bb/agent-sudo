#!/usr/bin/env bash
# Symlink agent-sudo into PATH and the skill into each agent's skill directory.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
skill=$here/skills/agent-sudo

chmod +x "$skill/scripts/agent-sudo" "$skill/scripts/agent-sudo-dialog"
mkdir -p "$HOME/.local/bin"
ln -sfn "$skill/scripts/agent-sudo" "$HOME/.local/bin/agent-sudo"

# Antigravity (GUI and agy CLI) share the global customization root ~/.gemini/config.
[ -d "$HOME/.gemini/config" ] && mkdir -p "$HOME/.gemini/config/skills"

for d in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.pi/agent/skills" \
         "$HOME/.gemini/config/skills"; do
  [ -d "$d" ] || continue
  ln -sfn "$skill" "$d/agent-sudo"
  echo "skill -> $d/agent-sudo"
done
echo "bin   -> $HOME/.local/bin/agent-sudo"
