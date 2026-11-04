#!/usr/bin/env python3
"""A minimal MCP server (stdio, JSON-RPC 2.0, standard library only) that exposes the prove-your-tests commands.

Any MCP client (Claude Code, Claude Desktop, Cursor, the OpenAI Agents SDK, and others) can call the same
deterministic commands. Each tool runs the command in a child process and returns its output and exit code;
the verdict still comes only from prove.py, never from the model that called the tool.

Usage: prove-your-tests mcp     (or: python3 -I mcp_server.py)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = "2025-06-18"

S = {"type": "string"}
A = {"type": "array", "items": {"type": "string"}}
TOOLS = {
    "check_plants": ("Validate a plants file (any model may write it). Exit 0 valid, 2 refused.",
                     {"plants": S, "repo": S}, ["plants"]),
    "scan_forms": ("List the real call forms of guarded names in a repo (tests skipped).",
                   {"repo": S, "names": A}, ["repo", "names"]),
    "plant": ("Write behavior plants for Python or JS/TS files (never reads tests).",
              {"repo": S, "out": S, "files": A, "max": {"type": "integer"}}, ["repo", "out", "files"]),
    "prove": ("Run the proof: each plant must turn the tests red, be restored byte-identical, then green again. "
              "Exit 0 PASS, 1 FAIL, 2 NOT-RUN, 3 restore failed.",
              {"repo": S, "plants": S, "test_cmd": S, "out": S, "timeout": {"type": "number"},
               "min_plants": {"type": "integer"}, "allow_dirty": {"type": "boolean"}},
              ["repo", "plants", "test_cmd", "out"]),
    "recover": ("Put every file back from the journal after a crash.", {"out": S}, ["out"]),
    "union": ("Join shard reports into one verdict.", {"plants": S, "shards": A}, ["plants", "shards"]),
}


def argv_for(name: str, a: dict) -> list[str]:
    if name == "check_plants":
        return ["plants_schema.py", a["plants"], *(["--repo", a["repo"]] if a.get("repo") else [])]
    if name == "scan_forms":
        return ["scan_forms.py", "--repo", a["repo"], *sum((["--name", n] for n in a["names"]), [])]
    if name == "plant":
        return ["plant.py", "--repo", a["repo"], "--out", a["out"], *(["--max", str(a["max"])] if a.get("max") else []),
                *a["files"]]
    if name == "prove":
        v = ["prove.py", "--repo", a["repo"], "--plants", a["plants"], "--test-cmd", a["test_cmd"], "--out", a["out"]]
        if "timeout" in a:
            v += ["--timeout", str(a["timeout"])]
        if "min_plants" in a:
            v += ["--min-plants", str(a["min_plants"])]
        if a.get("allow_dirty"):
            v += ["--allow-dirty"]
        return v
    if name == "recover":
        return ["prove.py", "--recover", a["out"]]
    if name == "union":
        return ["union.py", "--plants", a["plants"], *a["shards"]]
    raise KeyError(name)


def call_tool(name: str, args: dict) -> dict:
    if name not in TOOLS:
        return {"isError": True, "content": [{"type": "text", "text": f"unknown tool {name}"}]}
    missing = [k for k in TOOLS[name][2] if k not in args]
    if missing:
        return {"isError": True, "content": [{"type": "text", "text": f"missing arguments: {missing}"}]}
    script, *rest = argv_for(name, args)
    r = subprocess.run([sys.executable, "-I", str(HERE / script), *rest], capture_output=True, text=True)
    text = (r.stdout + r.stderr)[-20000:] + f"\nexit code: {r.returncode}"
    if name == "prove":
        report = Path(args["out"]) / "REPORT.md"
        if report.exists():
            text += f"\nreport: {report}"
    # a tool error means the command could not run; a FAIL or NOT-RUN verdict is a normal answer
    return {"isError": r.returncode not in (0, 1, 2), "content": [{"type": "text", "text": text}]}


def handle(msg: dict) -> dict | None:
    mid, method = msg.get("id"), msg.get("method")
    if mid is None:  # a notification: no answer
        return None
    if method == "initialize":
        result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "prove-your-tests", "version": "0.1.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": n, "description": d,
                             "inputSchema": {"type": "object", "properties": p, "required": req}}
                            for n, (d, p, req) in TOOLS.items()]}
    elif method == "tools/call":
        params = msg.get("params") or {}
        result = call_tool(params.get("name", ""), params.get("arguments") or {})
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main(argv: list[str] | None = None) -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply: dict | None = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            reply = handle(msg) if isinstance(msg, dict) else None
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
