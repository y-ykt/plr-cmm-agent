"""Tests for the Claude API backend of the orchestrator, with a fake client (no network)."""
import importlib
import os
from contextlib import contextmanager
from types import SimpleNamespace

import yaml

from agents import api_backend as a
from tests.test_inventory import CONFIG


def msg(blocks, stop="end_turn", usage=(100, 10, 0, 0)):
    i, o, cr, cc = usage
    return SimpleNamespace(content=blocks, stop_reason=stop,
                           usage=SimpleNamespace(input_tokens=i, output_tokens=o,
                                                 cache_read_input_tokens=cr, cache_creation_input_tokens=cc))


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool_use(id_, name, inp):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=inp)


class FakeClient:
    """Returns the scripted messages in order and records every request."""
    def __init__(self, script):
        self.script, self.requests = list(script), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    @contextmanager
    def _stream(self, **kw):
        self.requests.append(kw)
        m = self.script.pop(0)
        yield SimpleNamespace(get_final_message=lambda: m)


SETTINGS = {"model": "claude-opus-5-5", "effort": "high", "fallbacks": True,
            "prices": {"input": 4, "output": 20, "cache_read": 0.2, "cache_create": 5}}


def test_read_call_shape_and_cost():
    c = FakeClient([msg([text('{"files": []}')], usage=(1_000_000, 0, 0, 0))])
    out = a.read_call(c, SETTINGS, "prompt")
    assert out["result"] == '{"files": []}' and out["num_turns"] == 1 and out["total_cost_usd"] == 4.0
    kw = c.requests[0]
    assert kw["model"] == "claude-opus-5-5" and kw["output_config"] == {"effort": "high"}
    assert kw["fallbacks"] == "default" and kw["betas"] == [a.FALLBACK_BETA] and "thinking" not in kw
    assert kw["messages"] == [{"role": "user", "content": "prompt"}]


def test_read_call_without_fallbacks_and_prices():
    c = FakeClient([msg([text("x")])])
    out = a.read_call(c, {"model": "m", "fallbacks": False}, "p")
    assert "fallbacks" not in c.requests[0] and "betas" not in c.requests[0]
    assert out["total_cost_usd"] == 0.0 and out["usage"]["input_tokens"] == 100


def test_judge_call_tool_loop():
    calls = []

    def run_tool(name, args):
        calls.append((name, args))
        if name == "submit_judgment":
            raise ValueError("bad")
        return f"result of {name}"

    c = FakeClient([
        msg([tool_use("t1", "get_procedure", {}), tool_use("t2", "get_notes", {"experiment": "003"})], stop="tool_use"),
        msg([tool_use("t3", "submit_judgment", {"judgment": {}})], stop="tool_use", usage=(50, 5, 20, 0)),
        msg([text("done")]),
    ])
    out = a.judge_call(c, SETTINGS, "judge 003", tools=[{"name": "x"}], run_tool=run_tool)
    assert out["result"] == "done" and out["num_turns"] == 3 and "is_error" not in out
    assert calls == [("get_procedure", {}), ("get_notes", {"experiment": "003"}), ("submit_judgment", {"judgment": {}})]
    assert out["usage"] == {"input_tokens": 250, "output_tokens": 25, "cache_read_input_tokens": 20,
                            "cache_creation_input_tokens": 0}
    # the conversation sent on the third request: user, assistant (content unchanged), tool results, ...
    m = c.requests[2]["messages"]
    assert [x["role"] for x in m] == ["user", "assistant", "user", "assistant", "user"]
    assert m[2]["content"][0] == {"type": "tool_result", "tool_use_id": "t1", "content": "result of get_procedure"}
    assert m[4]["content"][0]["is_error"] is True and "ValueError: bad" in m[4]["content"][0]["content"]
    assert c.requests[0]["tools"] == [{"name": "x"}]


def test_judge_call_stops_at_max_turns():
    c = FakeClient([msg([tool_use("t", "get_levels", {})], stop="tool_use")] * 2)
    out = a.judge_call(c, SETTINGS, "p", tools=[], run_tool=lambda n, g: "r", max_turns=2)
    assert out["is_error"] and "stopped after 2 requests" in out["result"]


def test_tool_definitions_come_from_the_server(tmp_path):
    os.environ["PLR_CMM_RUN"] = str(tmp_path / "run")
    import plr_cmm_mcp.server as s
    s = importlib.reload(s)
    tools = a.tool_definitions(s.mcp)
    assert [t["name"] for t in tools] == list(a.JUDGE_TOOLS)
    assert tools[3]["input_schema"]["required"] == ["experiment"] and tools[3]["description"]
    run = a.tool_runner(s.mcp)
    assert run("get_levels", {}).startswith("# PLR-CMM levels")
    assert "rejected" in run("submit_judgment", {"judgment": {"experiment": "003"}})


def test_backend_is_chosen_by_the_key_in_config(tmp_path):
    raw = yaml.safe_load(open(CONFIG, encoding="utf-8"))
    key_in_file = bool(raw["llm"]["api_key"])     # the published file carries no key (the value is never printed)
    assert key_in_file is False
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    os.environ["PLR_CMM_CONFIG"] = str(cfg)
    os.environ.pop("PLR_CMM_MODEL", None)
    import agents.orchestrator as o
    o = importlib.reload(o)
    assert o.BACKEND == "claude-code" and o.MODEL == raw["llm"]["model"]
    raw["llm"]["api_key"] = "sk-test"
    cfg.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    os.environ["PLR_CMM_MODEL"] = "claude-sonnet-5-5"
    o = importlib.reload(o)
    assert o.BACKEND == "api" and o.MODEL == "claude-sonnet-5-5"
    os.environ.pop("PLR_CMM_MODEL"); os.environ.pop("PLR_CMM_CONFIG")
    importlib.reload(o)
