# Generated Docs

These files are derived from the repo shape and `context-kit.json`.

- do not hand-edit them casually
- regenerate with `npm run docs:refresh`
- review `docs/generated/context-efficiency-report.md` to see whether the small map is still materially smaller than the larger bundles
- review `docs/generated/contextual-retrieval.md` to see what query-time retrieval is indexing
- review `docs/generated/agent-catalog.md` to see which reusable agents an outsider will discover
- review `docs/generated/tool-catalog.md` to see which reusable tools an outsider will discover
- review `docs/generated/agent-usage-report.md` to see measured usage and estimated time saved
- review `docs/generated/context-registry.md` to see what an external index or agent will discover first
- review `docs/generated/context-ab-report.md` to see whether routed mode actually beat baseline mode
- review `docs/generated/context-value-demo.md` for the shortest "why this matters" summary
- review `docs/generated/sandbox-policy-report.md` to keep execution boundaries visible
- pair the structural report with `npm run harness:benchmark -- --base-url <url>` before declaring the context design stable
