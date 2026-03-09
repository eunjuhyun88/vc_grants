# CLAUDE.md

This repository is configured with Memento Kit.

## Project Info

- Name: `VC_Grants` (Funding Intelligence Agent)
- Summary: `범용 AI agent — 사용자가 프로젝트 등록하면 맞춤 펀딩 기회(Grant/Accelerator/VC Cohort/Ecosystem Builder) 탐색·검증·매칭·팔로업`
- Stack: `Python / SQLite / Telegram Bot`
- Phase: `re-design → MVP implementation`
- Deadline: `TBD`

## Start Here

1. `README.md`
2. `AGENTS.md`
3. `docs/README.md`
4. `docs/SYSTEM_INTENT.md`
5. `ARCHITECTURE.md`

## File Map

| Need | Open |
| --- | --- |
| collaboration rules | `README.md`, `AGENTS.md` |
| Claude-native layer | `.claude/README.md`, `docs/CLAUDE_COMPATIBILITY.md` |
| runtime context memory | `.agent-context/briefs/`, `.agent-context/handoffs/` |
| architecture map | `ARCHITECTURE.md` |
| system intent | `docs/SYSTEM_INTENT.md` |
| doc router | `docs/README.md` |
| active plans | `docs/exec-plans/active/` |
| surface specs | `docs/product-specs/` |
| generated maps | `docs/generated/` |
| prompts | `prompts/` |

## Context Discipline

- Treat the current git worktree rooted at this repository as the canonical implementation target.
- Do not start in `docs/archive/`.
- Do not treat `.agent-context/` as authority.
- Keep `CLAUDE.md` short; put reusable expert workflows in `.claude/agents/` or `.claude/commands/`.
- Use `ctx:checkpoint` for semantic memory.
- Use `ctx:compact` and `ctx:restore` instead of relying on long chat history.
