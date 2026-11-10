# agent-sudo

Lets coding agents run root commands even though they have no terminal. With sudo and the default settings, requests run without interrupting you while your login is still fresh. With pkexec or run0, a separate Approve / Deny review always comes before system authentication. When a password is needed, a desktop prompt names the agent and shows the exact command, any piped-in content, the agent's stated reason and the working directory. Every request is logged, and your password goes from the prompt to sudo or polkit, never through the agent.

```bash
agent-sudo --reason "install foo from the distro repo" -- sh -c 'apt-get update && apt-get install -y foo'
```

## Why

Agents can't answer sudo's password prompt, so they fail or you copy commands across by hand. agent-sudo gives them the prompt they're missing: you type your password about as often as you would in a terminal, and you can see afterwards who asked for what. On a desktop, plain `systemctl restart` or `pkcon install` also escalate through polkit with a prompt that can't say who asked; the skill routes those through agent-sudo too.

## Settings

- `confirm = auth` (default): sudo prompts only when authentication is needed. `confirm = always`: review every sudo command too. With pkexec/run0, both settings require an Approve / Deny review before authentication, including when authentication is cached.
- `backend = auto` (default), `sudo`, `pkexec` or `run0`.

Both go in `~/.config/agent-sudo/config`.

## What the skill teaches agents

- Use `agent-sudo` for anything that needs root, including polkit-backed commands.
- Don't call or probe `sudo` directly.
- Batch privileged steps into one request, with scripts shown inline.
- Stop after a deny instead of trying another route.

## Requirements

A Linux desktop session with zenity and at least one of sudo, pkexec (polkit) or run0 (systemd 256+). Not macOS or native Windows yet.

## Security model

agent-sudo helps agents authenticate and keeps a record; it does not decide which commands are allowed. While a login is remembered, any process running as you can use it. For per-command control use `confirm = always`, or a command guard. It is not a boundary against an agent that is actively hostile, for example one hijacked by prompt injection.

Source, tests and full documentation: https://github.com/citizenu03bb/agent-sudo
