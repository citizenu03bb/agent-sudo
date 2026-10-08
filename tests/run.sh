#!/usr/bin/env bash
# Non-interactive tests for agent-sudo. Fake zenity, sudo, pkexec, run0, pkcheck
# and id (tests/fakebin) stand in for the real ones: nothing ever runs as root
# and no real password prompt appears. zenity answers Deny unless a test sets
# FAKE_ZENITY_ANSWER. Throwaway XDG dirs keep the real log and config untouched.

# shellcheck disable=SC2319  # check() deliberately takes the status of a [ ] test
set -u
here=$(cd "$(dirname "$0")" && pwd)
root=$(dirname "$here")
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

export PATH="$here/fakebin:$root/plugin/skills/agent-sudo/scripts:$PATH"
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
run env AGENT_SUDO_BACKEND=pkexec AGENT_SUDO_CONFIRM=always agent-sudo --reason "deny me" -- id -u
check "pkexec backend: review deny" 77 $? '=== --question'
run env AGENT_SUDO_BACKEND=run0 AGENT_SUDO_CONFIRM=always agent-sudo --reason "deny me" -- id -u
check "run0 backend: review deny" 77 $? '=== --question'

mkdir -p "$XDG_CONFIG_HOME/agent-sudo"; echo "backend = sudo" >"$XDG_CONFIG_HOME/agent-sudo/config"
run agent-sudo --reason "config" -- id -u;                 check "config file picks backend" 77 $? '=== --entry'
[ "$(last_log 8)" = sudo ];                                check "log records backend" 0 $?
rm "$XDG_CONFIG_HOME/agent-sudo/config"

run env AGENT_SUDO_BACKEND=sudo agent-sudo --reason "big" -- sh -c "$(seq -f 'echo %g' 1 40)"
check "long request opens review window" 77 $? '=== --text-info'
run env AGENT_SUDO_BACKEND=pkexec AGENT_SUDO_CONFIRM=always agent-sudo --reason "big" -- sh -c "$(seq -f 'echo %g' 1 40)"
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

# --- approvals (fakes run the command as the caller; a marker file shows it ran) ---
ran=$work/ran
dialogs() { grep -c '^=== ' "$FAKE_ZENITY_OUT"; }
attempt() { rm -f "$ran"; run env AGENT_SUDO_BACKEND=sudo "$@" agent-sudo --reason "touch marker" -- touch "$ran"; }

# Default (confirm = auth): the backend's remembered login decides.
attempt FAKE_SUDO_CACHED=1
check "fresh login: runs with no dialog" 0 $?
[ -e "$ran" ] && [ "$(dialogs)" = 0 ] && [ "$(last_log 3)" = cached ];  check "fresh login: logged cached" 0 $?
attempt FAKE_ZENITY_ANSWER=approve
check "expired login: one password dialog showing the request" 0 $? 'Type your password to run it'
[ -e "$ran" ] && [ "$(dialogs)" = 1 ] && [ "$(last_log 3)" = approved ]; check "expired login: ran, logged approved" 0 $?
attempt
check "expired login + deny: refused" 77 $? 'denied by'
[ ! -e "$ran" ];                                           check "expired login + deny: nothing ran" 0 $?
attempt FAKE_ZENITY_ANSWER=approve FAKE_ZENITY_PASSWORD=wrong
check "wrong password: sudo fails" 1 $? 'WRONG PASSWORD'
[ ! -e "$ran" ];                                           check "wrong password: nothing ran" 0 $?
rm -f "$work/calls"; attempt FAKE_ZENITY_ANSWER=approve FAKE_SUDO_CALLS="$work/calls"
! grep -qE '(^| )-(k|K|l)( |$)' "$work/calls" && [ "$(wc -l <"$work/calls")" = 1 ]
check "sudo called once, without -k or -l (uses and renews the login)" 0 $?

# confirm = always: an Approve click before every command.
attempt AGENT_SUDO_CONFIRM=always FAKE_SUDO_CACHED=1
check "always: review comes first, deny refuses" 77 $? 'If sudo needs your password, it will ask next'
[ ! -e "$ran" ];                                           check "always + deny: nothing ran" 0 $?
attempt AGENT_SUDO_CONFIRM=always FAKE_SUDO_CACHED=1 FAKE_ZENITY_ANSWER=approve
[ -e "$ran" ] && [ "$(dialogs)" = 1 ] && [ "$(last_log 3)" = approved ]; check "always + fresh login: one click, ran" 0 $?
attempt AGENT_SUDO_CONFIRM=always FAKE_ZENITY_ANSWER=approve
check "always + expired login: click, then password" 0 $? 'sudo needs your password'
[ -e "$ran" ] && [ "$(dialogs)" = 2 ];                     check "always + expired login: two dialogs, ran" 0 $?
mkdir -p "$XDG_CONFIG_HOME/agent-sudo"; echo "confirm = always" >"$XDG_CONFIG_HOME/agent-sudo/config"
attempt FAKE_SUDO_CACHED=1
[ ! -e "$ran" ] && [ "$(dialogs)" = 1 ];                   check "config file sets confirm = always" 0 $?
rm "$XDG_CONFIG_HOME/agent-sudo/config"
attempt AGENT_SUDO_CONFIRM=maybe;                          check "unknown confirm setting" 64 $? 'unknown confirm'

# polkit backends: polkit authenticates and keeps its own memory; nothing revokes it.
for b in pkexec run0; do
  rm -f "$ran" "$work/pk"; run env AGENT_SUDO_BACKEND=$b FAKE_PKCHECK_CALLS="$work/pk" agent-sudo --reason x -- touch "$ran"
  check "$b: polkit decides, no dialog of ours" 0 $?
  [ -e "$ran" ] && [ "$(dialogs)" = 0 ] && [ "$(last_log 3)" = polkit ] && [ ! -s "$work/pk" ]
  check "$b: ran, logged polkit, no pkcheck revoke" 0 $?
done

# auto: members of the sudo group get sudo, whatever polkit agent is around.
rm -f "$ran"; run env FAKE_ID_GROUPS="someone sudo" FAKE_SUDO_CACHED=1 agent-sudo --reason x -- touch "$ran"
[ -e "$ran" ] && [ "$(last_log 8)" = sudo ];               check "auto picks sudo for the sudo group" 0 $?

# Fail closed: a dialog that dies without recording an answer is not an approval.
attempt AGENT_SUDO_CONFIRM=always FAKE_SUDO_CACHED=1 FAKE_ZENITY_ANSWER=crash
check "sudo: crashed review refuses" 77 $? 'review dialog failed'
[ ! -e "$ran" ];                                           check "sudo: crashed review, nothing ran" 0 $?
attempt FAKE_ZENITY_ANSWER=crash
[ ! -e "$ran" ];                                           check "sudo: crashed password dialog, nothing ran" 0 $?
for b in pkexec run0; do
  rm -f "$ran"; run env AGENT_SUDO_BACKEND=$b AGENT_SUDO_CONFIRM=always FAKE_ZENITY_ANSWER=crash agent-sudo --reason x -- touch "$ran"
  check "$b: crashed review refuses" 77 $? 'review dialog failed'
  [ ! -e "$ran" ];                                         check "$b: crashed review, nothing ran" 0 $?
done

echo "$pass passed, $fail failed"
[ $fail -eq 0 ]
