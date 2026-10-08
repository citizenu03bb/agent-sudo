# agent-sudo

Root for coding agents (Claude Code, Codex, Pi) with a human in the loop. Each request opens a desktop dialog showing which agent is asking, the exact command (including any heredoc or piped stdin), the agent's stated reason and the working directory. The command runs only after you approve, and your password never passes through the agent.

```bash
agent-sudo --reason "install foo from the distro repo" -- sh -c 'apt-get update && apt-get install -y foo'
```

## Why

Agents have no terminal, so `sudo` can't prompt them. The usual workarounds are worse: `NOPASSWD` rules, or a shared sudo timestamp (`timestamp_type=global`) that lets any agent run `sudo -n` silently right after you've used sudo in a terminal. agent-sudo forces a fresh, visible approval for every request instead.

## Install

Needs bash, zenity, and at least one of sudo, pkexec (polkit) or run0 (systemd 256+).

```bash
./install.sh
```

This symlinks `bin/agent-sudo` into `~/.local/bin` and `skill/` into the skill directories of Claude Code (`~/.claude/skills`), Codex (`~/.codex/skills`) and Pi (`~/.pi/agent/skills`), whichever exist. The skill tells agents to use agent-sudo instead of calling sudo, to batch privileged steps into one request, and how to react to each exit code.

## Backends

Chosen by, in order: `AGENT_SUDO_BACKEND`, then `backend = ...` in `~/.config/agent-sudo/config`, then `/etc/xdg/agent-sudo/config`, then `auto`.

| backend | how you approve |
|---|---|
| `sudo` | type your password in agent-sudo's dialog; it goes straight to `sudo -k -A` |
| `pkexec` | approve in agent-sudo's review window, then type your password in the desktop's polkit prompt |
| `run0` | same as pkexec, via systemd; polkit's remembered approval is revoked before and after each call |
| `auto` | inside a `no_new_privs` sandbox: run0 if the system bus is reachable, otherwise refuse with a hint to re-run outside the sandbox. Else pkexec if a polkit agent is running, else sudo |

`sudo -k` ignores any cached sudo login and saves none, so a terminal `sudo` never carries over to an agent.

Requests over 15 lines or 1500 characters open a scrollable review window first. Piped or heredoc stdin is captured and shown, and must end within 10 seconds; binary stdin is shown as size and hash only.

## Exit codes

| code | meaning |
|---|---|
| 77 | denied, or the dialog timed out |
| 69 | no way to ask from here: no graphical session, or inside a sandbox |
| 64 | usage error |
| other | the command's own exit code |

Every request is logged to `~/.local/state/agent-sudo/log.tsv`: time, agent, outcome, exit code, directory, reason, command, backend.

## Security model

agent-sudo is a consent and visibility layer for agents that follow their instructions. It is not a boundary against an agent that is actively hostile, for example one hijacked by prompt injection. Such an agent can skip agent-sudo and use any cached sudo login, show its own fake password dialog, or edit your shell startup files. Keep sudo timestamps per-terminal (`timestamp_type=tty`), and with pkexec or run0 only type your password into the desktop's own prompt.

The reason line is written by the agent and labelled as unverified. Commands that run files the agent can edit (`make install`, `./setup.sh`) execute agent-written code even when the command itself looks harmless.

## Tests

```bash
tests/run.sh
```

A fake zenity answers every dialog with Deny, so the tests never run anything as root or show a real prompt. They use throwaway XDG directories and leave your log and config alone.

## License

MIT
