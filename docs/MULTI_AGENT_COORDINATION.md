# Multi-Agent Coordination

This file defines how multiple agents can work in parallel without corrupting context or stepping on the same code paths.

Scope:

- strongest when agents share the same repository filesystem or worktree family
- for cross-machine or cloud agents, promote the same ownership plan into tracked docs or an external coordinator and publish the registry manifest for shared discovery

## Coordination Model

The unit of parallel work is:

1. one work ID
2. one branch/worktree
3. one active coordination claim
4. one explicit surface
5. one explicit path boundary

If any of those are missing, the task is not safely partitioned.

## Required Workflow

1. create or enter a dedicated worktree
2. reserve a work ID
3. create a coordination claim before meaningful edits
4. record semantic checkpoint/handoff as work evolves
5. release or hand off the claim when the task ends

## Claim Rules

Use `npm run coord:claim -- ...` with:

- `--work-id`
- `--agent`
- `--surface`
- `--summary`
- one or more `--path` prefixes on feature branches by default

Claims are stored under `.agent-context/coordination/claims/`.

The claim command rejects:

- unknown surface ids
- feature-branch claims with no path boundary
- immediate overlap with another active claim

Each claim carries:

- branch
- worktree path
- surface
- owned path prefixes
- lease expiry
- optional dependencies and referenced docs

## Conflict Rules

The coordination system should fail fast when:

- a feature branch has no active claim
- two active claims overlap on a claimed path prefix
- two active claims share a surface but one or both did not declare explicit path boundaries
- a lease expires and the owner has not renewed or released it
- one branch holds multiple active claims

Shared paths are allowed only for configured low-risk prefixes such as generated docs or watch logs.

## Handoff Rules

When agent A hands work to agent B:

1. update the checkpoint and brief
2. release the claim with `--status handoff --handoff-to <agent>`
3. agent B creates a new claim that references the new work ID or dependency chain

Do not silently continue work under another agent's stale claim.

## Mechanical Enforcement

- `npm run coord:check`
  - active claim validation
  - lease freshness
  - branch ownership checks
  - path-overlap detection
- `npm run gate:context`
  - includes coordination validation
- `.githooks/pre-push`
  - prevents pushes when coordination conflicts are active

## Commands

- `npm run coord:claim`
- `npm run coord:list`
- `npm run coord:check`
- `npm run coord:release`

## Success Criteria

The multi-agent system is healthy when:

- most non-trivial feature branches have exactly one active claim
- claims identify code boundaries before implementation starts
- handoffs move through checkpoint + release instead of ad-hoc chat memory
- coordination checks catch overlaps before merge-time conflicts appear
