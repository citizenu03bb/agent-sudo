# agent-sudo

Root for coding agents (Claude Code, Codex, Pi, Antigravity) with a human in the loop. Each request opens a desktop dialog showing which agent is asking, the exact command (including any heredoc or piped stdin), the agent's stated reason and the working directory. The command runs only after you approve, and your password never passes through the agent.

```bash
agent-sudo --reason "install foo from the distro repo" -- sh -c 'apt-get update && apt-get install -y foo'
```

## Why

Agents have no terminal, so `sudo` can't prompt them. The usual workarounds are worse: `NOPASSWD` rules, or a shared sudo timestamp (`timestamp_type=global`) that lets any agent run `sudo -n` silently right after you've used sudo in a terminal. agent-sudo forces a fresh, visible approval for every request instead.

## Install

Linux desktop. Needs bash, zenity, and at least one of sudo, pkexec (polkit) or run0 (systemd 256+). On Windows, WSL with WSLg (which runs Linux GUI apps such as zenity) should work, but is untested.

**As a skill, for any agent** ([skills.sh](https://skills.sh)):

```bash
npx skills add citizenu03bb/agent-sudo
```

**As a Claude Code plugin:**

```text
/plugin marketplace add citizenu03bb/agent-sudo
/plugin install agent-sudo@agent-sudo
```

**From a clone**, which also puts `agent-sudo` on your PATH:

```bash
git clone https://github.com/citizenu03bb/agent-sudo && cd agent-sudo && ./install.sh
```

`install.sh` symlinks `skills/agent-sudo/scripts/agent-sudo` into `~/.local/bin` and `skills/agent-sudo/` into the skill directories of Claude Code (`~/.claude/skills`), Codex (`~/.codex/skills`), Pi (`~/.pi/agent/skills`) and Antigravity, both IDE and `agy` CLI (`~/.gemini/config/skills`), whichever exist. With the other two methods the wrapper ships inside the skill (`scripts/`) and agents call it from there.

The skill tells agents to use agent-sudo instead of calling or probing sudo, to treat polkit-backed commands as root actions, to batch privileged steps into one request, and to stop after a deny.

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

Root doesn't only come through sudo. On a desktop, plain `systemctl restart`, `pkcon install`, `snap install`, `nmcli` and similar commands escalate through polkit, and the desktop's password prompt then can't say which agent asked. The skill tells agents to route these through agent-sudo too.

## Known gap

Skills load on demand. In benchmarks, Pi and Antigravity read the skill before acting, but Claude often tried `sudo -n` or a plain `systemctl` first and only loaded the skill after that failed. The worst outcome is a prompt you can refuse, since nothing runs as root without your approval, but expect the occasional extra click. This should shrink as agents get better at loading skills before acting.

## Tests

```bash
tests/run.sh
```

A fake zenity answers every dialog with Deny, so the tests never run anything as root or show a real prompt. They use throwaway XDG directories and leave your log and config alone.

### Dry-run mode

`AGENT_SUDO_DRY_RUN=<file>` makes agent-sudo record each request (agent, reason, argv, stdin) as a JSON line and answer with `AGENT_SUDO_DRY_RUN_RC` (0 approve, 77 deny, 69 can't ask) without a dialog and without running anything. Useful for testing an agent integration.

### Agent benchmark

`evals/` holds a behaviour benchmark in the layout of the skill-creator skill: six tasks (`evals/evals.json`), run against Claude Code, Pi and the Antigravity CLI with and without the skill, or with two skill versions. Grading is automatic, from the recorded requests and transcripts.

```bash
python3 evals/run_bench.py --iteration 1 --work-root "$(mktemp -d)" [--agents claude,pi,agy] [--configs with_skill,without_skill]
python3 evals/grade.py agent-sudo-workspace/iteration-1
```

Nothing runs as root. Each agent runs under `bwrap` with the system D-Bus hidden, so no polkit prompt can appear. A per-run tools directory first on PATH holds an agent-sudo shim in dry-run mode and recording stand-ins for sudo, pkexec, run0, docker and the other escalation routes. Results, the harness itself and agents' persistent memories are hidden from the agents under test. For the agy runs, the harness temporarily adds allow-rules to `~/.gemini/antigravity-cli/settings.json` and restores the file byte-for-byte afterwards. Benchmark runs use real model calls.

## License

MIT
