# Releasing

## Checklist

1. `tests/run.sh` passes.
2. `claude plugin validate --strict plugin/.claude-plugin/plugin.json` and `claude plugin validate --strict .claude-plugin/marketplace.json` pass.
3. Bump `version` in `plugin/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (keep them equal).
4. Commit, then tag and push:
   ```bash
   git tag -a v0.2.2 -m "agent-sudo 0.2.2"
   git push origin main --tags
   ```
5. Optional: `gh release create v0.2.2 --generate-notes`.

The skill lives in one place, `plugin/skills/agent-sudo/`, and every channel installs from it: `npx skills add`, the Claude Code plugin, and `install.sh`.

## skills.sh

There is no submission step. skills.sh lists a skill automatically, from the skills CLI's anonymous install telemetry, once someone installs it:

```bash
npx skills add citizenu03bb/agent-sudo
```

The skills CLI finds the skill through `.claude-plugin/marketplace.json`, which points at `plugin/`. `npx skills update` pulls new versions for existing users.

**Short description (for the README and listing page):** Root for coding agents with a human in the loop: every sudo or polkit request opens a desktop dialog showing the agent, the exact command and its reason.

## Claude plugin directory

Submit from a claude.ai account (Pro, Max, Team or Enterprise) in the developer portal at https://claude.ai/directory/manage: **Submit new** → **Plugin bundle** → enter the repository with plugin folder `plugin` → **Validate** → fix anything marked Blocking → submit. The first organization to submit a repository folder owns that listing. The portal then scans each new commit on the branch or tag it follows, so raise `version` with every release. Checklist: https://claude.com/docs/plugins/pre-submission-checklist

Expect a "Held for a reviewer" result rather than instant listing: the plugin's scripts call sudo, pkexec and run0. Suggested answers for the form:

- **Name:** agent-sudo
- **Repository:** https://github.com/citizenu03bb/agent-sudo
- **Install:** `/plugin marketplace add citizenu03bb/agent-sudo` then `/plugin install agent-sudo@agent-sudo`
- **Icon:** `plugin/.claude-plugin/icon.png` (1024 px). The portal adopts it only at the first save, so push it before saving.
- **Components:** one skill (`agent-sudo`), with a bash wrapper and a zenity dialog helper in `scripts/`. No hooks, MCP servers or agents. About 230 tokens always-on, about 2.1k when invoked.
- **Platform:** Linux desktop (zenity plus sudo, pkexec or run0). Not macOS or native Windows yet.
- **What it does:** Agents can't answer sudo's password prompt, and the usual workarounds (NOPASSWD rules, shared sudo timestamps) give them silent root. This skill routes every root action, including polkit-backed ones like `systemctl restart`, through `agent-sudo`. That opens a dialog naming the agent and showing the exact command, any piped-in content and the agent's stated reason. Nothing runs until the user approves, and the password goes from the dialog to sudo/polkit without passing through the agent.
- **Security notes:**
  - `sudo -k` is used on every call, so it ignores and never creates cached sudo logins.
  - `run0`'s temporary polkit authorization is revoked before and after each call.
  - The reason line is labelled as unverified.
  - Long requests and piped input are shown in full before approval.
  - The README states the limits plainly: it's a consent layer for agents that follow instructions, not a boundary against a hijacked agent.
- **Testing:** 24 non-interactive tests with a fake dialog that never approves. A behaviour benchmark (`evals/`) across Claude Code, Pi and the Antigravity CLI, run in a bwrap sandbox with no system bus so it can't raise real prompts. Manually verified on Ubuntu with the sudo, pkexec and run0 backends, from Claude Code, Codex, Pi and Antigravity.
