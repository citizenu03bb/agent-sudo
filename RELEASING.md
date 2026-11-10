# Releasing

The skill and scripts live in `plugin/skills/agent-sudo/`. Clone installation, the skills CLI and this repository's custom Claude Code marketplace use that source. The plugin is not listed in Claude's official marketplace.

1. Run `bash tests/run.sh`, `python3 tests/install.py`, and `xvfb-run -a -s '-screen 0 800x600x24' python3 tests/dialog-geometry.py`.
2. Validate the plugin and marketplace with `claude plugin validate plugin` and `claude plugin validate .`.
3. Set the same new version in `plugin/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`. Update descriptions and docs when behavior changes.
4. Commit and push; wait for both GitHub Actions jobs to pass on that exact commit.
5. Tag that commit and push the tag, then create a GitHub release with notes describing changes and compatibility considerations. Never move an existing release tag.

For version 0.5.0:

```bash
git tag -a v0.5.0 -m 'agent-sudo 0.5.0'
git push origin v0.5.0
gh release create v0.5.0 --verify-tag --title 'agent-sudo 0.5.0' --notes-file /path/to/release-notes.md
```

Users of the clone update with `git pull --ff-only`. Skills CLI users can use `npx skills update`. Claude Code users refresh this repository's custom marketplace and update the plugin in their plugin manager. A GitHub release does not publish the plugin in Claude's official marketplace.

A future official-directory submission is a separate action. Do not claim acceptance or availability there without confirmation from that directory.
