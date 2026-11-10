#!/usr/bin/env python3
"""Validate version agreement and release notes; optional argument is the tag."""
import json
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
plugin = json.loads((root / 'plugin/.claude-plugin/plugin.json').read_text())
marketplace = json.loads((root / '.claude-plugin/marketplace.json').read_text())
version = plugin['version']
assert re.fullmatch(r'\d+\.\d+\.\d+', version), 'Expected a stable X.Y.Z version'
entry, = [p for p in marketplace['plugins'] if p['name'] == plugin['name']]
assert entry['version'] == version, 'Plugin and marketplace versions differ'
assert (root / entry['source']).resolve() == root / 'plugin'
tag = 'v' + version
if len(sys.argv) > 1:
    assert sys.argv[1] == tag, f'Tag must match manifests: expected {tag}'
notes = root / 'release-notes' / f'{tag}.md'
assert notes.read_text().strip(), 'Release notes must not be empty'
print(f'Release metadata valid: {tag}')
