


Process the design document

  .dev\[your topic]\[your desgni doc.md]
  

according to Design-From-Talk.md guide.

do not create new design, use the already existing one and create just task documents in same folder

Related documents that you can reference if needed:

- xxx
  
  

VERIFY FACTS

Do not assume. Verify all facts with the codebase before writing the design and tasks.

REVIEW BEFORE WRITING DESIGN
Review the whole design with respect to the existing codebase If there is anything ambiguous
or unclear or wrong or simply good to add, ask the user clarifying/suggesting questions first.

FINAL CHECK

Before finishing, make final review. Summarize the design and check if each of the final ideas there is covered
by the the TASKS. Fix it if not.

Also verify the design if it really matches the current codebase.
Check for potential project dependecy issues.

Check against the success conditions mentioned in the design talk.

create empty sample debt tracker (take inspiration from the below)

use codebase-memory mcp. Do not use search_code. Use search_graph to query my codebase instead."

```
# Gizmos-2 Headless — Technical Debt Tracker

| ID | Source | Description | Priority | Target Batch | Status |
|----|--------|-------------|----------|--------------|--------|
| DEBT-001 | BATCH-01 | GZH-001: `GZH001_2` for `TerminalDisconnectedEvent` round-trip not written (only Connected tested) | P3 | BATCH-02 | RESOLVED |
| DEBT-002 | BATCH-02 | GZH-011 Change 4: `SimHostApp` and `EditorSubsystem` don't pass hub to `LayerControlGizmo` (uiPublisher defaults null; hub not stored in those roots yet) | P2 | BATCH-03 | RESOLVED |
| DEBT-003 | BATCH-02 | GZH-010/015: `GizmoNetworkTransportModule` missing `GizmoCapabilitiesIngressSystem` — `Tracker.OnSample` never called in production from DDS samples | P2 | BATCH-03 | OPEN |

Legend:
- P1 = Critical (never enters tracker; always becomes Corrective Task 0 in next batch)
- P2 = Should fix (tracked here, assigned target batch)
- P3 = Nice to have (tracked here, best-effort)
- Status: OPEN / RESOLVED (do not delete resolved rows)

```