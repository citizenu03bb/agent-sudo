---
name: agent-sudo
description: Run a command that needs root on the user's machine. Use whenever a task needs sudo or root (installing system packages, editing /etc, mount/umount, modprobe/DKMS, writing under /usr or /opt, disk tools) and also for system changes that go through polkit without sudo (systemctl start/stop/restart/enable on system units, pkcon, snap install, nmcli, timedatectl/hostnamectl set-*). Use it instead of calling or probing sudo yourself, even just `sudo -n`. Uses the user's remembered sudo or polkit login; when a password is needed, a desktop prompt shows the user the exact command and your reason, and the password never passes through you. Every request is logged.
---

# agent-sudo

You have no terminal, so `sudo` can't ask you for a password. Every root command goes through `agent-sudo`:

```bash
agent-sudo --reason "<one honest line: why this needs root>" -- <command> [args...]
```

If `agent-sudo` isn't on your PATH, use the copy bundled with this skill: `scripts/agent-sudo` in this skill's directory (the folder containing this SKILL.md), called by its full path. It needs a desktop session (zenity, plus sudo, pkexec or run0) on Linux.

The point is that every root action is attributed to you and logged with your reason, and that when a password is needed the user sees exactly what it is for. Often nothing is shown: while the user's login is fresh, requests just run. Three habits defeat that, so check yourself against them before your first command:

- **Don't probe or call sudo yourself.** `sudo -n true`, `sudo -l` or `sudo -n <cmd>` either fail (no terminal) or run as root with no record of who asked or why. When a step needs root, go straight to `agent-sudo`; it is just as quick when the login is fresh.
- **polkit commands are root commands.** `systemctl restart|start|stop|enable` on a system unit, `pkcon install`, `snap install`, `nmcli` changes, `timedatectl`/`hostnamectl set-*` work without sudo by making the desktop pop a password prompt that names no agent and logs nothing. Run them through `agent-sudo` like anything else: `agent-sudo --reason "restart the stuck print spooler" -- systemctl restart cups`.
- **No means stop.** If `agent-sudo` exits 77 (denied) or 69 (can't ask from here), don't try to reach the same result another way: not `sudo`, `pkexec`, `run0`, a plain `systemctl`, `docker` or a different package manager. Tell the user what you wanted to run and let them decide.

## Rules

1. **Never call `sudo` (or `pkexec`, `run0`, `su`) directly.** No `sudo -S`, never echo, pipe or ask for a password in chat.
2. **One request per step, so batch.** Each call is at most one prompt and one log entry. Put a privileged sequence in one call and show the script inline, so the user sees all of it in the prompt and the log:
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
| 77 | the user clicked Deny, or the dialog timed out | Stop. Don't retry, and don't reach the same result by another route. Say what you wanted to run and ask what they want. |
| 69 | no way to ask the user from here (no graphical session, or inside a sandbox) | If your harness can run this one call outside its sandbox (e.g. Codex escalation), re-run the same `agent-sudo` call there. Otherwise stop and give the user the exact command to run themselves (in Claude Code, the `!` prefix runs it in-session). Don't try other routes. |
| 64 | usage error (e.g. missing `--reason`) | Fix the call. |
| other | the command's own exit code | Handle it normally. |

Every request is logged to `~/.local/state/agent-sudo/log.tsv`. The user can make `agent-sudo` available everywhere with the repository's `install.sh`; don't run it yourself unless they ask.

## Backends and prompts

The user picks the backend and the prompting; you don't. With the default `confirm = auth`, a request runs without any prompt while the user's sudo or polkit login is fresh, and otherwise shows one password prompt with your command and reason. With `confirm = always`, the user also gets an Approve / Deny dialog before every command. Either way, write the reason for a human who may read it in a prompt or the log later.

## Per-agent notes

- **Codex:** agent-sudo cannot work inside the Codex sandbox (read-only filesystem, no system D-Bus, no setuid). Always request escalation (run outside the sandbox) for the `agent-sudo` call, with the same reason as the justification. If escalation isn't available in this session, you'll get exit 69: tell the user and give them the command.
- **Claude Code:** if the Bash sandbox is on, run the `agent-sudo` call with the sandbox disabled.
- **Pi:** runs unsandboxed; just call it.
- **Antigravity (IDE and `agy` CLI):** runs commands unsandboxed by default; just call it. If the session was started with `--sandbox` and you get exit 69, tell the user and give them the command.
