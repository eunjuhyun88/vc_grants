# Claude Compatibility Bootstrap

This report explains which Claude-native compatibility files were seeded or detected.

## Static Layer

- Root compatibility doc: `docs/CLAUDE_COMPATIBILITY.md`
- Claude routing doc: `.claude/README.md`
- Claude agents: `.claude/agents/`
- Claude commands: `.claude/commands/`
- Claude hooks: `.claude/hooks/`
- Claude hook settings: `.claude/settings.json`

## Risky Local Guidance

- Risky directories detected: `1`
- Local guides currently present: `1`
- Local guides missing: `0`

### Present Guides
- `src/db/CLAUDE.md` -> database access boundary

## Next Steps

- Fill any placeholder `Local Risks` sections in newly created local `CLAUDE.md` files.
- Keep root `CLAUDE.md` concise and navigational.
- Promote stable reusable workflows into `.claude/commands/` or `.claude/agents/`.
- Keep deterministic automation in `.claude/hooks/` and expensive validation in git hooks or explicit gates.

