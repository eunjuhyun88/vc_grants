# Context Efficiency Report

This report estimates how much context the routing system saves before the agent reaches implementation files.

## Core Bundles

| Bundle | Files | Lines | Approx Tokens | Reduction vs canonical | Reduction vs all docs |
| --- | --- | --- | --- | --- | --- |
| small map | 10 | 864 | 7850 | 44.8% | 66.5% |
| canonical | 27 | 1733 | 14216 | 0.0% | 39.3% |
| all docs | 64 | 2746 | 23431 | -64.8% | 0.0% |

## Estimated Savings

- Small map saves approximately `6366` tokens vs the canonical bundle.
- Small map saves approximately `15581` tokens vs the all-doc bundle.
- Surface `core` saves approximately `15370` tokens vs the all-doc bundle.

## Surface Bundles

| Bundle | Files | Lines | Approx Tokens | Reduction vs canonical | Reduction vs all docs |
| --- | --- | --- | --- | --- | --- |
| core | 14 | 915 | 8061 | 43.3% | 65.6% |

## Structural Scorecard

| Check | Actual | Target | Result |
| --- | --- | --- | --- |
| Small-map reduction vs canonical | 44.8% | >= 40% | PASS |
| Small-map reduction vs all docs | 66.5% | >= 55% | PASS |
| Worst surface reduction vs all docs | 65.6% | >= 50% | PASS |
| Small-map approx tokens | 7850 | <= 3800 | FAIL |
| Small-map file count | 10 | <= 6 | FAIL |
| Canonical approx tokens | 14216 | <= 12000 | FAIL |

## Structural Readiness

- FAIL: structural routing gate
- Final acceptance still requires a repeated runtime benchmark with controlled noise.

## Budget Checks

- FAIL: Small map approx tokens <= 3800
- FAIL: Small map files <= 6
- FAIL: Canonical approx tokens <= 12000

## Small Map Files

- `README.md`
- `AGENTS.md`
- `docs/README.md`
- `ARCHITECTURE.md`
- `docs/SYSTEM_INTENT.md`
- `docs/CONTEXT_ENGINEERING.md`
- `docs/CLAUDE_COMPATIBILITY.md`
- `docs/AGENT_FACTORY.md`
- `docs/TOOL_DESIGN.md`
- `docs/AGENT_OBSERVABILITY.md`

## How To Use

- Compare small-map and surface bundles against canonical/all-doc bundles.
- Review `docs/generated/contextual-retrieval.md` if ambiguous tasks still open too many docs.
- Review `docs/generated/agent-catalog.md` if outsiders still cannot discover reusable agents quickly.
- Use this with `docs/CONTEXT_EVALUATION.md` for task-level evaluation.
- Run `npm run harness:benchmark -- --base-url http://localhost:4173` for repeated runtime/noise validation.
- If the small map grows too much, routing quality is degrading even if docs remain correct.

