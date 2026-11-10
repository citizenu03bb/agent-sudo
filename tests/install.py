#!/usr/bin/env python3
"""Install into throwaway destinations; never change the real home directory."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    home = Path(temp)
    def install(*args, ok=True):
        result = subprocess.run([str(root / 'install.sh'), '--home', str(home), *args], capture_output=True, text=True)
        assert (result.returncode == 0) == ok, result.stdout + result.stderr
        return result
    (home / '.claude').mkdir()
    install()
    link = home / '.claude/skills/agent-sudo'
    assert link.resolve() == root / 'plugin/skills/agent-sudo'
    assert (home / '.local/bin/agent-sudo').resolve() == root / 'plugin/skills/agent-sudo/scripts/agent-sudo'
    install('--agent', 'codex', '--agent', 'pi', '--agent', 'antigravity')
    for directory in ('.codex/skills', '.pi/agent/skills', '.gemini/config/skills'):
        assert (home / directory / 'agent-sudo').resolve() == link.resolve()
    install()  # idempotent; no nested symlink inside the source skill
    assert not (root / 'plugin/skills/agent-sudo/agent-sudo').exists()
    link.unlink()
    link.mkdir()
    (link / 'keep').write_text('do not overwrite')
    install(ok=False)
    assert (link / 'keep').read_text() == 'do not overwrite'
    install('--agent', 'unknown', ok=False)
print('Installer checks passed: detection, explicit agents, repeat install, conflict protection')
