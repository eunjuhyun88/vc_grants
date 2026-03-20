Review the current staged changes or the file I just modified.
Check against the Critical Rules in CLAUDE.md:

- RULE-01: Does any Telegram list command (/grants /cohorts /funds /all /ranking /changes) call an LLM? If yes, flag as VIOLATION.
- RULE-02: Is any Opportunity being created without a parent Program? If yes, flag as VIOLATION.
- RULE-02: Is any deadline value being inferred or estimated without a verified source? If yes, flag as VIOLATION.
- RULE-03: Is any dedup auto-merging below confidence 0.85? If yes, flag as VIOLATION.
- RULE-04: Is any output being produced without checking output_status, confidence, source_tier, apply_url, and status filters? If yes, flag as VIOLATION.

Output format:
- List each VIOLATION with file name, line number, rule ID, and what the violation is.
- If no violations found, output: ✅ PASS — no rule violations detected.
- Do not suggest improvements outside the defined rules.
