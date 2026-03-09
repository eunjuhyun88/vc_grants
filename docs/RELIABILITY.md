# Reliability

## Reliability Rules

- Define what counts as a healthy local run
- Define required gates before push/merge
- Define any latency or uptime expectations that matter locally
- Require repeated runtime comparisons with at least 2 measured runs before trusting variance metrics

## Failure Policy

- Errors should be actionable
- Validation should be reproducible
- Fix drift continuously instead of in large cleanup bursts
