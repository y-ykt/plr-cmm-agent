"""Orchestrator: runs the reading stage and the judging stage over many studies.

The model is called through Claude Code (claude -p), or through the Claude API when config.yaml
has llm.api_key (agents/api_backend.py).

Stage 1 (read)  : one call per batch of record files (about 60k chars) -> notes JSON
                  per file (runs/<run>/notes/<study>/<file>.json)
Stage 2 (judge) : one call per study with the plr-cmm tools (claude -p: the MCP server
                  as a separate process; API: the same tools run in this process);
                  the agent submits its judgment through submit_judgment, which validates it

A study is named by its identifier, the name of its records folder (the extracted text is under
work/text/<identifier>/, written by plr_cmm_mcp.extract), or by the path of that folder.

Usage:
  .venv/bin/python -m agents.orchestrator read  --run r1 --experiments <folder> <folder> ...
  .venv/bin/python -m agents.orchestrator judge --run r1 --condition full --experiments <folder> ...
Notes are shared between runs: judge --notes-from r1 reuses r1's notes.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plr_cmm_mcp import config  # noqa: E402
from plr_cmm_mcp.ids import check_study_id  # noqa: E402
from plr_cmm_mcp.judge import load_json_text  # noqa: E402

LLM = dict(config.load().get("llm") or {})
LLM["model"] = os.environ.get("PLR_CMM_MODEL", LLM.get("model") or "claude-opus-5-5")
MODEL = LLM["model"]
BACKEND = "api" if LLM.get("api_key") else "claude-code"
PY = sys.executable          # the MCP server runs with the same interpreter as this script


def claude_call(prompt: str, stdin_text: str | None = None, mcp_config: Path | None = None,
                allowed_tools: str | None = None, max_turns: int = 30, timeout: int = 1200) -> dict:
    """Run claude -p and return the JSON result (result text + usage)."""
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("the Claude Code command 'claude' was not found in PATH")
    cmd = [claude, "-p", prompt, "--model", MODEL, "--output-format", "json",
           "--max-turns", str(max_turns)]
    if mcp_config:
        cmd += ["--mcp-config", str(mcp_config), "--strict-mcp-config"]
    if allowed_tools:
        cmd += ["--allowedTools", allowed_tools]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    t0 = time.time()
    try:
        cp = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True, env=env,
                            cwd=str(ROOT), timeout=timeout)
    except subprocess.TimeoutExpired as ex:
        raise RuntimeError(f"claude did not finish within {timeout} seconds") from ex
    elapsed = time.time() - t0
    if cp.returncode != 0 and not cp.stdout.strip():
        raise RuntimeError(f"claude failed ({cp.returncode}): {cp.stderr[-800:]}")
    try:
        out = json.loads(cp.stdout)
    except json.JSONDecodeError:
        out = {"result": cp.stdout, "is_error": True, "stderr": cp.stderr[-800:]}
    out["_elapsed"] = elapsed
    return out


def llm_call(prompt: str, stage: str, max_turns: int, mcp_config: Path | None = None) -> dict:
    """Call the model for one stage through the configured backend."""
    if BACKEND == "claude-code":
        if stage == "judge":
            return claude_call(prompt, mcp_config=mcp_config, allowed_tools="mcp__plr-cmm__*", max_turns=max_turns)
        return claude_call(prompt, max_turns=max_turns)
    from agents import api_backend
    client = make_api_client()
    if stage == "judge":
        import plr_cmm_mcp.server as server     # imported after the run's environment is set
        tools = api_backend.tool_definitions(server.mcp)
        return api_backend.judge_call(client, LLM, prompt, tools, api_backend.tool_runner(server.mcp),
                                      max_turns=max_turns)
    return api_backend.read_call(client, LLM, prompt)


_API_CLIENT = None


def make_api_client():
    global _API_CLIENT
    if _API_CLIENT is None:
        from agents import api_backend
        _API_CLIENT = api_backend.make_client(LLM["api_key"])
    return _API_CLIENT


def usage_of(out: dict) -> dict:
    u = out.get("usage", {}) or {}
    return {"input": u.get("input_tokens", 0), "output": u.get("output_tokens", 0),
            "cache_read": u.get("cache_read_input_tokens", 0),
            "cache_create": u.get("cache_creation_input_tokens", 0),
            "cost_usd": out.get("total_cost_usd", 0.0), "turns": out.get("num_turns", 0),
            "elapsed": round(out.get("_elapsed", 0.0), 1)}


def run_dir(run: str) -> Path:
    d = ROOT / "runs" / run
    d.mkdir(parents=True, exist_ok=True)
    return d


def append_log(run: str, rec: dict) -> None:
    with open(run_dir(run) / "calls.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ stage 1

BATCH_CHARS = int(os.environ.get("PLR_CMM_BATCH_CHARS", "60000"))


def batches(files: list[Path], limit: int = BATCH_CHARS) -> list[list[tuple[Path, str]]]:
    """Group files in order so that each batch holds at most `limit` characters
    (a single file larger than the limit forms a batch of its own)."""
    out: list[list[tuple[Path, str]]] = []
    cur: list[tuple[Path, str]] = []
    size = 0
    for p in files:
        text = p.read_text(encoding="utf-8")
        if cur and size + len(text) > limit:
            out.append(cur)
            cur, size = [], 0
        cur.append((p, text))
        size += len(text)
    if cur:
        out.append(cur)
    return out


def stage_read(run: str, experiments: list[str], work: Path) -> None:
    prompt = (ROOT / "agents" / "prompts" / "reader.md").read_text(encoding="utf-8")
    for exp in experiments:
        src = work / "text" / exp
        if not src.exists():
            print(f"[read] {exp}: no extracted text", flush=True)
            continue
        out_dir = run_dir(run) / "notes" / exp
        out_dir.mkdir(parents=True, exist_ok=True)
        todo = [p for p in sorted(src.glob("*.txt")) if not (out_dir / (p.stem + ".json")).exists()]
        for bi, batch in enumerate(batches(todo), 1):
            body = "\n\n".join(f"## File: {p.name}\n\n{text}" for p, text in batch)
            msg = f"{prompt}\n\n---\nStudy: {exp}\nFiles: {len(batch)}\n\n{body}"
            try:
                res = llm_call(msg, "read", max_turns=1)
            except RuntimeError as ex:          # claude missing, failed or timed out: record and go on
                append_log(run, {"stage": "read", "backend": BACKEND, "model": MODEL, "experiment": exp,
                                 "batch": bi, "error": str(ex)[:300]})
                print(f"[read] {exp} batch {bi} ERROR {str(ex)[:120]}", flush=True)
                continue
            u = usage_of(res)
            rec = {"stage": "read", "backend": BACKEND, "model": MODEL, "experiment": exp, "batch": bi,
                   "files": [p.name for p, _ in batch], "chars": sum(len(t) for _, t in batch), **u}
            try:
                obj = load_json_text(res.get("result", ""))
                items = obj.get("files", [])
                by_name = {it.get("file"): it for it in items}
                saved = 0
                for i, (p, _) in enumerate(batch):
                    it = by_name.get(p.name) or (items[i] if i < len(items) else None)
                    if it is None:
                        continue
                    it["file"] = p.name
                    (out_dir / (p.stem + ".json")).write_text(json.dumps(it, ensure_ascii=False, indent=1),
                                                              encoding="utf-8")
                    saved += 1
                rec["saved"] = saved
                rec["notes"] = sum(len(it.get("notes", [])) for it in items)
            except (ValueError, json.JSONDecodeError) as ex:
                rec["error"] = str(ex)[:200]
                (out_dir / f"batch{bi}.err.txt").write_text(res.get("result", ""), encoding="utf-8")
            append_log(run, rec)
            print(f"[read] {exp} batch {bi} files={len(batch)} chars={rec['chars']:,} "
                  f"in={u['input'] + u['cache_create'] + u['cache_read']:>7} out={u['output']:>5} "
                  f"${u['cost_usd']:.3f} {u['elapsed']}s saved={rec.get('saved', '-')} "
                  f"notes={rec.get('notes', '-')}", flush=True)


# ------------------------------------------------------------------ stage 2

def mcp_env(run: str, condition: str) -> dict[str, str]:
    """The environment of the plr-cmm server for one run."""
    return {"PLR_CMM_ROOT": str(ROOT), "PLR_CMM_RUN": str(run_dir(run)),
            "PLR_CMM_CONDITION": condition, "PLR_CMM_WORK": str(ROOT / "work"),
            "PLR_CMM_CONFIG": str(config.config_path().resolve())}   # the same config.yaml as this process


def write_mcp_config(run: str, condition: str) -> Path:
    """The MCP config for one run. Notes are read from <run>/notes, which stage_judge links to
    the run they were written in when --notes-from names another run."""
    cfg = {"mcpServers": {"plr-cmm": {
        "command": PY, "args": ["-m", "plr_cmm_mcp.server"], "env": mcp_env(run, condition)}}}
    p = run_dir(run) / "mcp.json"
    p.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    return p


def stage_judge(run: str, condition: str, experiments: list[str], notes_from: str) -> None:
    prompt = (ROOT / "agents" / "prompts" / "judge.md").read_text(encoding="utf-8")
    if notes_from != run:
        link = run_dir(run) / "notes"
        if not link.exists():
            link.symlink_to(run_dir(notes_from) / "notes")
    cfg = write_mcp_config(run, condition)
    (run_dir(run) / "condition.txt").write_text(condition, encoding="utf-8")
    if BACKEND == "api":                       # the tools run in this process under the run's environment
        for k, v in mcp_env(run, condition).items():
            os.environ[k] = v
    for exp in experiments:
        out = run_dir(run) / "judgments" / f"{exp}.json"
        if out.exists():
            continue
        msg = f"{prompt}\n\nStudy to judge: {exp}\n"
        try:
            res = llm_call(msg, "judge", max_turns=40, mcp_config=cfg)
        except RuntimeError as ex:              # record the failure; the run can be resumed later
            append_log(run, {"stage": "judge", "backend": BACKEND, "model": MODEL, "condition": condition,
                             "experiment": exp, "error": str(ex)[:300]})
            print(f"[judge] {exp} ERROR {str(ex)[:120]}", flush=True)
            continue
        u = usage_of(res)
        rec = {"stage": "judge", "backend": BACKEND, "model": MODEL, "condition": condition, "experiment": exp, **u,
               "accepted": out.exists(), "final": (res.get("result") or "")[:200]}
        append_log(run, rec)
        print(f"[judge] {exp} in={u['input']} cache={u['cache_read']} out={u['output']} "
              f"${u['cost_usd']:.3f} turns={u['turns']} {u['elapsed']}s accepted={rec['accepted']}", flush=True)


def study_ids(values: list[str]) -> list[str]:
    """The identifiers of the studies named on the command line: each value is the identifier itself
    (the name of the records folder) or the path of that folder, whose last component is taken.
    Duplicates are dropped; anything that is not a plain folder name is refused."""
    out: list[str] = []
    for v in values:
        sid = check_study_id(Path(v.rstrip("/")).name if "/" in v else v)
        if sid not in out:
            out.append(sid)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    exp_help = "the studies: the identifier (the name of the records folder) or the path of that folder"
    a = sub.add_parser("read"); a.add_argument("--run", required=True)
    a.add_argument("--experiments", nargs="+", required=True, help=exp_help); a.add_argument("--work", default="work")
    b = sub.add_parser("judge"); b.add_argument("--run", required=True)
    b.add_argument("--condition", choices=["full", "names"], default="full")
    b.add_argument("--experiments", nargs="+", required=True, help=exp_help); b.add_argument("--notes-from")
    args = ap.parse_args()
    try:
        studies = study_ids(args.experiments)
    except ValueError as ex:
        ap.error(str(ex))
    if args.cmd == "read":
        stage_read(args.run, studies, ROOT / args.work)
    else:
        stage_judge(args.run, args.condition, studies, args.notes_from or args.run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
