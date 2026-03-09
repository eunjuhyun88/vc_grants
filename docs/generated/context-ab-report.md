# Context A/B Report

This report summarizes routed-vs-baseline task comparisons recorded with `npm run eval:ab:record`.

## Summary

- Comparisons recorded: `0`
- Routed wins: `0`
- Average docs reduction: `n/a`
- Average latency reduction (minutes): `n/a`
- Average retrieval precision delta: `n/a`
- Archive avoided count: `0`

## Acceptance Gate

- FAIL: recorded comparisons >= `1` and routed mode wins at least once

## Targets

- Docs before first edit target: `<= 6`
- Resume latency target: `< 3 min`

## Comparisons

| Task ID | Surface | Routed Docs | Baseline Docs | Routed Minutes | Baseline Minutes | Routed Success | Baseline Success | Routed Win |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| none | none | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## How To Use

- Record one comparison per representative task.
- Keep the repo commit, machine envelope, and prompt scaffolding constant across routed and baseline modes.
- Use this report with `docs/generated/context-efficiency-report.md` and the runtime benchmark before calling the context design final.

