# Claude Subagents

Use Claude subagents for reusable expert modes that should stay consistent across sessions.

## Included Defaults

- `planner.md`
- `implementer.md`
- `reviewer.md`

## Guidelines

1. Keep each subagent narrow.
2. Route through canonical docs before code scanning.
3. Reuse project scripts instead of encoding long ad-hoc instructions.
4. Promote stable patterns here only after they have proven reusable.
