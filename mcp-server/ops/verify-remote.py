"""Exercise the public endpoint with the official MCP client; never print secrets."""
import asyncio
import argparse
import json
from pathlib import Path
import time

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--connection", type=Path, default=root / "private/connection.json")
args = parser.parse_args()
connection = json.loads(args.connection.read_text(encoding="utf-8"))


def payload(result):
    return result.structured_content or json.loads(next(block.text for block in result.content if block.type == "text"))


async def main():
    async with httpx2.AsyncClient(timeout=90) as anonymous:
        response = await anonymous.post(connection["url"], json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        assert response.status_code == 401
        print("Public endpoint rejects anonymous requests.")
    async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + connection["token"]}, timeout=90) as http:
        async with Client(streamable_http_client(connection["url"], http_client=http), mode="legacy") as client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools.tools]
            print("Authenticated MCP tools:", names)
            status = await client.call_tool("memory_status", {})
            assert not status.is_error
            print("Archive status:", json.dumps(payload(status)))
            for query in ["Shatterfish pause", "sage green", "Pawtropolis retention"]:
                start = time.monotonic()
                found = await client.call_tool("search_memory", {"query": query, "limit": 3})
                assert not found.is_error
                results = payload(found)["results"]
                print("Search:", query, "matches:", len(results), "seconds:", round(time.monotonic() - start, 2))
                if results:
                    passage = await client.call_tool("read_source", {"document_id": results[0]["document_id"], "start_chunk": results[0]["ordinal"], "chunk_count": 1})
                    assert not passage.is_error and payload(passage)["passages"]
            booted = await client.call_tool("boot", {"part": "threads"})
            assert not booted.is_error
            print("Boot threads part:", len(booted.content[0].text), "characters")
            record = args.connection.parent / "acceptance-note.json"
            if not record.exists():
                saved = await client.call_tool("remember", {"type": "fact", "scope": "project:watchthelight", "title": "Memory MCP deployment", "content": "The private memory MCP endpoint at mcp.example.org was deployed on October 13, 2026. Authentication, MCP tool discovery, and source retrieval were exercised through the public HTTPS endpoint. Initial archive ingestion was started separately; consult memory_status for its completion.", "source_date": "2026-10-13"})
                assert not saved.is_error
                record.write_text(json.dumps(payload(saved)), encoding="utf-8")
                print("Saved deployment note through MCP.")


asyncio.run(main())
