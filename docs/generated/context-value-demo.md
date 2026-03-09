# Context Value Demo

This generated report is the fastest way to explain why the context system is useful in practice.

## Why It Feels Different

- You start from about `4030` tokens instead of `13186` across the broader docs set.
- You can discover `1` surfaces, `3` reusable agents, and `3` reusable tools without replaying chat history.
- Ambiguous tasks can fall back to retrieval over `154` indexed chunks.
- Measured runtime evidence currently shows `n/a` minutes of estimated time saved.
- Routed-vs-baseline evidence currently has `0` wins across `0` recorded comparisons.

## Felt Value Scorecard

| Check | Result | Evidence |
| --- | --- | --- |
| Small start bundle | PASS | 4030 tokens vs 13186 tokens across all docs (69.4% smaller) |
| Discovery works without chat memory | PASS | 1 surfaces, 3 agents, 3 tools |
| Ambiguity has a retrieval escape hatch | PASS | 154 retrieval chunks across 27 sources |
| Time-saved evidence exists | NEEDS EVIDENCE | 0 finished runs, n/a minutes estimated saved |
| Routed mode beat baseline at least once | NEEDS EVIDENCE | 0/0 routed wins |

## Latest Measured Run

- No measured runs recorded yet.

## Fast Demo Commands

```bash
npm run docs:check
npm run registry:query -- --kind tool --q retrieve
npm run registry:describe -- --kind tool --id context-retrieve
npm run retrieve:query -- --q "routing rules"
npm run agent:start -- --agent planner --surface core
npm run agent:event -- --type doc_open --path docs/PLANS.md
npm run agent:finish -- --status success --baseline-minutes 30
npm run agent:report
npm run value:demo
```

## Interpretation

- If the small-map reduction is weak, the routing layer is still too fat.
- If discovery counts are zero, outsiders will not feel the system yet.
- If retrieval has no chunks, ambiguous work will still fall back to broad scanning.
- If time-saved evidence is missing, users will read this as process overhead rather than leverage.
- If there are no routed wins, the system may be tidy but still not feel faster.

