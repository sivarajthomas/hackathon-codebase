"""Minimal MCP client to smoke-test a running server (no LLM involved).

Connects to a Streamable-HTTP MCP server, lists its tools and calls a few of
them, printing the results. This exercises the full path:

    MCP protocol -> tool -> service -> repository -> connector -> BigQuery/GCS

Usage:
    # start a server first (in another terminal), then:
    python scripts/mcp_client_test.py --url http://127.0.0.1:8082/mcp --mode invoice
    python scripts/mcp_client_test.py --url http://127.0.0.1:8082/mcp --mode knowledge
"""

from __future__ import annotations

import argparse
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _print_result(title: str, result) -> None:
    print(f"\n--- {title} ---")
    for block in result.content:
        text = getattr(block, "text", None)
        if text is not None:
            try:
                print(json.dumps(json.loads(text), indent=2, default=str)[:1500])
            except (ValueError, TypeError):
                print(text[:1500])


async def run(url: str, mode: str) -> None:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("== Tools exposed ==")
            for tool in tools.tools:
                print(f"  {tool.name}: {tool.description or ''}")

            if mode == "invoice":
                _print_result(
                    "find_invoice",
                    await session.call_tool("find_invoice", {"invoice_id": "INV1005"}),
                )
            elif mode == "knowledge":
                _print_result(
                    "knowledge_list_folders",
                    await session.call_tool("knowledge_list_folders", {}),
                )
                _print_result(
                    "knowledge_list_files",
                    await session.call_tool("knowledge_list_files", {}),
                )


async def call_one(url: str, tool: str, args: dict) -> None:
    """Connect, optionally list tools, and call a single tool with args."""
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if tool == "list_tools":
                tools = await session.list_tools()
                print("== Tools exposed ==")
                for t in tools.tools:
                    print(f"  {t.name}: {t.description or ''}")
                return
            _print_result(f"{tool}({args})", await session.call_tool(tool, args))


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP server smoke test client.")
    parser.add_argument("--url", default="http://127.0.0.1:8082/mcp")
    parser.add_argument("--mode", choices=["invoice", "knowledge"], default="knowledge")
    parser.add_argument("--tool", help="Call a single tool by name (or 'list_tools').")
    parser.add_argument("--args", default="{}", help="JSON object of tool arguments.")
    args = parser.parse_args()
    if args.tool:
        asyncio.run(call_one(args.url, args.tool, json.loads(args.args)))
    else:
        asyncio.run(run(args.url, args.mode))


if __name__ == "__main__":
    main()
