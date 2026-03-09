# Agent Usage Report

This generated report summarizes runtime evidence for agent usage, context efficiency, and estimated time saved.

## Summary

- Runs recorded: `0`
- Finished runs: `0`
- Success rate: `n/a`
- Avg actual minutes: `n/a`
- Avg baseline minutes: `n/a`
- Total estimated time saved (minutes): `n/a`
- Avg docs before first edit: `n/a`
- Avg retrieval queries before first edit: `n/a`
- Avg registry queries before first edit: `n/a`

## Economic Primitive Breakdown

| Primitive | Value | Runs | Avg Actual Minutes | Total Estimated Time Saved |
| --- | --- | --- | --- | --- |
| none | none | 0 | n/a | n/a |

## Recent Runs

| Run | Agent | Surface | Status | Actual Minutes | Baseline Minutes | Time Saved |
| --- | --- | --- | --- | --- | --- | --- |
| none | none | none | none | n/a | n/a | n/a |

## How To Use

- Start a measured run with `npm run agent:start -- --agent "<agent-id>" --surface "<surface>"`.
- Record meaningful events with `npm run agent:event -- --type doc_open --path "<repo-path>"`.
- Finish the run with `npm run agent:finish -- --status success --baseline-minutes <n>`.
- Refresh this report with `npm run agent:report`.

