# Context Evaluation

This file defines how to evaluate whether the context system is actually helping.

## What To Measure

### 1. Structural efficiency

These are generated automatically:

- small-map files
- small-map lines
- small-map estimated tokens
- surface bundle lines/tokens
- canonical bundle lines/tokens
- all-docs bundle lines/tokens
- reduction percentages
- absolute tokens saved vs larger bundles

Primary report:

- `docs/generated/context-efficiency-report.md`

### 2. Retrieval quality

Track during real work:

- how many docs were opened before first edit
- whether the first opened docs were the correct ones
- whether the task needed archive docs or not

Suggested metric:

- retrieval precision = relevant docs opened before first edit / total docs opened before first edit
- retrieval hit rate = representative tasks where top retrieval results included the needed canonical doc

### 3. Resume quality

Track:

- time from session start to correct next action when using:
  - brief only
  - handoff
  - raw chat history

Suggested metric:

- resume latency in minutes

### 4. Noise rate

Track:

- runs that failed due to environment or harness noise
- runs that failed due to actual design or implementation problems

Suggested metric:

- infra noise rate = infra-caused failures / total measured runs

### 5. Runtime stability

Track:

- repeated harness duration on the same machine envelope
- duration coefficient of variation across measured runs
- warmup vs measured run separation

Suggested metric:

- duration CV = stddev(duration_ms) / mean(duration_ms)

### 6. Agent runtime value

Track:

- docs opened before first edit
- retrieval queries before first edit
- registry queries before first edit
- agent runtime minutes
- estimated manual baseline minutes
- estimated time saved

Primary report:

- `docs/generated/agent-usage-report.md`
- `docs/generated/context-value-demo.md`

### 7. Coordination safety

Track:

- pushes blocked by coordination conflicts
- overlapping-claim incidents
- handoffs that resumed on the wrong branch or stale lease

Suggested metrics:

- conflict catch rate = conflicts blocked before push / total observed conflicts
- stale-claim rate = expired or orphaned claims / total active claims

### 8. Tool reuse quality

Track:

- how often agents reused an existing tool instead of inventing an ad hoc wrapper
- whether tool contracts were sufficient without chat-only clarification
- whether the tool catalog exposed the right safe invocation first

Suggested metrics:

- reusable-tool hit rate = tasks where an existing tool contract was used / tasks that needed tooling
- tool catalog precision = relevant tool entries in the top visible registry results

## How To Run a Fair Comparison

Compare two modes:

1. routed mode
   - use the small map and canonical retrieval order
2. baseline mode
   - use a larger unfocused bundle such as all canonical docs or all docs

Control for:

- same model
- same reasoning mode
- same temperature or sampling settings
- same repository commit
- same branch/worktree
- same machine or container resources
- same network/tool availability
- same success criteria

Run each task multiple times. One run is not enough.

## Final Context Acceptance

Treat the context design as "final enough to rely on" only when all four are true:

1. structural scorecard passes in `docs/generated/context-efficiency-report.md`
2. runtime benchmark gate passes in `.agent-context/evaluations/<run-id>/summary.md`
3. at least one routed-vs-baseline task comparison shows lower docs-open count or lower resume latency
4. at least one measured agent run records baseline minutes and produces a non-empty usage report

## Why Noise Control Matters

Anthropic’s infrastructure-noise writeup shows that resource configuration alone can move agentic coding scores by several points. That means context experiments can also be misread if:

- one mode gets more retries
- one mode runs on a faster machine
- one mode gets a different browser/tool state
- one mode sees more transient failures

So the evaluation should separate:

- context-system improvement
- infrastructure variance

## Recommended Scorecard

| Metric | Target | Why |
| --- | --- | --- |
| Small-map reduction vs canonical | `>= 40%` | The routing layer should be materially smaller than full canonical context |
| Small-map reduction vs all docs | `>= 55%` bootstrap, `>= 70%` mature | A focused start bundle should avoid broad doc dumps |
| Surface bundle reduction vs all docs | `>= 50%` | Surface tasks should not need repo-wide context |
| Small-map approx tokens | `<= 3800` bootstrap, `<= 3500` mature | Keep the routing layer cheap enough to load first |
| Docs before first edit | `<= 6` | Forces just-in-time retrieval discipline |
| Retrieval hit rate | `>= 80%` bootstrap | Retrieval should usually include the right canonical doc near the top |
| Resume latency from brief | `< 3 min` | Briefs should be practically useful |
| Infra noise rate | `< 10%` | Too much infra noise invalidates comparisons |
| Duration CV on repeated runs | `< 15%` | Large variance means the environment is too noisy |
| Coordination conflict catch rate | `100%` for known overlaps | Overlaps should be blocked before merge-time damage |

## Practical Workflow

### Structural check

```bash
npm run docs:refresh
npm run docs:check
```

### Resume check

```bash
npm run ctx:save -- --title "resume benchmark" --work-id "W-..."
npm run ctx:checkpoint -- --work-id "W-..." --surface "<surface>" --objective "<objective>"
npm run ctx:compact -- --work-id "W-..."
npm run ctx:check -- --strict
```

### Evidence check

```bash
npm run harness:smoke -- --base-url http://localhost:4173
npm run harness:browser -- --base-url http://localhost:4173
```

### Noise-controlled benchmark

```bash
npm run harness:benchmark -- --base-url http://localhost:4173
```

This writes a repeated-run benchmark under `.agent-context/evaluations/` with:

- environment manifest
- repeated run timings
- infra-noise classification
- benchmark gate PASS/FAIL

### Manual A/B task check

For one representative task, record both:

- routed mode: small map -> canonical surface docs -> code
- baseline mode: large unfocused bundle

Track:

- docs opened before first edit
- minutes to first correct edit
- whether archive docs were needed
- final success/failure
- whether top retrieval results included the needed canonical doc

Then record it:

```bash
npm run eval:ab:record -- \
  --task-id "TASK-..." \
  --surface "<surface>" \
  --routed-docs 4 \
  --baseline-docs 11 \
  --routed-minutes 2 \
  --baseline-minutes 6
npm run eval:ab:refresh
```

For one parallel-task pair, also record:

- whether both agents declared claims before edits
- whether both agents declared explicit path boundaries before edits
- whether any overlap was blocked by `coord:check`
- whether handoff resumed from brief/checkpoint instead of raw chat memory

## Interpreting Results

If structural savings look good but task performance does not improve:

- retrieval order may still be wrong
- canonical docs may be too vague
- the task may depend on missing repo-local truth

If task performance varies widely run to run:

- the environment is too noisy
- do not conclude the context design is better or worse until infra noise is controlled

If the benchmark gate fails but the structure looks good:

- do not call the design final yet
- stabilize local preview, browser/tool availability, or machine allocation first

If the structure and runtime look good but the A/B report does not:

- the routing layer may still be too vague
- the registry may expose the wrong entry docs
- users will not feel the improvement yet, even if the system is tidy
