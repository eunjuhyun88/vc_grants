# Claude Compatibility

This repository ships a Claude-native compatibility layer on top of the generic Memento Kit operating system.

## Mapping

| Claude concept | Memento layer |
| --- | --- |
| concise repo memory | `CLAUDE.md` |
| reusable expert modes | `.claude/agents/` and `.claude/commands/` |
| deterministic automation | `.claude/hooks/` and `.claude/settings.json` |
| progressive context | `README.md`, `AGENTS.md`, `docs/README.md`, canonical docs, generated maps |
| local risk guidance | nested `CLAUDE.md` files near risky directories |

## Rules

1. Keep root `CLAUDE.md` concise.
2. Do not duplicate stable truth in long prompt blobs.
3. Put reusable workflows in `.claude/commands/` or `.claude/agents/`.
4. Keep `.claude/hooks/` deterministic and cheap.
5. Keep risky local `CLAUDE.md` files short and specific to the nearby directory.

## Installed Claude-Native Files

- `.claude/README.md`
- `.claude/settings.json`
- `.claude/agents/*.md`
- `.claude/commands/*.md`
- `.claude/hooks/*.sh`

## Local Guidance Bootstrap

Run:

```bash
npm run claude:bootstrap
```

This scans for risky directories such as auth, persistence, billing, migrations, and infra paths. If those directories exist and do not already have a local `CLAUDE.md`, Memento Kit seeds one.

## When To Use Which Layer

- Use `CLAUDE.md` for the shortest repository map.
- Use `.claude/agents/` for narrow reusable expert modes.
- Use `.claude/commands/` for repeatable slash-command workflows.
- Use `.claude/hooks/` only for deterministic automation.
- Use nested local `CLAUDE.md` files for nearby hazards and checks.
- Keep stable product and architecture truth in `docs/`, not only in Claude-native files.
