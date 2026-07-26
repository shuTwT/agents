# Feishu Agents

This repository is a portable agent-plugin marketplace for Feishu Open Platform development.

## Source of truth

- Author plugin content only under `plugins/`.
- Keep `.claude-plugin/marketplace.json` as the Claude Code marketplace source.
- Generate Codex and OpenCode artifacts with `python3 tools/generate.py`.
- Do not hand-edit generated output under `.codex/` or `.opencode/`.
- Generate marketplace catalogs with `make docs`; do not hand-edit files under `docs/`.

## Plugin conventions

- Plugin and component names use lowercase kebab-case.
- Agent, Skill, and Command descriptions must state when they should activate.
- Skills are navigation-first; move detailed material into `references/`.
- Never invent a Feishu endpoint, permission, event payload, or token rule. Use the official Feishu documentation search MCP when it is available.
- Never place credentials, access tokens, or customer data in this repository.

## Local quality checks

```bash
make generate-all
make check-drift
make validate
make test
```

The first plugin targets TypeScript/Node.js and Chinese-speaking Feishu Open Platform developers.
