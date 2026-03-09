# Git Workflow

## Purpose

This file defines the git operating model for agents working in this repository.

The goal is not "use more git features."
The goal is:

- no direct work on the protected branch
- short-lived feature branches
- worktree-friendly isolation
- explicit sync before push or merge
- reproducible local safety defaults

## Branch Rules

1. Do not work directly on `main`.
2. Start feature work on `codex/<task-name>`.
3. Prefer one worktree per meaningful task.
4. Create a coordination claim before meaningful edits on a feature branch.
5. Keep branches short-lived and scoped to one coherent change.

## Worktree Rules

- Use `npm run safe:worktree -- <task-name> [base-branch]` to create an isolated worktree.
- Treat the current worktree as the canonical implementation target for the active task.
- Do not mix unrelated tasks in one dirty worktree.
- If a worktree becomes large or unstable, checkpoint and split the next task into a fresh worktree.

## Sync Rules

- Run `npm run safe:status` before non-trivial work.
- Run `npm run safe:sync` before push when the branch may be behind `origin/main`.
- Use `npm run safe:sync:gate` when you want sync plus context and project validation.
- Keep uncommitted changes out of sync operations.
- Prefer rebase-based sync for feature branches and fast-forward only on `main`.

## Push And Merge Rules

- Pass `npm run docs:check` and `npm run ctx:check -- --strict` before push.
- Pass project-specific `check`, `build`, or `gate` commands when configured.
- Push only from a branch with an active checkpoint or brief.
- Merge only with explicit human approval.
- Prefer squash merge or a short clean history over long accidental merge chains.
- Do not create periodic merge commits just to "save progress."

## What Should Be Periodic

Do these periodically during long-running agent work:

- `ctx:save`
- `ctx:checkpoint`
- `ctx:compact`
- `safe:status`
- branch sync check

Do not do this periodically:

- meaningless merge commits
- blind rebases without a clean worktree
- push without validation

## Recommended Local Git Config

Apply with:

```bash
npm run safe:git-config
```

The kit sets these repo-local defaults:

- `core.hooksPath=.githooks`
- `fetch.prune=true`
- `pull.ff=only`
- `merge.conflictstyle=zdiff3`
- `rerere.enabled=true`
- `rerere.autoupdate=true`

## Fast Commands

- inspect current repo state: `npm run safe:status`
- create isolated worktree: `npm run safe:worktree -- <task-name> [base-branch]`
- install hooks: `npm run safe:hooks`
- apply git defaults: `npm run safe:git-config`
- sync branch: `npm run safe:sync`
- sync and validate: `npm run safe:sync:gate`

## Interpretation

This repository uses git as part of the agent operating system:

- branches isolate intent
- worktrees isolate execution
- checkpoints isolate memory
- gates isolate bad state before push
