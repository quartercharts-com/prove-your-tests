# prove-your-tests 0.1.0

First public release. Your tests pass. Do they catch bugs? Prove it.

- A deterministic runner: each planted bug must turn your tests red, the file comes back byte-identical, and the
  tests go green again. PASS only when every plant was caught; a timeout or a flaky test is NOT-RUN.
- Safe by design: refuses uncommitted work, journals every change, restores after crashes and signals,
  `recover` after `kill -9`.
- Plants from any AI, never by the author of the tests: one model-neutral prompt, a validator, a headless writer
  for Anthropic or any OpenAI-compatible API, an MCP server, adapters for Claude Code, Codex, Cursor and Gemini.
- Install with pipx or uv, as a Claude Code plugin, or as a GitHub Action.
- Measured on the shop example: weak tests 10/25, a pattern guard 8/46, an effect guard 25/25 and 46/46.

Topics for the repository: testing, mutation-testing, test-quality, claude-code, mcp, ai-agents, python,
javascript, typescript, github-actions, developer-tools.
