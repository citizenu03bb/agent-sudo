# Releasing

The plugin is distributed through this repository's custom marketplace and is not listed in Claude's official marketplace.

## Prepare

1. Set the same stable `X.Y.Z` version in `plugin/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
2. Add `release-notes/vX.Y.Z.md`, describing behavior changes, compatibility and update instructions.
3. Commit and push to `main`. Wait for CI: release metadata, shell syntax, installation, functional tests and real Zenity layout tests on Ubuntu 22.04 and 24.04.

## Publish

Tag the intended commit explicitly and push that tag. For example:

```bash
git tag -a v0.5.0 -m 'agent-sudo 0.5.0'
git push origin v0.5.0
```

The **Release** workflow runs the full CI suite on the tagged commit, verifies that the tag matches both manifests and that release notes exist, then publishes a GitHub release using those notes. Only the publish job has repository write permission. No personal token or manual `gh release create` is needed.

Ordinary branch pushes do not publish releases. Failed tests or mismatched metadata prevent publication. Never move a published tag; prepare a new version for corrections. If infrastructure fails before publication, rerun the failed workflow. An existing release is not overwritten.

Publishing a GitHub release does not submit or publish the plugin in Claude's official directory.

## User updates

Clone users run `git pull --ff-only`. Skills CLI users can use `npx skills update`. Claude Code users refresh this repository's custom marketplace and update the plugin through its plugin manager. Start a new agent session to reload skill instructions.
