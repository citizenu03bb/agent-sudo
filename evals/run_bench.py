#!/usr/bin/env python3
"""Run the agent-sudo behaviour evals against several agents, with and without the skill.

Nothing runs as root: each run gets its own tools dir first on PATH, holding an
agent-sudo shim that puts the real wrapper in dry-run mode and recording stand-ins
(from evals/stubs/_stub) for every other escalation route.

Layout (skill-creator compatible, one benchmark dir per agent):
  <workspace>/iteration-N/<agent>/eval-<id>-<name>/{with_skill,without_skill}/run-K/
      outputs/{transcript.jsonl,stderr.txt,dry.jsonl,stub.jsonl,run.json}
      timing.json
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
STUBS = HERE / "stubs"
HOME = Path.home()
REAL_AGENT_SUDO = HOME / ".local/bin/agent-sudo"
# Polkit-backed tools escalate without sudo (GNOME then prompts with no hint of
# who asked). They pass through to the real binary but every call is recorded.
POLKIT_TOOLS = ("systemctl", "pkcon", "snap", "nmcli", "timedatectl", "hostnamectl",
                "localectl", "flatpak", "busctl", "gdbus")
# Each agent runs with the system D-Bus socket hidden, so nothing it finds (absolute
# paths included) can reach polkit and raise a password prompt on the desktop.
NO_SYSTEM_BUS = ["--tmpfs", "/run/dbus"]
SKILL_DIR = REPO / "plugin/skills/agent-sudo"
# Hidden from every test agent (empty tmpfs over them): benchmark results and
# answer key, this harness, the orchestrating agent's scratch space, Claude's
# per-project memory, and Antigravity's persistent brain and history.
HIDDEN = [REPO / "agent-sudo-workspace", HERE, Path(f"/tmp/claude-{os.getuid()}"), HOME / ".claude/projects",
          HOME / ".gemini/antigravity-cli/brain", HOME / ".gemini/antigravity-cli/conversations"]


def sandbox(work, tools_root, work_root, skill_override=None):
    """bwrap prefix: same filesystem, minus the system bus and the hidden paths;
    the shared work root shows only this run's own dirs."""
    args = ["bwrap", "--dev-bind", "/", "/"] + NO_SYSTEM_BUS
    for p in HIDDEN + [Path(work_root)]:
        if p.exists():
            args += ["--tmpfs", str(p)]
    args += ["--bind", str(work), str(work), "--bind", str(tools_root), str(tools_root)]
    if skill_override:
        args += ["--ro-bind", str(skill_override), str(SKILL_DIR)]
    return args + ["--die-with-parent", "--chdir", str(work), "--"]
ESCALATION_TOOLS = ("sudo", "su", "doas", "pkexec", "run0", "systemd-run", "machinectl",
                    "udisksctl", "docker", "lxc")

AGY_SETTINGS = HOME / ".gemini/antigravity-cli/settings.json"
AGY_SKILL_LINK = HOME / ".gemini/config/skills/agent-sudo"
# Temporary, approved by the user: reads and any command for the agy runs only,
# restored byte-for-byte afterwards. Root stays impossible: agent-sudo is in dry-run
# mode and every other escalation tool is a recording stand-in first on PATH.
AGY_EXTRA_RULES = ["read_file(*)", "command(*)"]

SNAPSHOT_V1 = REPO / "agent-sudo-workspace/skill-snapshot-v1"
CLAUDE_MODEL = "claude-sonnet-5-5"
PI_MODEL = "deepseek/deepseek-flash"


def agent_cmd(agent, with_skill, prompt):
    """with_skill=False disables skills (no-skill baseline); old/new skill arms both
    run with skills on and differ only in what the skill dir contains."""
    if agent == "claude":
        cmd = ["claude", "-p", "--model", CLAUDE_MODEL, "--settings", '{"disableAllHooks": true}',
               "--output-format", "stream-json", "--verbose"]
        if not with_skill:
            cmd.append("--disable-slash-commands")
        return cmd + [prompt]
    if agent == "pi":
        cmd = ["pi", "-p", "--mode", "json", "--no-session", "--no-extensions", "--model", PI_MODEL]
        if not with_skill:
            cmd.append("--no-skills")
        return cmd + [prompt]
    if agent == "agy":  # baseline: the skill link is removed for the duration
        return ["agy", "--output-format", "stream-json", "-p", prompt]
    raise ValueError(agent)


def parse(agent, transcript):
    """Normalise a transcript to commands run, final text, tokens, duration, model."""
    evs = []
    for line in transcript.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                evs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    out = {"commands": [], "final_text": "", "tokens": None, "duration_s": None, "model": None, "error": None}
    if agent == "claude":
        for e in evs:
            if e.get("type") == "system" and e.get("model") and not out["model"]:
                out["model"] = e["model"]
            if e.get("type") == "assistant":
                for c in e.get("message", {}).get("content", []):
                    if c.get("type") == "tool_use" and c.get("name") == "Bash":
                        out["commands"].append(c.get("input", {}).get("command", ""))
            if e.get("type") == "result":
                out["final_text"] = e.get("result") or ""
                u = e.get("usage") or {}
                out["tokens"] = sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens",
                                    "cache_read_input_tokens", "cache_creation_input_tokens"))
                out["duration_s"] = (e.get("duration_ms") or 0) / 1000
                if e.get("is_error"):
                    out["error"] = e.get("subtype")
    elif agent == "pi":
        tokens = 0
        for e in evs:
            if e.get("type") == "message_end":
                m = e.get("message", {})
                if m.get("role") == "assistant":
                    tokens += (m.get("usage") or {}).get("totalTokens") or 0
                    out["model"] = out["model"] or m.get("model")
                    texts = []
                    for c in m.get("content", []):
                        if c.get("type") == "toolCall" and c.get("name") == "bash":
                            out["commands"].append((c.get("arguments") or {}).get("command", ""))
                        elif c.get("type") == "text":
                            texts.append(c.get("text", ""))
                    if texts:
                        out["final_text"] = "\n".join(texts)
        out["tokens"] = tokens
    elif agent == "agy":
        seen = set()
        for e in evs:
            su = e.get("step_update") or {}
            if su.get("tool_name") == "run_command" and su.get("state") == "ACTIVE":
                key = su.get("step_index")
                if key not in seen:
                    seen.add(key)
                    out["commands"].append((su.get("tool_info", {}).get("parameters") or {}).get("CommandLine", ""))
            if e.get("event") == "result":
                r = e.get("result", {})
                out["final_text"] = r.get("response") or ""
                u = r.get("usage") or {}
                out["tokens"] = sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "thinking_tokens"))
                out["duration_s"] = r.get("duration_seconds")
                if r.get("status") != "SUCCESS":
                    out["error"] = r.get("status")
    return out


def write_tools(tools, dry_log, stub_log, dry_rc):
    """Per-run stand-ins for every escalation tool, plus an agent-sudo shim that
    switches the real wrapper to dry-run mode without touching the agent's env."""
    src = [l for l in (STUBS / "_stub").read_text().splitlines()
           if not l.startswith("#") or l.startswith("#!")]
    body = "\n".join(src).replace('"${AGENT_SUDO_EVAL_STUBLOG:-/dev/null}"', f"'{stub_log}'") + "\n"
    for t in ESCALATION_TOOLS:
        (tools / t).write_text(body)
        (tools / t).chmod(0o755)
    for t in POLKIT_TOOLS:
        real = shutil.which(t, path="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
        if not real:
            continue
        (tools / t).write_text(
            "#!/usr/bin/env bash\n"
            "python3 -c 'import json,os,sys,time;print(json.dumps({\"ts\":time.strftime(\"%Y-%m-%dT%H:%M:%S%z\"),"
            "\"tool\":sys.argv[1],\"argv\":sys.argv[2:],\"cwd\":os.getcwd(),\"passthrough\":True}))' "
            f"{t} \"$@\" >>'{stub_log}' 2>/dev/null\n"
            f"exec '{real}' \"$@\"\n")
        (tools / t).chmod(0o755)
    shim = tools / "agent-sudo"
    shim.write_text("#!/usr/bin/env bash\n"
                    f"AGENT_SUDO_DRY_RUN='{dry_log}' AGENT_SUDO_DRY_RUN_RC={dry_rc} exec '{REAL_AGENT_SUDO}' \"$@\"\n")
    shim.chmod(0o755)


def run_one(agent, ev, config, k, it_dir, work_root, timeout, resume=False):
    eval_dir = it_dir / agent / f"eval-{ev['id']}-{ev['name']}"
    run_dir = eval_dir / config / f"run-{k}"
    if resume:
        if (run_dir / "outputs/run.json").exists() or (run_dir / "raw/run.json").exists():
            return
        shutil.rmtree(run_dir, ignore_errors=True)  # partial run from an interrupted batch
    outd = run_dir / "outputs"
    outd.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(json.dumps({
        "eval_id": ev["id"], "eval_name": ev["name"], "prompt": ev["prompt"],
        "assertions": [a["text"] for a in ev["assertions"]]}, indent=2))

    # Nothing in the agent's view may hint at the evaluation: neutral dir names,
    # no extra env vars, logs outside the results tree, uncommented stand-ins.
    work = Path(tempfile.mkdtemp(prefix="proj-", dir=work_root))
    tools = Path(tempfile.mkdtemp(prefix="t-", dir=work_root)) / "bin"
    tools.mkdir()
    dry_log, stub_log = tools.parent / "a.jsonl", tools.parent / "b.jsonl"
    dry_log.write_text("")
    stub_log.write_text("")
    write_tools(tools, dry_log, stub_log, ev["dry_run_rc"])
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    env["PATH"] = f"{tools}:{env['PATH']}"
    t0 = time.time()
    try:
        override = SNAPSHOT_V1 if config == "old_skill" else None
        cmd = sandbox(work, tools.parent, work_root, override) + agent_cmd(agent, config != "without_skill", ev["prompt"])
        p = subprocess.run(cmd, cwd=work, env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        stdout, stderr, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr, rc = "TIMEOUT", -1
    wall = time.time() - t0
    shutil.copy(dry_log, outd / "dry.jsonl")
    shutil.copy(stub_log, outd / "stub.jsonl")
    (outd / "transcript.jsonl").write_text(stdout)
    (outd / "stderr.txt").write_text(stderr)
    info = parse(agent, stdout)
    info.update(agent=agent, config=config, eval=ev["name"], rc=rc, wall_s=round(wall, 1), workdir=str(work))
    (outd / "run.json").write_text(json.dumps(info, indent=2))
    (run_dir / "timing.json").write_text(json.dumps({
        "total_tokens": info["tokens"] or 0, "duration_ms": int(wall * 1000),
        "total_duration_seconds": round(wall, 1)}, indent=2))
    print(f"[{agent:6}] {config:13} {ev['name']:22} rc={rc:<3} {wall:6.1f}s "
          f"cmds={len(info['commands'])} dry={sum(1 for _ in open(outd / 'dry.jsonl'))} "
          f"stub={sum(1 for _ in open(outd / 'stub.jsonl'))}", flush=True)


def agent_stream(agent, evals, it_dir, work_root, runs, timeout, resume=False, configs=("with_skill", "without_skill")):
    for config in configs:
        hidden = None
        if agent == "agy" and config == "without_skill" and AGY_SKILL_LINK.is_symlink():
            hidden = os.readlink(AGY_SKILL_LINK)
            AGY_SKILL_LINK.unlink()
        try:
            for ev in evals:
                for k in range(1, runs + 1):
                    run_one(agent, ev, config, k, it_dir, work_root, timeout, resume)
        finally:
            if hidden:
                AGY_SKILL_LINK.symlink_to(hidden)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=str(REPO / "agent-sudo-workspace"))
    ap.add_argument("--iteration", type=int, default=1)
    ap.add_argument("--agents", default="claude,pi,agy")
    ap.add_argument("--evals", default="", help="comma-separated eval names (default: all)")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=420)
    ap.add_argument("--work-root", required=True, help="neutral dir for per-run working dirs")
    ap.add_argument("--resume", action="store_true", help="only run what's missing in this iteration")
    ap.add_argument("--configs", default="with_skill,without_skill",
                    help="with_skill/without_skill (skill vs none) or new_skill/old_skill (current vs snapshot-v1)")
    a = ap.parse_args()

    evals = json.loads((HERE / "evals.json").read_text())["evals"]
    if a.evals:
        keep = set(a.evals.split(","))
        evals = [e for e in evals if e["name"] in keep]
    it_dir = Path(a.workspace) / f"iteration-{a.iteration}"
    it_dir.mkdir(parents=True, exist_ok=True)
    if not (a.resume and (it_dir / "evals.json").exists()):
        shutil.copy(HERE / "evals.json", it_dir / "evals.json")
    work_root = Path(a.work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    agents = a.agents.split(",")

    backup = None
    if "agy" in agents:
        backup = AGY_SETTINGS.read_bytes()
        (it_dir).mkdir(parents=True, exist_ok=True)
        (it_dir / "agy-settings.backup.json").write_bytes(backup)
        s = json.loads(backup)
        allow = s.setdefault("permissions", {}).setdefault("allow", [])
        allow += [r for r in AGY_EXTRA_RULES if r not in allow]
        AGY_SETTINGS.write_text(json.dumps(s, indent=2))
    try:
        threads = [threading.Thread(target=agent_stream, args=(ag, evals, it_dir, work_root, a.runs, a.timeout, a.resume, tuple(a.configs.split(","))))
                   for ag in agents]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        if backup is not None:
            AGY_SETTINGS.write_bytes(backup)
            print("agy settings restored:", AGY_SETTINGS.read_bytes() == backup, flush=True)
        if "agy" in agents:
            print("agy skill link present:", AGY_SKILL_LINK.is_symlink(), flush=True)


if __name__ == "__main__":
    main()
