# Harness

## Harness Layers

1. Docs governance
2. Context quality
3. Context efficiency report
4. Smoke harness
5. Browser evidence harness
6. Repeated runtime benchmark

## Commands

- `npm run docs:refresh`
- `npm run docs:check`
- `npm run ctx:check -- --strict`
- review `docs/generated/context-efficiency-report.md`
- review `docs/generated/contextual-retrieval.md`
- review `docs/generated/context-ab-report.md`
- `npm run harness:smoke -- --base-url http://localhost:4173`
- `npm run harness:browser -- --base-url http://localhost:4173`
- `npm run harness:all -- --base-url http://localhost:4173`
- `npm run harness:benchmark -- --base-url http://localhost:4173`

## Evidence Policy

- Generated docs show the current discoverable shape of the repo
- Generated context-efficiency output shows how much the routing layer is saving relative to larger bundles
- Generated contextual retrieval output shows how many docs and chunks are indexed for query-time disambiguation
- Generated A/B output shows whether routed mode beat baseline mode on representative tasks
- `.agent-context/harness/` stores local run artifacts
- Browser evidence harness captures DOM and screenshots
- `.agent-context/evaluations/` stores repeated-run noise benchmarks and environment manifests
