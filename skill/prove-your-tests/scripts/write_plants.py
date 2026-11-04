#!/usr/bin/env python3
"""Headless plant writer for CI: ask a model for plants, keep them only if they check out.

Works with the Anthropic API or any OpenAI-compatible endpoint (OpenAI, Moonshot/Kimi, DeepSeek, OpenRouter,
a local server). The model sees the plant-writer prompt, the catalog, the call-form scan and the code files you
name; it never sees a test file (a test path is refused). Its answer must be a plants file that passes
plants_schema.py and whose every edit applies to the tree as it is; anything else is NOT-RUN (exit 2) and no
file is written.

The API key is read ONLY from an environment variable (default ANTHROPIC_API_KEY or OPENAI_API_KEY, or the one
named by --key-env). It is never printed, logged or written; error text is scrubbed of it.

Usage:
  write_plants.py --provider anthropic|openai --model NAME --repo DIR --mode behavior|guard
                  --rule "only refund() moves money" [--name GUARDED ...] --out plants.json FILE [FILE ...]
                  [--base-url URL] [--key-env VAR] [--min-plants 25] [--timeout 300]
Exit: 0 plants written, 2 NOT-RUN (bad answer, bad input, no key), 3 the provider call failed.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from contextlib import redirect_stdout
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan_forms  # noqa: E402
from plants_schema import problems  # noqa: E402
from prove import check_plant, plants_digest  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DEFAULT_URL = {"anthropic": "https://api.anthropic.com/v1/messages",
               "openai": "https://api.openai.com/v1/chat/completions"}
DEFAULT_KEY = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def build_prompt(args: argparse.Namespace, repo: Path, scan: str) -> str:
    parts = [(HERE / "prompts" / "plant-writer.md").read_text(encoding="utf-8"),
             "\n## Catalog\n", (HERE / "references" / "catalog.md").read_text(encoding="utf-8"),
             f"\n## Your inputs\n- mode: {args.mode}\n- rule: {args.rule}\n- guarded names: {', '.join(args.name) or 'none'}\n"
             f"- minimum plants: {args.min_plants}\n- answer with the plants JSON object only, no other text\n",
             f"\n## Call-form scan (tests skipped)\n```\n{scan}\n```\n"]
    for f in args.files:
        parts.append(f"\n## File {f}\n```\n{(repo / f).read_text(encoding='utf-8')}\n```\n")
    return "".join(parts)


def call(provider: str, url: str, key: str, model: str, prompt: str, timeout: float) -> str:
    if provider == "anthropic":
        body = {"model": model, "max_tokens": 16000, "messages": [{"role": "user", "content": prompt}]}
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    else:
        body = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        headers = {"authorization": f"Bearer {key}", "content-type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if provider == "anthropic":
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return data["choices"][0]["message"]["content"]


def extract_json(text: str) -> object:
    """The plants object from a model answer: the whole answer, a fenced json block, or the outermost braces."""
    for candidate in (text, *re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    a, b = text.find("{"), text.rfind("}")
    if a != -1 and b > a:
        return json.loads(text[a:b + 1])
    raise json.JSONDecodeError("no JSON object in the answer", text, 0)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=["anthropic", "openai"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--mode", choices=["behavior", "guard"], required=True)
    ap.add_argument("--rule", required=True)
    ap.add_argument("--name", action="append", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--base-url")
    ap.add_argument("--key-env")
    ap.add_argument("--min-plants", type=int, default=25)
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("files", nargs="+")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    for f in args.files:
        if scan_forms.TEST_PATH.search(f.replace("\\", "/")):
            print(f"write-plants: {f} looks like a test file; the plant writer must never see tests")
            return 2
        if not (repo / f).is_file() or repo not in (repo / f).resolve().parents:
            print(f"write-plants: {f} is not a file inside {repo}")
            return 2
    key_env = args.key_env or DEFAULT_KEY[args.provider]
    key = os.environ.get(key_env, "")
    if not key:
        print(f"write-plants: set the {key_env} environment variable (the key is read from there only)")
        return 2
    scrub = lambda s: s.replace(key, "<key>")  # noqa: E731

    buf = io.StringIO()
    if args.name:
        with redirect_stdout(buf):
            scan_forms.main(["--repo", str(repo), *sum((["--name", n] for n in args.name), [])])
    prompt = build_prompt(args, repo, buf.getvalue() or "(no guarded names given)")

    try:
        answer = call(args.provider, args.base_url or DEFAULT_URL[args.provider], key, args.model, prompt, args.timeout)
    except (urllib.error.URLError, OSError, KeyError, IndexError, ValueError) as exc:
        print(f"write-plants: the provider call failed: {scrub(str(exc))}")
        return 3
    try:
        doc = extract_json(answer)
    except json.JSONDecodeError:
        print("write-plants: NOT-RUN, the answer holds no plants JSON; nothing written")
        return 2
    errs = problems(doc)
    if not errs:
        if doc["mode"] != args.mode:
            errs.append(f"the answer is mode {doc['mode']}, asked for {args.mode}")
        planted = {e["file"] for p in doc["plants"] for e in p["edits"]}
        stray = sorted(planted - set(args.files) - {e["file"] for p in doc["plants"] for e in p["edits"] if "create" in e})
        if stray:
            errs.append(f"plants edit files the writer was not given: {stray}")
        for p in doc["plants"]:
            why = check_plant(p, repo)
            if why:
                errs.append(f"plant {p['id']} does not apply: {why}")
        if len(doc["plants"]) < args.min_plants:
            errs.append(f"only {len(doc['plants'])} plants, at least {args.min_plants} asked")
    if errs:
        for e in errs[:30]:
            print(f"write-plants: {scrub(e)}")
        print(f"write-plants: NOT-RUN, {len(errs)} problem(s) in the model's answer; nothing written")
        return 2
    doc.setdefault("version", 1)
    doc["plants_sha256"] = plants_digest(doc["plants"])
    Path(args.out).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"write-plants: {len(doc['plants'])} plants -> {args.out} (model {args.model} via {args.provider})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
