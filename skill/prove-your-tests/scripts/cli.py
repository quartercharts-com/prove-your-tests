#!/usr/bin/env python3
"""prove-your-tests: one command for every step. No model runs here except in `write-plants`.

  prove-your-tests prove   --repo DIR --plants plants.json --test-cmd "CMD" --out DIR [...]
  prove-your-tests recover OUT_DIR
  prove-your-tests plant   --repo DIR --out plants.json FILE [...]      behavior plants, Python and JS/TS
  prove-your-tests scan    --repo DIR --name NAME [...]                 real call forms of a guarded name
  prove-your-tests check-plants plants.json [--repo DIR]                validate any model's plants
  prove-your-tests union   --plants plants.json SHARD_DIR [...]
  prove-your-tests write-plants --provider anthropic|openai --model M [...]   optional, needs an API key
  prove-your-tests mcp                                                  serve the commands as MCP tools (stdio)
  prove-your-tests prompt                                               print the model-neutral plant-writer prompt
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

COMMANDS = {"prove": "prove", "plant": "plant", "scan": "scan_forms", "check-plants": "plants_schema",
            "union": "union", "write-plants": "write_plants", "mcp": "mcp_server"}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "--version":
        from importlib import metadata
        try:
            print(metadata.version("prove-your-tests"))
        except metadata.PackageNotFoundError:
            print("prove-your-tests (not installed as a package)")
        return 0
    if cmd == "recover":
        if len(rest) != 1:
            print("usage: prove-your-tests recover OUT_DIR")
            return 2
        cmd, rest = "prove", ["--recover", rest[0]]
    if cmd == "prompt":
        print((HERE.parent / "prompts" / "plant-writer.md").read_text(encoding="utf-8"), end="")
        return 0
    if cmd not in COMMANDS:
        print(f"prove-your-tests: unknown command {cmd!r}\n{__doc__}")
        return 2
    module = __import__(COMMANDS[cmd])
    return module.main(rest)


if __name__ == "__main__":
    sys.exit(main())
