# Claude Compatibility Layer

This repository includes a Claude-native compatibility layer on top of the generic Memento Kit operating system.

## Purpose

- keep `CLAUDE.md` short and navigational
- expose reusable expert modes through `.claude/agents/` and `.claude/commands/`
- run deterministic automation through `.claude/hooks/`
- add local `CLAUDE.md` files near risky modules when those directories exist

## What Lives Here

| Need | Open |
| --- | --- |
| Claude-native repo map | `CLAUDE.md` |
| Claude-specific routing rules | `docs/CLAUDE_COMPATIBILITY.md` |
| reusable subagents | `.claude/agents/` |
| reusable slash commands | `.claude/commands/` |
| deterministic Claude hooks | `.claude/hooks/`, `.claude/settings.json` |
| risky-directory local guidance | `**/CLAUDE.md` near auth, persistence, infra, billing, or migration paths |

## Rules

1. Keep `CLAUDE.md` concise. It is a compass, not an encyclopedia.
2. Put stable workflow instructions in `.claude/agents/` or `.claude/commands/`, not in long chat prompts.
3. Keep hooks deterministic and cheap. Use hooks for automation, not for hidden reasoning.
4. Treat nested `CLAUDE.md` files as local risk guides, not as global authority.
5. Keep canonical project truth in tracked docs under `docs/` and route through `README.md`, `AGENTS.md`, and `docs/README.md`.
