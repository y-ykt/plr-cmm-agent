"""Manual check: start the server over stdio and list its tools (not run by pytest)."""
import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


async def main() -> None:
    env = dict(os.environ, PLR_CMM_ROOT=str(ROOT), PLR_CMM_RUN=str(ROOT / "runs" / "dev"),
               PLR_CMM_CONDITION="full")
    params = StdioServerParameters(command=sys.executable, args=["-m", "plr_cmm_mcp.server"],
                                   env=env, cwd=str(ROOT))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("tools:", [t.name for t in tools.tools])
            res = await s.list_resources()
            print("resources:", [str(x.uri) for x in res.resources])
            pr = await s.list_prompts()
            print("prompts:", [p.name for p in pr.prompts])
            out = await s.call_tool("get_levels", {})
            print("get_levels ->", out.content[0].text[:60].replace("\n", " "))


asyncio.run(main())
