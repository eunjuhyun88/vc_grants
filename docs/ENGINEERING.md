# Engineering Authority

## Current Inventory Snapshot
<!-- BEGIN MEMENTO MANAGED INVENTORY -->
Refreshed: `2026-03-09`

| Surface | Routes | Stores | APIs | Mapping Mode |
| --- | --- | --- | --- | --- |
| `core` | 1 | 0 | 0 | auto-seeded-all |

### Unmapped Discovered Routes
- none

### Unmapped Discovered Stores
- none

### Unmapped Discovered APIs
- none

Review this snapshot, then replace the placeholder language in `State Authority` with project-specific rules.
<!-- END MEMENTO MANAGED INVENTORY -->

## State Authority

Replace this placeholder with project-specific truth for:

- routes/surfaces
- client or local state
- server-authoritative state
- persistence

## Boundary Rules

- Parse external data at boundaries
- Prefer stable contracts over inferred shapes
- Document ownership changes here before large refactors spread
- Promote repeated state and API ownership rules into this file
