"""Calling the model through the Claude API (python package anthropic) instead of claude -p.

Used by agents/orchestrator.py when config.yaml has llm.api_key. Both calls return the same
shape as claude_call in the orchestrator: {"result": text, "usage": {...}, "num_turns": n,
"total_cost_usd": x, "_elapsed": seconds}, so the orchestrator records and prints them alike.

Stage 1 (read)  : read_call  - one request, the notes JSON comes back as text.
Stage 2 (judge) : judge_call - the plr-cmm tools of plr_cmm_mcp/server.py are given to the model
                  as API tools and run in this process (no MCP server process); the loop
                  continues while the model calls tools, up to max_turns requests.

The usage of every request is accumulated. The API returns token counts, not a price; the cost
is computed from llm.prices in config.yaml when it is given, otherwise it is recorded as 0.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable

MAX_TOKENS = 16_000
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# The tools of the judging stage, in the order agents/prompts/judge.md names them.
JUDGE_TOOLS = ("get_procedure", "get_capabilities", "get_levels", "get_notes", "get_premise",
               "judgment_schema", "submit_judgment", "render_judgment")


def make_client(api_key: str):
    try:
        import anthropic
    except ImportError as ex:
        raise RuntimeError("llm.api_key is set in config.yaml but the package anthropic is not installed: "
                           "pip install anthropic") from ex
    for name in ("httpx2", "httpx", "anthropic"):   # the MCP server sets the root logger to INFO; keep
        logging.getLogger(name).setLevel(logging.WARNING)   # the one-line-per-request HTTP log out of the output
    return anthropic.Anthropic(api_key=api_key)


def _request_kwargs(settings: dict) -> dict:
    kw: dict[str, Any] = {"model": settings["model"], "max_tokens": MAX_TOKENS,
                          "output_config": {"effort": settings.get("effort", "high")}}
    if settings.get("fallbacks", True):
        kw["betas"] = [FALLBACK_BETA]
        kw["fallbacks"] = "default"
    return kw


def _usage_add(total: dict, usage) -> None:
    total["input_tokens"] += getattr(usage, "input_tokens", 0) or 0
    total["output_tokens"] += getattr(usage, "output_tokens", 0) or 0
    total["cache_read_input_tokens"] += getattr(usage, "cache_read_input_tokens", 0) or 0
    total["cache_creation_input_tokens"] += getattr(usage, "cache_creation_input_tokens", 0) or 0


def cost_usd(usage: dict, prices: dict | None) -> float:
    """USD from token counts and a price table in USD per million tokens
    ({input, output, cache_read, cache_create}); 0 when there is no table."""
    if not prices:
        return 0.0
    per = {"input_tokens": "input", "output_tokens": "output",
           "cache_read_input_tokens": "cache_read", "cache_creation_input_tokens": "cache_create"}
    return sum(usage.get(k, 0) * float(prices.get(v, 0)) for k, v in per.items()) / 1_000_000


def _text_of(message) -> str:
    return "".join(b.text for b in message.content if getattr(b, "type", "") == "text")


def _send(client, kw: dict):
    """One request; streaming, so that long inputs and outputs do not hit the HTTP timeout."""
    with client.beta.messages.stream(**kw) as stream:
        return stream.get_final_message()


def _finish(message, usage: dict, turns: int, prices: dict | None, t0: float) -> dict:
    out = {"result": _text_of(message), "stop_reason": getattr(message, "stop_reason", None),
           "usage": usage, "num_turns": turns, "total_cost_usd": cost_usd(usage, prices),
           "_elapsed": time.time() - t0}
    if out["stop_reason"] == "refusal":
        out["is_error"] = True
    return out


def read_call(client, settings: dict, prompt: str) -> dict:
    """Stage 1: one request, the result text holds the notes JSON."""
    t0 = time.time()
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    kw = _request_kwargs(settings)
    kw["messages"] = [{"role": "user", "content": prompt}]
    msg = _send(client, kw)
    _usage_add(usage, msg.usage)
    return _finish(msg, usage, 1, settings.get("prices"), t0)


def tool_definitions(server_mcp, names: tuple[str, ...] = JUDGE_TOOLS) -> list[dict]:
    """The API tool definitions of the named plr-cmm tools, taken from the MCP server itself
    (name, description, input schema), so that they are not written twice."""
    tools = {t.name: t for t in asyncio.run(server_mcp.list_tools())}
    missing = [n for n in names if n not in tools]
    if missing:
        raise RuntimeError(f"tools not found in the MCP server: {missing}")
    return [{"name": n, "description": tools[n].description or "", "input_schema": tools[n].input_schema}
            for n in names]


def tool_runner(server_mcp) -> Callable[[str, dict], str]:
    """Runs one plr-cmm tool in this process and returns its result as text."""
    def run(name: str, args: dict) -> str:
        result = asyncio.run(server_mcp.call_tool(name, args))
        content = result[0] if isinstance(result, tuple) else getattr(result, "content", result)
        parts = []
        for block in content or []:
            text = getattr(block, "text", None)
            parts.append(text if text is not None else json.dumps(block if isinstance(block, dict) else str(block),
                                                                   ensure_ascii=False))
        return "\n".join(parts)
    return run


def judge_call(client, settings: dict, prompt: str, tools: list[dict], run_tool: Callable[[str, dict], str],
               max_turns: int = 40) -> dict:
    """Stage 2: the model judges with the plr-cmm tools; loop until it stops calling tools."""
    t0 = time.time()
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    messages: list[dict] = [{"role": "user", "content": prompt}]
    kw = _request_kwargs(settings)
    kw["tools"] = tools
    msg = None
    for turn in range(1, max_turns + 1):
        kw["messages"] = messages
        msg = _send(client, kw)
        _usage_add(usage, msg.usage)
        if msg.stop_reason != "tool_use":
            return _finish(msg, usage, turn, settings.get("prices"), t0)
        messages.append({"role": "assistant", "content": msg.content})   # thinking blocks go back unchanged
        results = []
        for block in msg.content:
            if getattr(block, "type", "") != "tool_use":
                continue
            try:
                text, is_error = run_tool(block.name, dict(block.input)), False
            except Exception as ex:                                       # the tool's error goes back to the model
                text, is_error = f"{type(ex).__name__}: {ex}", True
            item = {"type": "tool_result", "tool_use_id": block.id, "content": text}
            if is_error:
                item["is_error"] = True
            results.append(item)
        messages.append({"role": "user", "content": results})
    out = _finish(msg, usage, max_turns, settings.get("prices"), t0)
    out["is_error"] = True
    out["result"] = f"stopped after {max_turns} requests while the model was still calling tools"
    return out
