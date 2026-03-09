---
description: Run a light context garbage-collection pass without changing product code.
---

Do not edit product code. Only clean context artifacts.

1. Review `docs/exec-plans/active/` and move completed plans to `docs/exec-plans/completed/` if appropriate.
2. Review `docs/AGENT_WATCH_LOG.md` and note if the log has become too noisy to be useful.
3. Run `npm run ctx:compact`.
4. Review `docs/generated/legacy-doc-audit.md` and flag stale docs for promotion, pruning, or archiving.
5. If risky local guidance is stale, rerun `npm run claude:bootstrap`.
