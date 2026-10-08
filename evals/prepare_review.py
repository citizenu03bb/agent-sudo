#!/usr/bin/env python3
"""Make benchmark runs readable in skill-creator's eval viewer.

For each run: move raw files (transcript, stderr, logs, run.json) from outputs/ to
raw/, write outputs/summary.md for the human reviewer, and copy eval_metadata.json
next to each config dir so the viewer shows the prompt.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade import is_bypass  # noqa: E402

RAW = ("transcript.jsonl", "stderr.txt", "dry.jsonl", "stub.jsonl", "run.json")


def jl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def main():
    it = Path(sys.argv[1])
    for run_dir in sorted(p.parent for p in it.glob("*/eval-*/*/run-*/outputs")):
        out, raw = run_dir / "outputs", run_dir / "raw"
        raw.mkdir(exist_ok=True)
        for f in RAW:
            if (out / f).exists():
                shutil.move(str(out / f), raw / f)
        meta = run_dir.parent.parent / "eval_metadata.json"
        if meta.exists():
            shutil.copy(meta, run_dir.parent / "eval_metadata.json")
        run = json.loads((raw / "run.json").read_text())
        dry, stub = jl(raw / "dry.jsonl"), jl(raw / "stub.jsonl")
        md = [f"# {run['agent']} · {run['config']} · {run['eval']}",
              f"model `{run.get('model')}` · exit {run['rc']} · {run['wall_s']} s · tokens {run.get('tokens')}", "",
              f"## agent-sudo requests ({len(dry)})"]
        for r in dry:
            md += [f"- **reason:** {r['reason']!r} → answered `{r['answer_rc']}`",
                   "  ```", "  " + " ".join(r["argv"]).replace("\n", "\n  ")]
            if r.get("stdin"):
                md += ["  --- stdin ---", "  " + r["stdin"].rstrip().replace("\n", "\n  ")]
            md += ["  ```"]
        bypass = [s for s in stub if is_bypass(s)]
        harmless = [s for s in stub if not is_bypass(s)]
        md += ["", f"## Direct escalation attempts ({len(bypass)})"]
        md += [f"- `{s['tool']} {' '.join(s['argv'])}`" for s in bypass] or ["- none"]
        if harmless:
            md += ["", f"<details><summary>Read-only polkit-tool calls ({len(harmless)}, not counted)</summary>", ""]
            md += [f"- `{s['tool']} {' '.join(s['argv'])}`" for s in harmless] + ["", "</details>"]
        md += ["", f"## Commands run ({len(run['commands'])})"]
        md += [f"{i + 1}. `{c.strip().splitlines()[0][:200] if c.strip() else ''}`"
               + (" …" if len(c.strip().splitlines()) > 1 else "") for i, c in enumerate(run["commands"])]
        md += ["", "## Final answer", "", run.get("final_text") or "_(none)_"]
        if run.get("error"):
            md += ["", f"**error:** {run['error']}"]
        (out / "summary.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
