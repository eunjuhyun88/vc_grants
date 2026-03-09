# Claude Hooks

These hooks are the Claude-native safety and memory layer for this repository.

## Included Hooks

- `session-start.sh`
  - reminds Claude to use the small-map reading order
  - injects the latest branch brief when available
- `post-edit.sh`
  - refreshes lightweight runtime context after edit tools
- `pre-compact.sh`
  - refreshes compact artifacts before Claude compaction
- `stop-context.sh`
  - refreshes runtime context at stop/subagent-stop time

## Rules

1. Hooks must stay deterministic.
2. Hooks should reuse repo-local scripts rather than duplicate logic.
3. Expensive validation belongs in git hooks and explicit gates, not in every Claude hook.
