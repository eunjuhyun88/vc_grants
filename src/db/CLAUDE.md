# Local Guidance: `src/db`

- Treat `src/db/` as persistence authority for the Funding Intelligence Agent.
- Preserve the `Organization -> Program -> Opportunity` hierarchy and do not add shortcuts that bypass `Program`.
- Keep source-backed facts separate from AI reasoning fields.
- Be careful with migrations, foreign keys, dedup rules, and output eligibility fields because mistakes here change every Telegram response.
