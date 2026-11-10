# agent-sudo

Root for coding agents (Claude Code, Codex, Pi, Antigravity) without a terminal. When a root command needs your password, a desktop prompt shows which agent is asking, the exact command (including any heredoc or piped stdin), the agent's stated reason and the working directory. With sudo and the default settings, requests run without interrupting you while your login is still fresh. With pkexec or run0, a separate Approve / Deny review always comes first, followed by system authentication if needed. Every request is logged. Your password goes from the prompt to sudo or polkit, never through the agent.

```bash
agent-sudo --reason "install foo from the distro repo" -- sh -c 'apt-get update && apt-get install -y foo'
```

## Why

Agents have no terminal, so `sudo` can't ask them for a password: they fail, or you copy commands across by hand. agent-sudo gives them the prompt they're missing and nothing more. It uses each backend's own remembered login, so you type your password about as often as you would in a terminal, and it records who asked for what.

It decides how an agent gets root, not which commands may run. For rules such as "package installs yes, disk tools never", use a command guard alongside it (your agent's own permission rules, such as Claude Code's `permissions.deny`, or a dedicated shell guard), or turn on `confirm = always` below.

## Install

Requires a Linux graphical desktop, Bash, Zenity, GNU core utilities, and at least one of `sudo`, `pkexec` or `run0` (systemd 256+). The installer does not install system packages or configure privilege policies. WSLg is untested; native Windows and macOS are unsupported.

### From a clone

```bash
git clone https://github.com/citizenu03bb/agent-sudo.git
cd agent-sudo
./install.sh
```

This links the command into `~/.local/bin` and detects existing agent configuration directories. It creates missing skill directories for detected agents. For a fresh agent installation, select one or more explicitly:

```bash
./install.sh --agent claude --agent codex
```

Supported names: `claude`, `codex`, `pi`, `antigravity`. Targets are respectively `~/.claude/skills`, `~/.codex/skills`, `~/.pi/agent/skills` and `~/.gemini/config/skills`. Existing files or real skill directories are never overwritten; resolve a reported conflict before retrying. Existing symlinks are updated.

If `~/.local/bin` is absent from PATH, add this to your shell startup file and open a new shell (or run it in your current shell):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Keep the clone at the same path: these are symlinks, not copies. To update, run `git pull --ff-only` from the clone. Start a new agent session to reload the skill. To uninstall, remove only the installed symlinks; configuration and logs are retained. `--home /absolute/directory` selects an alternate installation destination, mainly for tests.

### As a skill for a supported agent

Requires Node.js/npm. The [skills CLI](https://github.com/vercel-labs/skills) installs the skill and its bundled scripts, not a global `agent-sudo` executable:

```bash
npx skills add citizenu03bb/agent-sudo --skill agent-sudo
```

Follow the CLI's agent and scope selection. Use `--global` for a user-wide installation rather than project scope. Agents invoke the bundled `scripts/agent-sudo` when it is not on PATH. Use `npx skills update` to check for updates.

### Claude Code: this repository's custom marketplace

**This plugin is not published in Claude's official marketplace.** These commands add this repository as a custom marketplace; run them inside Claude Code:

```text
/plugin marketplace add citizenu03bb/agent-sudo
/plugin install agent-sudo@agent-sudo
```

The plugin bundles the skill and scripts; it does not install a global executable or Linux dependencies. For updates, refresh this custom marketplace and update the plugin through Claude Code's plugin manager. Choose one skill installation method per agent to avoid duplicate copies.

The skill instructs agents to route privileged actions through the wrapper, include their justification, and stop after a refusal. It cannot enforce those instructions against a hostile agent.

## Consent

Set with `confirm = ...` in `~/.config/agent-sudo/config` (then `/etc/xdg/agent-sudo/config`). `AGENT_SUDO_CONFIRM` may request `always`, but cannot downgrade an effective configured `always` to `auth`. This is a configuration safeguard, not an isolation boundary: the same user can still modify their config or XDG search paths.

| `confirm` | what you see |
|---|---|
| `auth` (default) | With sudo: no prompt while your login is fresh; otherwise the password dialog includes the request (large requests open a separate review first). With pkexec/run0: always review first, then system authentication if needed. |
| `always` | An Approve / Deny dialog before every command, then the backend's password prompt if it still needs one. |

With sudo under `auth`, a fresh login means agents run root commands without asking, for as long as sudo remembers it, and a `NOPASSWD` rule in your sudoers means no prompt at all for the commands it covers. Choose `always` if you want a veto on each sudo command too. Polkit backends always require review because their system prompt cannot display the captured stdin and full request context. `always` does not add a second review to those backends. An automatic pkexec-to-sudo fallback reuses the approval for the same request; only authentication may be requested again.

## Backends

Chosen by, in order: `AGENT_SUDO_BACKEND`, then `backend = ...` in the same config files, then `auto`.

| backend | how authentication works |
|---|---|
| `sudo` | your sudo login. While it's fresh, nothing to type; when it has expired, agent-sudo's password dialog (`sudo -A`). A successful run renews it, as in a terminal. |
| `pkexec` | our request review, followed by the desktop's polkit authentication |
| `run0` | our request review every time, followed by polkit authentication via systemd if needed; remembered authentication does not skip review |
| `auto` | inside a `no_new_privs` sandbox: run0 if the system bus is reachable, otherwise refuse with a hint to re-run outside the sandbox. Else sudo if you're in the `sudo`, `wheel` or `admin` group, else pkexec if a polkit agent is running, else sudo |

How long a login is remembered is sudo's or polkit's setting, not agent-sudo's: `timestamp_timeout` and `timestamp_type` in sudoers (with `timestamp_type=global`, one login covers every terminal and agent), and the polkit action's `auth_admin_keep` for run0.

Requests whose command, agent name, reason and working directory do not fit a compact label open a scrollable review window first. Long lines and multiline explanations are preserved in full in that window. Piped or heredoc stdin is captured and shown, and must end within 10 seconds; binary stdin is shown as size and hash only.

## Exit codes

| code | meaning |
|---|---|
| 77 | denied, or the dialog timed out |
| 69 | no way to ask from here: no graphical session, or inside a sandbox |
| 64 | usage error |
| other | the command's own exit code |

Every request is logged to `~/.local/state/agent-sudo/log.tsv`: time, agent, outcome, exit code, directory, reason, command, backend. New records escape backslashes, tabs, newlines and carriage returns as `\\`, `\t`, `\n` and `\r` in every field, so multiline explanations remain one physical record. Existing records are not rewritten. The dialog preserves the original multiline text.

## Security model

agent-sudo gives agents a way to authenticate and leaves a record. It is not a boundary against an agent that is actively hostile, for example one hijacked by prompt injection: such an agent can call `sudo -n` itself while your login is fresh, show its own fake password dialog, or edit your shell startup files. While a login is remembered, any process running as you can use it, agent or not; that is how sudo and polkit work. Shorten `timestamp_timeout` if that window is too wide, and with pkexec or run0 only type your password into the desktop's own prompt.

The password goes from zenity straight to sudo, or into polkit's own prompt; agent-sudo never stores or sees it. The reason line is written by the agent and labelled as unverified. Commands that run files the agent can edit (`make install`, `./setup.sh`) execute agent-written code even when the command itself looks harmless.

Root doesn't only come through sudo. On a desktop, plain `systemctl restart`, `pkcon install`, `snap install`, `nmcli` and similar commands escalate through polkit, and the desktop's password prompt then can't say which agent asked. The skill tells agents to route these through agent-sudo too.

## Known gap

Skills load on demand. In benchmarks, Pi and Antigravity read the skill before acting, but Claude often tried `sudo -n` or a plain `systemctl` first and only loaded the skill after that failed. What that costs depends on your login:

- While your sudo login is fresh, such a `sudo -n` succeeds: the command runs as root without going through agent-sudo, so it isn't logged with an agent and a reason. That is no more access than sudo already grants under your login, but it is a gap in the record.
- When the login has expired, it fails, and the agent then uses agent-sudo.
- A plain `systemctl restart` (or `pkcon`, `nmcli`…) goes to polkit directly: the desktop's own prompt, which doesn't name the agent, or no prompt if polkit still remembers a recent approval.

A command guard that intercepts the agent's shell commands closes this gap. It should also shrink as agents get better at loading skills before acting.

## Layout

`plugin/` is the installable part: the skill (`plugin/skills/agent-sudo/`, with the wrapper and dialog in `scripts/`), the Claude plugin manifest and icon, and a short README used as the directory listing. Everything else (tests, the benchmark in `evals/`, `install.sh`) is for development and isn't installed by `npx skills add` or the Claude plugin.

## Tests

[GitHub Actions CI](https://github.com/citizenu03bb/agent-sudo/actions/workflows/ci.yml) runs on pushes and pull requests, on Ubuntu 22.04 and 24.04. It checks shell syntax, runs the simulated-backend suite, checks installation into temporary destinations, and measures real Zenity dialogs under Xvfb on an 800 × 600 screen. Test commands never escalate privileges.

```bash
tests/run.sh
```

Fake `zenity`, `sudo`, `pkexec`, `run0`, `pkcheck` and `id` (`tests/fakebin`) stand in for the real ones, so the tests never run anything as root or show a real prompt. They cover fresh and expired logins, both `confirm` settings, wrong passwords, failed reviews, polkit review before execution, stdin preservation and reuse of approval on pkexec-to-sudo fallback. They use throwaway XDG directories and leave your log and config alone.

Real Zenity layout checks (requires Xvfb and xwininfo; no password or root command):

```bash
xvfb-run -a -s '-screen 0 800x600x24' python3 tests/dialog-geometry.py
```

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
