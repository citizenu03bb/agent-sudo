---
name: agent-sudo
description: Run a command that needs root on the user's machine. Use whenever a task needs sudo or root (installing system packages, editing /etc, system-level systemctl, mount/umount, modprobe/DKMS, writing under /usr or /opt, disk tools) instead of calling sudo yourself. Opens a desktop dialog that shows the user the exact command and your reason; the user approves by typing the password, which never passes through you.
---

# agent-sudo

You have no terminal, so `sudo` can't ask you for a password, and any cached sudo login belongs to the user, not to you. Every root command goes through `agent-sudo`:

```bash
agent-sudo --reason "<one honest line: why this needs root>" -- <command> [args...]
```

## Rules

1. **Never call `sudo` directly.** No `sudo -n` to probe for a cached login, no `sudo -S`, never echo, pipe or ask for a password in chat.
2. **One dialog per call, so batch.** Put a privileged sequence in one call and show the script inline, so the user sees all of it in the dialog:
   `agent-sudo --reason "install foo from the distro repo" -- sh -c 'apt-get update && apt-get install -y foo'`
   Keep unprivileged steps (downloads, builds, reads) outside the call.
3. **What the user sees must be what runs.** Don't hand `agent-sudo` a script file from a temp or project path: the user can't read its contents in the dialog. Inline it with `sh -c '...'`, or pipe it in: stdin is captured and shown in the dialog, so these are fine:
   `agent-sudo --reason "..." -- sh <<'EOF'` … `EOF`
   `agent-sudo --reason "write foo config" -- tee /etc/foo.conf <<'EOF'` … `EOF`
   Stdin must end within 10 s (heredocs and small pipes do); a stream that stays open is refused. Binary stdin is shown only as a size and hash, so avoid it. Long requests open a scrollable review window before the password dialog.
4. **Investigate first without root.** Read-only checks (`systemctl status`, `journalctl --user`, `ls -l`, `cat` of world-readable files) don't need it.
5. **Destructive operations** (mkfs, dd, partitioning, umount, rm on system paths, chmod/chown -R): first show the identifying evidence in chat (`lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT,SERIAL`, `findmnt`, `fuser -vm`), then make the call.
6. **Run it in the foreground.** The dialog waits up to 3 minutes (`--timeout` to change it). Don't background it, and don't fire several in parallel.

## Exit codes

| code | meaning | what to do |
|---|---|---|
| 77 | the user clicked Deny, or the dialog timed out | Don't retry the same command. Ask in chat what they want. |
| 69 | no way to ask the user from here (no graphical session, or inside a sandbox) | Inside a sandbox: re-run the same call outside it. Otherwise give the user the command to run themselves (in Claude Code, the `!` prefix runs it in-session). |
| 64 | usage error (e.g. missing `--reason`) | Fix the call. |
| other | the command's own exit code | Handle it normally. |

Every request is logged to `~/.local/state/agent-sudo/log.tsv`.

## Backends

The user picks the backend; you don't. `AGENT_SUDO_BACKEND` or `~/.config/agent-sudo/config` (`backend = auto|sudo|pkexec|run0`), default `auto`. Depending on it, the user either types the password in agent-sudo's dialog (sudo), or approves in agent-sudo's review window and then types it in the desktop's own polkit prompt (pkexec, run0). Either way, the command runs only after the user approves.

## Per-agent notes

- **Codex:** agent-sudo cannot work inside the Codex sandbox (read-only filesystem, no system D-Bus, no setuid). Always request escalation (run outside the sandbox) for the `agent-sudo` call, with the same reason as the justification. If escalation isn't available in this session, you'll get exit 69: tell the user and give them the command.
- **Claude Code:** if the Bash sandbox is on, run the `agent-sudo` call with the sandbox disabled.
- **Pi:** runs unsandboxed; just call it.
