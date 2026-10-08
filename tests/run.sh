#!/usr/bin/env bash
# Non-interactive tests for agent-sudo. A fake zenity answers every dialog with
# Deny, so no command ever runs as root and no real password prompt appears.
# Uses throwaway XDG dirs, so the real log and config are untouched.

# shellcheck disable=SC2319  # check() deliberately takes the status of a [ ] test
set -u
here=$(cd "$(dirname "$0")" && pwd)
root=$(dirname "$here")
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

export PATH="$here/fakebin:$root/bin:$PATH"
export XDG_STATE_HOME=$work/state XDG_CONFIG_HOME=$work/config XDG_CONFIG_DIRS=$work/etc-xdg
export FAKE_ZENITY_OUT=$work/dialogs
export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-test}
unset AGENT_SUDO_BACKEND CLAUDECODE

pass=0 fail=0
check() {  # name, expected rc, actual rc, [grep pattern that must be in dialogs+stderr]
  local ok=1
  [ "$2" = "$3" ] || ok=0
  if [ $# -ge 4 ] && ! grep -qE -- "$4" "$FAKE_ZENITY_OUT" "$work/err" 2>/dev/null; then ok=0; fi
  if [ $ok = 1 ]; then pass=$((pass + 1)); echo "ok    $1"
  else fail=$((fail + 1)); echo "FAIL  $1 (rc $3, wanted $2${4:+, pattern '$4'})"; fi
}
run() { : >"$FAKE_ZENITY_OUT"; "$@" 2>"$work/err"; }
last_log() { tail -n1 "$XDG_STATE_HOME/agent-sudo/log.tsv" | cut -f"$1"; }

run agent-sudo -- id -u;                                   check "missing --reason" 64 $? 'reason is required'
run agent-sudo --reason x;                                 check "missing command" 64 $? 'usage:'
run env AGENT_SUDO_BACKEND=nope agent-sudo --reason x -- id -u; check "unknown backend" 64 $? "unknown backend"
run env -u WAYLAND_DISPLAY -u DISPLAY agent-sudo --reason x -- id -u; check "no display" 69 $? 'no graphical session'

run env AGENT_SUDO_BACKEND=sudo agent-sudo --reason "deny me" -- id -u
check "sudo backend: deny" 77 $? '=== --entry'
run env AGENT_SUDO_BACKEND=pkexec agent-sudo --reason "deny me" -- id -u
check "pkexec backend: review deny" 77 $? '=== --question'
run env AGENT_SUDO_BACKEND=run0 agent-sudo --reason "deny me" -- id -u
check "run0 backend: review deny" 77 $? '=== --question'

mkdir -p "$XDG_CONFIG_HOME/agent-sudo"; echo "backend = sudo" >"$XDG_CONFIG_HOME/agent-sudo/config"
run agent-sudo --reason "config" -- id -u;                 check "config file picks backend" 77 $? '=== --entry'
[ "$(last_log 8)" = sudo ];                                check "log records backend" 0 $?
rm "$XDG_CONFIG_HOME/agent-sudo/config"

run env AGENT_SUDO_BACKEND=sudo agent-sudo --reason "big" -- sh -c "$(seq -f 'echo %g' 1 40)"
check "long request opens review window" 77 $? '=== --text-info'
run env AGENT_SUDO_BACKEND=pkexec agent-sudo --reason "big" -- sh -c "$(seq -f 'echo %g' 1 40)"
check "long request, review mode" 77 $? 'review root request \(40 lines\)'

run env AGENT_SUDO_BACKEND=sudo agent-sudo --reason "heredoc" -- tee /etc/agent-sudo-test <<'EOF'
key = value
EOF
check "heredoc stdin is shown" 77 $? 'key = value'
run bash -c 'printf "a\0b" | AGENT_SUDO_BACKEND=sudo agent-sudo --reason bin -- tee /dev/null'
check "binary stdin shown as hash" 77 $? 'binary data on stdin \(3 bytes'
run bash -c 'sleep 12 | agent-sudo --reason endless -- cat'
check "endless stdin refused" 64 $? 'did not end within 10s'

run setpriv --no-new-privs env AGENT_SUDO_BACKEND=sudo agent-sudo --reason nnp -- id -u
check "no_new_privs blocks setuid backend" 69 $? 'no_new_privs'

for agent in codex pi agy antigravity; do
  printf '#!/usr/bin/env bash\n"$@"\n' >"$work/$agent"; chmod +x "$work/$agent"
  run "$work/$agent" bash -c 'AGENT_SUDO_BACKEND=sudo agent-sudo --reason detect -- id -u'
  case $agent in codex) want=Codex ;; pi) want=Pi ;; agy) want="Antigravity CLI" ;; antigravity) want=Antigravity ;; esac
  [ "$(last_log 2)" = "$want" ]; check "detects $want as caller" 0 $?
done

run env -u WAYLAND_DISPLAY AGENT_SUDO_DRY_RUN="$work/dry.jsonl" agent-sudo --reason "dry" -- tee /etc/x <<'EOF'
k = v
EOF
check "dry run: approve, no dialog" 0 $? 'not executed'
grep -q '"stdin": "k = v' "$work/dry.jsonl";               check "dry run records stdin" 0 $?
run env AGENT_SUDO_DRY_RUN="$work/dry.jsonl" AGENT_SUDO_DRY_RUN_RC=77 agent-sudo --reason dry -- id -u
check "dry run: scripted deny" 77 $? 'denied by'
[ ! -s "$FAKE_ZENITY_OUT" ];                               check "dry run never opens a dialog" 0 $?

grep -q . "$work/state/agent-sudo/log.tsv" && ! grep -q approved "$work/state/agent-sudo/log.tsv"
check "nothing was ever approved" 0 $?

echo "$pass passed, $fail failed"
[ $fail -eq 0 ]
