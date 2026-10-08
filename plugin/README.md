# agent-sudo

Lets coding agents run root commands with you in the loop. Every request opens a desktop dialog that names the agent and shows the exact command, any piped-in content, the agent's stated reason and the working directory. Nothing runs until you approve, and your password goes from the dialog to sudo or polkit without passing through the agent.

```bash
agent-sudo --reason "install foo from the distro repo" -- sh -c 'apt-get update && apt-get install -y foo'
```

## Why

Agents have no terminal, so `sudo` can't ask them for a password. The usual workarounds give them silent root: `NOPASSWD` rules, or a shared sudo login that any agent can reuse with `sudo -n` right after you've typed your password in a terminal. On a desktop, plain `systemctl restart` or `pkcon install` also escalate through polkit, and the password prompt can't say which agent asked. agent-sudo asks you every time, says who is asking, and caches nothing.

## What the skill teaches agents

- Use `agent-sudo` for anything that needs root, including polkit-backed commands.
- Never probe with `sudo -n`.
- Batch privileged steps into one request, with scripts shown inline.
- Stop after a deny instead of trying another route.

## Requirements

A Linux desktop session with zenity and at least one of sudo, pkexec (polkit) or run0 (systemd 256+). Not macOS or native Windows yet.

## Security model

agent-sudo is a consent and visibility layer for agents that follow their instructions. It is not a boundary against an agent that is actively hostile, for example one hijacked by prompt injection. The reason line is written by the agent and shown as unverified.

Source, tests and full documentation: https://github.com/citizenu03bb/agent-sudo
