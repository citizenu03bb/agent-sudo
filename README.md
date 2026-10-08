# agent-sudo

Root for coding agents (Claude Code, Codex, Pi, Antigravity) without a terminal. When a root command needs your password, a desktop prompt shows which agent is asking, the exact command (including any heredoc or piped stdin), the agent's stated reason and the working directory. While your login is still fresh, requests run without interrupting you, and every one is logged. Your password goes from the prompt to sudo or polkit, never through the agent.

```bash
agent-sudo --reason "install foo from the distro repo" -- sh -c 'apt-get update && apt-get install -y foo'
```

## Why

Agents have no terminal, so `sudo` can't ask them for a password: they fail, or you copy commands across by hand. agent-sudo gives them the prompt they're missing and nothing more. It uses each backend's own remembered login, so you type your password about as often as you would in a terminal, and it records who asked for what.

It decides how an agent gets root, not which commands may run. For rules such as "package installs yes, disk tools never", use a command guard alongside it (your agent's own permission rules, such as Claude Code's `permissions.deny`, or a dedicated shell guard), or turn on `confirm = always` below.

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

`install.sh` symlinks `plugin/skills/agent-sudo/scripts/agent-sudo` into `~/.local/bin` and `plugin/skills/agent-sudo/` into the skill directories of Claude Code (`~/.claude/skills`), Codex (`~/.codex/skills`), Pi (`~/.pi/agent/skills`) and Antigravity, both IDE and `agy` CLI (`~/.gemini/config/skills`), whichever exist. With the other two methods the wrapper ships inside the skill (`scripts/`) and agents call it from there.

The skill tells agents to use agent-sudo instead of calling or probing sudo, to treat polkit-backed commands as root actions, to batch privileged steps into one request, and to stop after a deny.

## Consent

Set with `AGENT_SUDO_CONFIRM` or `confirm = ...` in `~/.config/agent-sudo/config` (then `/etc/xdg/agent-sudo/config`).

| `confirm` | what you see |
|---|---|
| `auth` (default) | Nothing while your login is fresh. When the backend needs your password, one prompt with the whole request. |
| `always` | An Approve / Deny dialog before every command, then the backend's password prompt if it still needs one. |

Under `auth`, a fresh login means agents run root commands without asking, for as long as the backend remembers it, and a `NOPASSWD` rule in your sudoers means no prompt at all for the commands it covers. That is the point of the default, so choose `always` if you want a veto on each command.

## Backends

Chosen by, in order: `AGENT_SUDO_BACKEND`, then `backend = ...` in the same config files, then `auto`.

| backend | how authentication works |
|---|---|
| `sudo` | your sudo login. While it's fresh, nothing to type; when it has expired, agent-sudo's password dialog (`sudo -A`). A successful run renews it, as in a terminal. |
| `pkexec` | the desktop's polkit prompt, every time |
| `run0` | the desktop's polkit prompt, via systemd; polkit then remembers the approval for a few minutes |
| `auto` | inside a `no_new_privs` sandbox: run0 if the system bus is reachable, otherwise refuse with a hint to re-run outside the sandbox. Else sudo if you're in the `sudo`, `wheel` or `admin` group, else pkexec if a polkit agent is running, else sudo |

How long a login is remembered is sudo's or polkit's setting, not agent-sudo's: `timestamp_timeout` and `timestamp_type` in sudoers (with `timestamp_type=global`, one login covers every terminal and agent), and the polkit action's `auth_admin_keep` for run0.

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

agent-sudo gives agents a way to authenticate and leaves a record. It is not a boundary against an agent that is actively hostile, for example one hijacked by prompt injection: such an agent can call `sudo -n` itself while your login is fresh, show its own fake password dialog, or edit your shell startup files. While a login is remembered, any process running as you can use it, agent or not; that is how sudo and polkit work. Shorten `timestamp_timeout` if that window is too wide, and with pkexec or run0 only type your password into the desktop's own prompt.

The password goes from zenity straight to sudo, or into polkit's own prompt; agent-sudo never stores or sees it. The reason line is written by the agent and labelled as unverified. Commands that run files the agent can edit (`make install`, `./setup.sh`) execute agent-written code even when the command itself looks harmless.

Root doesn't only come through sudo. On a desktop, plain `systemctl restart`, `pkcon install`, `snap install`, `nmcli` and similar commands escalate through polkit, and the desktop's password prompt then can't say which agent asked. The skill tells agents to route these through agent-sudo too.

## Known gap

Skills load on demand. In benchmarks, Pi and Antigravity read the skill before acting, but Claude often tried `sudo -n` or a plain `systemctl` first and only loaded the skill after that failed. The worst outcome is a prompt you can refuse, since nothing runs as root without your approval, but expect the occasional extra click. This should shrink as agents get better at loading skills before acting.

## Layout

`plugin/` is the installable part: the skill (`plugin/skills/agent-sudo/`, with the wrapper and dialog in `scripts/`), the Claude plugin manifest and icon, and a short README used as the directory listing. Everything else (tests, the benchmark in `evals/`, `install.sh`) is for development and isn't installed by `npx skills add` or the Claude plugin.

## Tests

```bash
tests/run.sh
```

Fake `zenity`, `sudo`, `pkexec`, `run0`, `pkcheck` and `id` (`tests/fakebin`) stand in for the real ones, so the tests never run anything as root or show a real prompt. They cover fresh and expired logins, both `confirm` settings, wrong passwords and crashed dialogs as well as denials. They use throwaway XDG directories and leave your log and config alone.

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
