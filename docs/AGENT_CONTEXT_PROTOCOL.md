# Agent Context Protocol

Scope: current git worktree rooted at this repository

## 1) Purpose

Prevent context loss and reduce restart cost across long-running agent work.

## 2) Context Architecture

- `snapshot`: machine state
- `checkpoint`: semantic memory
- `brief`: fast resume
- `handoff`: fuller transfer
- `claim`: multi-agent ownership and path boundary

## 3) Core Commands

- `npm run ctx:save`
- `npm run ctx:checkpoint`
- `npm run ctx:compact`
- `npm run ctx:restore -- --mode brief`
- `npm run ctx:restore -- --mode handoff`
- `npm run ctx:check -- --strict`
- `npm run coord:claim`
- `npm run coord:check`
- `npm run coord:release`

## 4) Rules

- use checkpoints for non-trivial work
- use briefs for fast resume
- keep pinned facts durable and minimal
- do not commit runtime memory
- do not work on a feature branch without an active coordination claim
