# Design-vs-Implementation Correctness Scan (reusable prompt for Claude)

**Purpose.** Verify that the codebase *correctly and fully* implements a set of design documents,
and produce a fix-ready `TASK-DETAIL*.md` + `TASK-TRACKER.md` for an independent coding agent.
This is a **deep implementation-correctness** audit (does the code behave as designed?), not a
shallow interface-conformance check (do the signatures match?).

**When to use.** "Check if the codebase implements design X", "find where the implementation
diverges from the spec", "audit subsystem Y for correctness vs its design docs".

> This guide encodes a method that has been run successfully used already.

what the user should give you:
 - the list of folders with design docs to check 
 - the output folder where the corrective task should go

---

## 0. Hard rules (non-negotiable for this repo)

1. **Use the `codebase-memory-mcp` graph tools to query code.** Project name (verify with `list_projects`):
   Tools: `search_graph` (BM25 `query=`, regex `name_pattern=`,
   `label=`, `file_pattern=`), `query_graph` (Cypher), `trace_path`, `get_code_snippet`, `get_architecture`.
2. **NEVER use `search_code` (the MCP grep tool) or the harness `Grep` for code lookups.** The first one has errors and the other is slow and consumes too many tokens. The user forbids it unless there is no other way of getting the info.
   Use `Read` only for exact raw file content (design docs, test files, the specific lines you will cite).
3. **A green test suite is NOT proof of correctness.** The most valuable findings are stubs behind passing
   tests, dead/unwired features, and tests that assert against stubs or bypass the real path.
4. **Do not fan out independent per-doc subagents for the *analysis conclusion*.** The designs are
   interdependent (shared types/protocols). Build ONE consolidated feature list first, then audit by
   risk-ranked cluster. (Parallel agents are fine *inside* the structured workflow below, because they
   share the cluster definitions and a verify stage.)
5. **Reference design sections; do not duplicate them.** Findings cite `<doc> §<n>` + the exact code symbol.

### 0.1 Confirm the MCP server is connected before starting
- Call `list_projects`. If it returns the project -> good. Exit with loud error if not.


---

## 1. Phase 0 -- enumerate the intended features

1. Identify the design-doc folders in scope (e.g. `.dev/blueprints-1`, `.dev/blueprints-2`, `.dev/breakpoints-1`). If the use  haven't given you a list of concrete folder, ask for them and stop.
2. Read the **`TASK-TRACKER.md`** (in each -- these are the compact feature
   inventory (one task = one feature, usually with Success Conditions in the matching `TASK-DETAIL*.md`).
3. Read the **`DEBT-TRACKER.md`** in each -- these list already-known deviations. A finding that is already
   `RESOLVED` is not a new bug; an `OPEN` debt that contradicts the design IS worth carrying forward.
4. Build one consolidated feature list and a **risk ranking**. Highest risk = algorithm-heavy code and
   integration seams: compilers/emitters, allocators, flatten/emit dual paths, IL/codegen, hot-reload
   sequencing/rollback, debug protocol. Lowest risk = pure data records, thin wrappers.

> Do NOT try to read every `TASK-DETAIL.md` line into context (they are huge). Read sections on demand
> during the audit. The trackers + design docs are enough to scope clusters.

---

## 2. The 7 correctness lenses (what "deep" means)

Each lens targets a distinct bug class. The workflow applies all 7 per cluster.

1. **SC-anchor** -- For each Success Condition / MUST clause: find the test claiming to cover it, READ the
   test body (is it vacuous? asserting a stub/constant/non-null-only? bypassing the ECB/event path?), then
   READ the production code path it exercises. *Highest-signal lens.*
2. **algorithm** -- Read the FULL body of algorithm-heavy methods; diff against the design's pseudocode.
   Off-by-one, wrong block/ordering, missing coalesce/split, overflow, wrong edge handling.
3. **integration-seam** -- `trace_path` producer->consumer: does the exact string/shape one side emits equal
   what the other matches/reads? Do events reach subscribers? Silent contract drift.
4. **reachability** -- Features implemented but never invoked from production (only test callers, or zero
   callers via `trace_path` inbound). Dead wiring, unregistered windows, uncalled menu populators.
5. **invariant** -- Struct byte-budgets/offsets/magic values; determinism (emit paths iterating
   `Dictionary`/`HashSet` without `OrderBy`); static mutable state; ring-buffer wraparound; ALC collectibility.
6. **dual-path** -- Logic duplicated in two places that MUST agree (e.g. emitter vs flattener ordering;
   write-op vs read-op pairing). Flag drift between them.
7. **spec-drift** -- Where code matches a patched/simplified `TASK-DETAIL` instead of the Detailed Design,
   flag the accumulated divergence.

**Bug archetypes seen on this repo (look for these specifically):**
- Codegen op emitted as a **comment** instead of a real call (probe/event dispatch silently dead).
- Read-op paired with the wrong write-op (cursor vs working-state field).
- ID maps keyed by positional index on one side, hash on the other -> all names garble.
- Arrays declared but never populated -> `IndexOutOfRangeException` at the consumer.
- UI/editor features built but never wired (sink never routed, window never registered, `IsAttached => true`).
- Tests that call a handler directly instead of through the event/coordinator that should invoke it.

---

## 3. The workflow (hunt + adversarial verify)

**Opt-in:** This launches dozens of agents. Only run when the user has asked for the scan / opted into a
workflow. Prefer **Sonnet** agents (set `model: 'sonnet'` on the `agent()` calls) -- the work is read-and-compare,
and Sonnet is much cheaper at this fan-out. (Last run: 87 agents, ~6.5M tokens, ~13 min wall.)

**Shape:** `pipeline(clusters, hunt, verify)`. Each cluster: a hunter produces candidate findings (structured),
then each candidate goes to an adversarial refuter that defaults to "not a defect" unless it re-confirms by
re-reading code + design. Keep only `isReal` survivors; sort by the refuter's corrected severity.

**Run it in the background**, then read the result file and fold survivors into the deliverables (Section 4).
If an agent stalls, the runtime auto-retries (seen with very large design docs); that's fine.

### 3.1 Reusable workflow script

Launch with the `Workflow` tool (`script:` inline). Edit the `UNITS` array to match the design set in scope and
the risk ranking from Phase 0. Everything else is reusable as-is.

```js
export const meta = {
  name: 'design-correctness-audit',
  description: 'Deep implementation-correctness audit of <SUBSYSTEM> vs design docs, risk-ranked, hunt + adversarial verify',
  phases: [
    { title: 'Hunt',   detail: 'per-cluster: extract SC/MUST-clauses, read tests+prod code, apply 7 lenses' },
    { title: 'Verify', detail: 'adversarially refute each candidate; keep only confirmed' },
  ],
}

const PROJECT = 'D-WORK-IOS-IG-SimHost-FDP' // verify with list_projects

const SHARED = `
## Tools (MANDATORY)
- codebase-memory MCP. Project EXACTLY: \`${PROJECT}\`.
- Load first: ToolSearch(query="select:mcp__codebase-memory-mcp__search_graph,mcp__codebase-memory-mcp__query_graph,mcp__codebase-memory-mcp__get_code_snippet,mcp__codebase-memory-mcp__trace_path,mcp__codebase-memory-mcp__get_architecture", max_results=10)
- Use search_graph / query_graph (Cypher) / trace_path / get_code_snippet. Read for exact design/test text.
- NEVER use search_code or harness Grep for code. Use the graph.
- Labels: Class, Interface, Method, Function, Enum, Variable, File, Module, Folder. Edges: CALLS, DEFINES, DEFINES_METHOD, INHERITS, IMPORTS, USAGE, WRITES, THROWS.

## Goal: IMPLEMENTATION CORRECTNESS, not interface conformance. A green test suite is not proof.
Apply 7 lenses, reading METHOD BODIES:
1 SC-anchor: per Success Condition, find the test -> read it -> is it vacuous/stub-asserting/path-bypassing? -> read the prod path.
2 algorithm: read full bodies of algorithm-heavy methods; diff vs design pseudocode.
3 integration-seam: trace_path producer->consumer; exact emitted string/shape == what consumer matches/reads? events reach subscribers?
4 reachability: features built but never invoked from production (only-test or zero callers).
5 invariant: struct byte budgets/offsets/magic; determinism (Dictionary/HashSet iteration in emit paths); static mutable state; ring buffers.
6 dual-path: duplicated logic that must agree (emitter vs flattener; write-op vs read-op).
7 spec-drift: code matching a patched task spec instead of the Detailed Design.

## Rules
- Do NOT re-report pure signature/naming nits or items already filed (listed per cluster). Find behavioral defects, stubs, dead wiring, broken invariants, algorithm bugs, dual-path drift.
- Every finding cites a real symbol you READ via MCP + concrete evidence (code does X vs design requires Y). Cannot confirm -> confidence="reported".
- Prefer FEWER, HIGH-CONFIDENCE findings. No invention. If a focus area is correct, say so in summary instead of inventing.
`

const FINDINGS_SCHEMA = {
  type: 'object', required: ['unit', 'summary', 'findings'],
  properties: {
    unit: { type: 'string' }, summary: { type: 'string' },
    findings: { type: 'array', items: { type: 'object',
      required: ['title','severity','lens','designRef','codeRef','claim','evidence','confidence'],
      properties: {
        title: { type: 'string' },
        severity: { type: 'string', enum: ['Critical','High','Medium','Low'] },
        lens: { type: 'string', enum: ['SC-anchor','algorithm','integration-seam','reachability','invariant','dual-path','spec-drift'] },
        designRef: { type: 'string' }, codeRef: { type: 'string' },
        claim: { type: 'string' }, evidence: { type: 'string' },
        confidence: { type: 'string', enum: ['verified','reported'] },
      } } },
  },
}
const VERDICT_SCHEMA = {
  type: 'object', required: ['isReal','confidence','reasoning'],
  properties: {
    isReal: { type: 'boolean' },
    confidence: { type: 'string', enum: ['high','medium','low'] },
    reasoning: { type: 'string' },
    correctedSeverity: { type: 'string', enum: ['Critical','High','Medium','Low','none'] },
  },
}

// EDIT THIS: one entry per risk-ranked cluster (highest risk first).
// design = doc path(s) (semicolon-separate multiple); focus = exactly what to read + which lenses dominate;
// refs = TASK-DETAIL/TRACKER/DEBT to consult; known = already-filed issues to NOT duplicate.
const UNITS = [
  { key: 'cluster-key', design: '.dev/<folder>/<DesignDoc>.md',
    focus: 'Read FULL bodies of <methods>; diff <algorithm> vs design §<n>; trace <seam>; check <invariant>.',
    refs: '.dev/<folder>/TASK-DETAIL.md (<TASK-IDs>), .dev/<folder>/DEBT-TRACKER.md',
    known: 'BPF-xxx ... (extend with NEW specifics only).' },
  // ...
]

function hunterPrompt(u) {
  return `Audit IMPLEMENTATION CORRECTNESS of a C# codebase vs design. Findings only; fix nothing.
${SHARED}
## Cluster: ${u.key}
Design: ${u.design}
Reference (claimed-done + known debt): ${u.refs}
ALREADY KNOWN (don't duplicate; may extend with NEW specifics): ${u.known}
## Focus
${u.focus}
## Process
1 Read relevant design sections (focus area, not cover-to-cover). 2 Locate prod code AND tests via the graph; read bodies with get_code_snippet; Read test files. 3 Apply the 7 lenses (SC-anchor: judge test vacuity). 4 Return ONLY behavioral/correctness defects, most-severe first; concrete, real symbols. If an area is correct, say so in summary.`
}
function refutePrompt(f, unit) {
  return `Adversarial verifier. A prior agent reported a possible correctness defect in cluster "${unit}". REFUTE it. Default isReal=false unless you positively re-confirm by reading actual code + design.
${SHARED}
## Claimed finding
Title: ${f.title}
Severity: ${f.severity} | Lens: ${f.lens} | Reporter confidence: ${f.confidence}
Design ref: ${f.designRef}
Code ref: ${f.codeRef}
Claim: ${f.claim}
Evidence: ${f.evidence}
## Process
1 Re-open cited code via get_code_snippet (+ trace_path for reachability/seam). 2 Re-open cited design via Read. 3 Look hard for reasons it is NOT a defect (correct/intentional+documented/design simplification/misread). 4 Set isReal + reasoning citing what you read; correctedSeverity (or "none").`
}

phase('Hunt')
log(`Correctness audit: ${UNITS.length} clusters, hunt + adversarial verify.`)
const perUnit = await pipeline(
  UNITS,
  (u) => agent(hunterPrompt(u), { label: `hunt:${u.key}`, phase: 'Hunt', schema: FINDINGS_SCHEMA, model: 'sonnet' }),
  (review, u) => {
    if (!review || !review.findings || review.findings.length === 0) return []
    return parallel(review.findings.map((f) => () =>
      agent(refutePrompt(f, u.key), { label: `verify:${u.key}:${(f.title || '').slice(0, 40)}`, phase: 'Verify', schema: VERDICT_SCHEMA, model: 'sonnet' })
        .then((v) => ({ ...f, unit: u.key, verdict: v }))
        .catch(() => null)))
  }
)
const all = perUnit.flat().filter(Boolean)
const confirmed = all.filter((f) => f.verdict && f.verdict.isReal)
log(`Hunt produced ${all.length} candidates; ${confirmed.length} survived verification.`)
const rank = { Critical: 0, High: 1, Medium: 2, Low: 3, none: 4 }
confirmed.sort((a, b) => (rank[a.verdict.correctedSeverity ?? a.severity] ?? 5) - (rank[b.verdict.correctedSeverity ?? b.severity] ?? 5))
return {
  totalCandidates: all.length, confirmedCount: confirmed.length,
  byCluster: UNITS.map((u) => ({ cluster: u.key, confirmed: confirmed.filter((f) => f.unit === u.key).length })),
  confirmed,
}
```

### 3.2 Cluster design tips
- One cluster per algorithm-heavy file/subsystem; split very large designs (e.g. a 4k-line compiler doc) into
  2 clusters (schedule/lower vs emit/roslyn).
- Put the dominant lens(es) and the exact symbols to read into `focus` -- vague focus yields vague findings.
- Always pass `known:` so agents extend rather than re-report filed issues.
- Concurrency auto-caps at ~10-16; passing 14+ clusters is fine (excess queues).

---

## 4. Fold results into the deliverables

The workflow returns immediately with a task id and writes the full result JSON to a temp output file
(path in the completion notification). Read that file (it is large -- page through it), then:

1. Append a **PART 2 -- Deep Correctness Audit** section to `<fixes-folder>/TASK-DETAIL.md` (create the folder
   by writing the file). One entry per confirmed finding: stable `BPF-NNN` id, corrected severity, lens,
   design ref, code ref, the gap (design X vs code Y), and a one-line fix direction. Group by severity.
2. Add matching checkbox rows to `<fixes-folder>/TASK-TRACKER.md`, linking to the detail anchors.
3. Note which findings re-confirm/extend earlier items, and which clusters produced ZERO findings (that is a
   real signal that the subsystem is solid -- record it).
4. **Honesty caveat to include:** the findings are adversarially verified by the agents, not necessarily
   re-read by you. Each carries its verifier's reasoning + exact refs so the fixing agent can confirm.

### Severity guidance
- **Critical** = wrong runtime behavior / uncompilable generated code / crash / data garble.
- **High** = a designed feature is non-functional or dead-wired; algorithm bug on a real path.
- **Medium** = failure-path-only corruption, determinism gap, fake-green test, partial population.
- **Low** = missing test the design mandates; cosmetic divergence.

---

## 5. Closing recommendation to always make

After any such audit, recommend the highest-leverage prevention: **end-to-end integration tests** that exercise
the real seams (e.g. "compile -> run under a debug session -> hit a breakpoint"; "open the editor -> windows
register + log populates"). End-to-end tests catch the entire "built but never wired / emitted as a comment"
bug class that unit-tests-around-stubs structurally cannot.
