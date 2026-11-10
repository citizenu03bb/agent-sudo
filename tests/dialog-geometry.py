#!/usr/bin/env python3
"""Real Zenity layout regression checks, no sudo and no password entry.
Run: xvfb-run -a -s '-screen 0 800x600x24' python3 tests/dialog-geometry.py
Requires zenity, Xvfb, xwininfo. Use an isolated X display, never your desktop.
"""
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

helper = Path(__file__).resolve().parents[1] / 'plugin/skills/agent-sudo/scripts/agent-sudo-dialog'
root_info = subprocess.check_output(['xwininfo', '-root'], text=True)
width = int(re.search(r'Width: (\d+)', root_info)[1])
height = int(re.search(r'Height: (\d+)', root_info)[1])
cases = [
    ('short', 'askpass', 'id -u', 'audit', 'Codex', '/tmp', False),
    ('long-command', 'askpass', 'echo ' + 'W' * 1200, 'audit', 'Codex', '/tmp', True),
    ('long-review', 'review', 'echo ' + 'W' * 1200, 'audit', 'Codex', '/tmp', True),
    ('long-reason', 'askpass', 'id -u', 'W' * 4000, 'Codex', '/tmp', True),
    ('multiline-reason', 'review', 'id -u', 'because\n' * 100, 'Codex', '/tmp', True),
    ('long-agent', 'askpass', 'id -u', 'audit', 'W' * 4000, '/tmp', True),
    ('long-cwd', 'askpass', 'id -u', 'audit', 'Codex', '/' + 'W' * 1000, True),
    ('unicode', 'askpass', 'echo ' + '界' * 400, 'audit', 'Codex', '/tmp', True),
    ('password-after-review', 'password', 'echo ' + 'W' * 1200, 'W' * 4000, 'W' * 4000, '/tmp', False),
]
for name, mode, command, reason, agent, cwd, scroll in cases:
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        (work / 'review').write_text(command + '\n')
        (work / 'status').touch()
        env = dict(os.environ, GDK_BACKEND='x11', AGENT_SUDO_MODE=mode,
                   AGENT_SUDO_REVIEW=str(work / 'review'), AGENT_SUDO_STATUS=str(work / 'status'),
                   AGENT_SUDO_REASON=reason, AGENT_SUDO_AGENT=agent,
                   AGENT_SUDO_CWD=cwd, AGENT_SUDO_TIMEOUT='8')
        with subprocess.Popen([str(helper)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True) as process:
            try:
                geometry = None
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and process.poll() is None:
                    tree = subprocess.check_output(['xwininfo', '-root', '-tree'], text=True)
                    geometry = re.search(r'"agent-sudo:[^\n]+?\s(\d+)x(\d+)\+', tree)
                    if geometry and min(map(int, geometry.groups())) > 100:
                        time.sleep(.15)
                        tree = subprocess.check_output(['xwininfo', '-root', '-tree'], text=True)
                        geometry = re.search(r'"agent-sudo:[^\n]+?\s(\d+)x(\d+)\+', tree)
                        break
                    time.sleep(.05)
                assert geometry, f'{name}: no dialog appeared'
                w, h = map(int, geometry.groups())
                assert w > 100 and h > 100, f'{name}: window did not finish mapping'
                assert w <= width and h <= height, f'{name}: {w}x{h} exceeds {width}x{height}'
                assert (work / 'page').exists() == scroll, f'{name}: wrong review path'
                if scroll:
                    page = (work / 'page').read_text()
                    for value in (command, reason, agent, cwd):
                        assert value in page, f'{name}: review text was truncated'
                process.communicate(timeout=20)
                assert process.returncode != 0, f'{name}: timeout unexpectedly approved'
                assert 'approved' not in (work / 'status').read_text()
                print(f'PASS {name}: {w}x{h}', flush=True)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
print(f'{len(cases)} geometry checks passed on {width}x{height}')
