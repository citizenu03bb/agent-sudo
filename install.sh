#!/usr/bin/env bash
# Install symlinks without replacing existing files or skill directories.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
skill=$here/plugin/skills/agent-sudo
install_home=$HOME
agents=()
while [ $# -gt 0 ]; do
  case $1 in
    --home) [ $# -ge 2 ] || exit 64; install_home=$2; shift 2 ;;
    --agent) [ $# -ge 2 ] || exit 64; agents+=("$2"); shift 2 ;;
    -h|--help)
      echo 'usage: ./install.sh [--agent claude|codex|pi|antigravity]... [--home DIRECTORY]'
      echo 'Without --agent, detect existing agent configuration directories.'
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 64 ;;
  esac
done
[[ $install_home = /* ]] || { echo '--home must be an absolute path' >&2; exit 64; }
if [ ${#agents[@]} -eq 0 ]; then
  [ ! -d "$install_home/.claude" ] || agents+=(claude)
  [ ! -d "$install_home/.codex" ] || agents+=(codex)
  [ ! -d "$install_home/.pi/agent" ] || agents+=(pi)
  [ ! -d "$install_home/.gemini/config" ] || agents+=(antigravity)
fi
sources=("$skill/scripts/agent-sudo")
targets=("$install_home/.local/bin/agent-sudo")
for agent in "${agents[@]}"; do
  case $agent in
    claude) directory=.claude/skills ;;
    codex) directory=.codex/skills ;;
    pi) directory=.pi/agent/skills ;;
    antigravity) directory=.gemini/config/skills ;;
    *) echo "Unknown agent: $agent" >&2; exit 64 ;;
  esac
  sources+=("$skill")
  targets+=("$install_home/$directory/agent-sudo")
done
# Preflight every target before making any links. Never follow a directory link.
for target in "${targets[@]}"; do
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "Refusing to replace existing file or directory: $target" >&2
    exit 1
  fi
done
for i in "${!targets[@]}"; do
  mkdir -p "$(dirname "${targets[$i]}")"
  ln -sfnT "${sources[$i]}" "${targets[$i]}"
  printf 'Installed %s -> %s\n' "${targets[$i]}" "${sources[$i]}"
done
if [ ${#agents[@]} -eq 0 ]; then
  echo 'No agent detected. Re-run with --agent to install its skill.'
fi
case ":$PATH:" in
  *":$install_home/.local/bin:"*) ;;
  *) printf 'Add this directory to your shell PATH: %s/.local/bin\n' "$install_home" ;;
esac
for dependency in zenity; do
  command -v "$dependency" >/dev/null || echo "Missing runtime dependency: $dependency" >&2
done
if ! command -v sudo >/dev/null && ! command -v pkexec >/dev/null && ! command -v run0 >/dev/null; then
  echo 'Missing runtime backend: install sudo, pkexec or run0.' >&2
fi
echo 'Keep this clone at its current path; installed links point into it.'
