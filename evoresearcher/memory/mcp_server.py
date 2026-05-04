"""Thin MCP-style wrappers for the two memories."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from evoresearcher.memory.store import JSONMemoryStore
from evoresearcher.schemas import MemoryEntry


def query_memory(memory_path: str, query: str, top_k: int = 3) -> list[dict]:
    store = JSONMemoryStore(Path(memory_path))
    return [entry.model_dump() for entry in store.query(query, top_k)]


def add_memory(memory_path: str, entry: dict) -> None:
    store = JSONMemoryStore(Path(memory_path))
    store.add(MemoryEntry.model_validate(entry))


def build_fastmcp_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("evoresearcher-memory")
    server.tool()(query_memory)
    server.tool()(add_memory)
    return server


if __name__ == "__main__":
    build_fastmcp_server().run()
