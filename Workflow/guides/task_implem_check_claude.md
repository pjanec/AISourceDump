# Fix-Verification Audit (reusable prompt for Claude)

**Purpose.** Verify that the **claimed-DONE fixes** in one or more `TASK-TRACKER.md` + `TASK-DETAIL.md`
fix-sets were *actually* implemented (and implemented *correctly*) in the current codebase, and produce a
fresh `TASK-DETAIL.md` + `TASK-TRACKER.md` of the **surviving gaps** for an independent coding agent.

This is the *second-order* companion to [design_implem_check_claude.md](./design_implem_check_claude.md):
- That guide audits **code vs design docs** ("does the code implement the spec?").
- This guide audits **code vs a list of fixes that were already filed and marked done** ("did the fixes
  that we claim we made actually land in production, or only in a test / a comment / one of two paths?").

**When to use.** "Check if the tasks in tracker X are properly implemented", "re-verify that batch Y's fixes
actually landed", "did we really close those issues or just check the boxes?".

> Encodes a method already run successfully on this repo (76 fixes re-checked → 23 candidates → 16 confirmed
> gaps; the compiler-emit / hot-reload / navigation / squad clusters held up 100%).

**What the user must give you:**
 - the list of folders that each contain a `TASK-TRACKER.md` + `TASK-DETAIL.md` (e.g. `.dev/blueprint-fixes-1`, `.dev/other-fixes-1`)
 - the output folder for the corrective tasks (e.g. `.dev/other-fixes-2`)

If either is missing, ask and stop.

---

## 0. Hard rules (non-negotiable for this repo)

1. **Use the `codebase-memory-mcp` graph tools to query code.** Confirm the project name with `list_projects`
   FIRST (it is the one whose `root_path` matches the cwd — do NOT assume the name from an older guide).
   Tools: `search_graph` (BM25 `query=`, regex `name_pattern=`, `label=`, `file_pattern=`),
   `query_graph` (Cypher), `trace_path`, `get_code_snippet`, `get_architecture`.
2. **NEVER use `search_code` (the MCP grep) or the harness `Grep` for code lookups.** The first has errors,
   the second is slow and burns tokens. Use `Read` only for exact raw file content (the `TASK-DETAIL` entries,
   design sections, and test bodies you cite).
3. **A green test suite is NOT proof a fix landed.** The whole point of this pass is to catch fixes that exist
   only in a test, only in a comment, only on one of two code paths, or behind a stub. Read the **production
   method body**, not just the test.
4. **The two trackers + detail docs are SMALL enough to read fully.** Unlike design docs, `TASK-DETAIL.md`
   files are typically a few hundred lines. Read them cover-to-cover up front — they already contain the exact
   code ref, the gap, and the *required fix* for every item. That is your verification checklist.
5. **Reference the original ID; do not duplicate the design.** Every finding cites the original `BPF-NNN` /
   `OFX-NNN` (etc.) id + the exact code symbol you READ via MCP + concrete current-code evidence.

### 0.1 Confirm the MCP server is connected before starting
- Call `list_projects`. If it returns the project → good, capture the exact `name`. Exit with a loud error if not.

---

## 1. Phase 0 — build the verification checklist

1. Read each in-scope `TASK-TRACKER.md`. Note for every row:
   - its **id**, **severity/lens**, and whether the box is `[x]` (claimed done) or `[ ]` (left open).
   - any inline note like *"(BATCH-10, partial: X only)"* or *"re-scoped to DEBT-NNN"* — these set the
     **tracker status** of the item (see §4) and tell you what to expect.
2. Read each `TASK-DETAIL.md` fully. Each entry gives **Code** (file + symbol), **Gap** (design X vs code Y),
   and **Fix** (what must now be true). The Fix line is the literal thing you verify is present.
3. Group the items into **risk-ranked clusters** by subsystem / file proximity (so one agent can verify several
   related items in one pass and share context). Highest risk first: algorithm-heavy emit/codegen, integration
   seams, editor/UI wiring. Lowest: pure data records, doc/debt rows.
4. **Embed each item's checklist line directly into its cluster prompt** (`id | sev | file:symbol | required
   fix`). Do NOT make agents re-derive the fix — you already have it from the detail doc. This is the single
   biggest quality lever; vague cluster prompts yield vague verdicts.

> Tip: include the already-`[ ]`-open items too. They should come back confirmed-NOT_IMPLEMENTED — a free
> sanity check that the workflow's verdict logic is sound.

---

## 2. The verification lenses (what "properly implemented" means)

For each claimed-done fix, decide its **status**: `NOT_IMPLEMENTED` (fix entirely absent), `PARTIAL` (one half
landed, a named sub-part missing), or *implemented-correctly* (no finding). Look specifically for these
"checked the box but…" archetypes — they are what this pass exists to catch:

1. **Test-only fix** — the test was rewritten but the production code it claims to exercise is unchanged.
2. **Comment-only / stub fix** — a `// Stub for Slice 1` body, a `{ }` empty method, a `TODO`.
3. **One-of-two-paths** — the fix landed in one translator/branch/emitter but not its sibling that "must agree".
   (Confirm BOTH paths via `trace_path`/`get_code_snippet`.)
4. **Built-but-unwired** — the method/window/handler exists and is unit-tested, but has **zero production
   callers** (`trace_path` inbound = tests only) or isn't on the interface consumers use → dead at runtime.
5. **Flag-ignored** — a field (`Enabled`, `IsStale`, …) was added to a record but the consumer's guard never
   reads it.
6. **Half-done numeric/spec fix** — dashed stroke drawn but not zoom-scaled; threshold added but formula wrong;
   `>=` changed to `>` on one of two call sites.
7. **Re-scoped / deferred** — verify the DEBT entry it points to actually exists and is the right status; an
   undocumented deferral (source comment but no DEBT row) is still a finding.

**SC-anchor items** (tests the design mandated): Read the test body. Is it vacuous (hard-coded booleans,
`Assert.Empty` on a constant-false predicate, calling a handler directly instead of through the event/ECB)?
Does it now exercise the real production path?

---

## 3. The workflow (verify + adversarial refute)

**Opt-in:** launches dozens of agents — run only when the user asked for the check / opted into a workflow.
Prefer **Sonnet** agents (`model: 'sonnet'`) — the work is read-and-compare and Sonnet is far cheaper at this
fan-out. (Last run: 37 agents, ~2.4M tokens, ~47 min wall with auto-retried stalls.)

**Shape:** `pipeline(clusters, verify, refute)`. Each cluster: a **verifier** reads the current cited code for
every item in its checklist and emits a finding ONLY for items whose required fix is missing/partial/incorrect
(listing the confirmed-OK ids in `verifiedOk`). Each finding then goes to an **adversarial refuter** that
**defaults to `isReal=false` (the fix IS present)** unless it re-confirms the gap by re-reading code + design.
Keep only `isReal` survivors; sort by the refuter's corrected severity.

**Run it in the background**, then read the result JSON and fold survivors into the deliverables (§4). Stalls on
large files auto-retry — that's fine.

### 3.1 Reusable workflow script

Launch with the `Workflow` tool (`script:` inline, or write it to a file and pass `scriptPath:`). Edit `PROJECT`
and the `UNITS` array to match the fix-sets in scope; everything else is reusable as-is.

```js
export const meta = {
  name: 'fix-verification-audit',
  description: 'Verify claimed-DONE fixes from <tracker-set> are actually present & correct in current code; verify + adversarial refute',
  phases: [
    { title: 'Verify', detail: 'per-cluster: read cited code, check each DONE fix is genuinely present/correct, flag missing/partial/incorrect' },
    { title: 'Refute', detail: 'adversarially re-confirm each flagged regression; default = fix is actually present' },
  ],
}

const PROJECT = '<verify with list_projects — the one whose root_path == cwd>'

const SHARED = `
## Tools (MANDATORY)
- codebase-memory MCP. Project EXACTLY: \`${PROJECT}\`.
- Load first: ToolSearch(query="select:mcp__codebase-memory-mcp__search_graph,mcp__codebase-memory-mcp__query_graph,mcp__codebase-memory-mcp__get_code_snippet,mcp__codebase-memory-mcp__trace_path,mcp__codebase-memory-mcp__get_architecture", max_results=10)
- Use search_graph / query_graph (Cypher) / trace_path / get_code_snippet. Use Read ONLY for exact design/test text.
- NEVER use search_code or harness Grep for code lookups. Use the graph.
- Labels: Class, Interface, Method, Function, Enum, Variable, File, Module, Folder. Edges: CALLS, DEFINES, DEFINES_METHOD, INHERITS, IMPORTS, USAGE, WRITES, THROWS.

## Your job: VERIFY FIXES, not re-audit from scratch.
Each issue below was previously reported with a code location and a Required Fix, then marked DONE [x].
For EACH issue read the CURRENT cited production code and decide: is the Required Fix genuinely present and correct NOW?
- A green test suite is NOT proof. Read the actual PRODUCTION method body, not just the test.
- Watch for: fix applied only to a test (not production); comment-only / stub "fix"; partial fix (one branch done, another not / one of two sibling paths); built-but-unwired (method exists but zero production callers / not on the consumer interface); a flag added to a record but the consumer guard never reads it.
- For SC-anchor / test-vacuity issues: Read the test body and confirm it now exercises the real path (not a hard-coded boolean / stub / bypass).

## Output rule
- Emit a finding ONLY for an issue whose Required Fix is NOT properly implemented now (status NOT_IMPLEMENTED | PARTIAL | INCORRECT).
- If an issue's fix IS genuinely present and correct, do NOT emit a finding — list its id in verifiedOk and (briefly) why in summary.
- Every finding cites the exact symbol you READ via MCP + concrete evidence (current code does X vs required fix Y). Prefer FEWER, HIGH-CONFIDENCE findings. No invention.
`

const FINDINGS_SCHEMA = {
  type: 'object', required: ['unit', 'summary', 'verifiedOk', 'findings'],
  properties: {
    unit: { type: 'string' }, summary: { type: 'string' },
    verifiedOk: { type: 'array', items: { type: 'string' } },
    findings: { type: 'array', items: { type: 'object',
      required: ['taskId','title','status','severity','codeRef','evidence','confidence'],
      properties: {
        taskId: { type: 'string' },
        title: { type: 'string' },
        status: { type: 'string', enum: ['NOT_IMPLEMENTED','PARTIAL','INCORRECT'] },
        severity: { type: 'string', enum: ['Critical','High','Medium','Low'] },
        codeRef: { type: 'string' },
        evidence: { type: 'string' },
        confidence: { type: 'string', enum: ['verified','reported'] },
      } } },
  },
}
const VERDICT_SCHEMA = {
  type: 'object', required: ['isReal','confidence','reasoning'],
  properties: {
    isReal: { type: 'boolean' }, // true = the fix really IS still missing/partial/incorrect
    confidence: { type: 'string', enum: ['high','medium','low'] },
    reasoning: { type: 'string' },
    correctedStatus: { type: 'string', enum: ['NOT_IMPLEMENTED','PARTIAL','INCORRECT','IMPLEMENTED'] },
    correctedSeverity: { type: 'string', enum: ['Critical','High','Medium','Low','none'] },
  },
}

// EDIT THIS: one entry per risk-ranked cluster (highest risk first).
// tasks = the DONE issues to re-verify, one per line: `ID (sev) file:symbol (Lline): <Required Fix — what must now be TRUE>`.
// refs = pointer to the detail doc + the ids in this cluster (agents may Read it on demand).
const UNITS = [
  { key: 'cluster-key', refs: '.dev/<folder>/TASK-DETAIL.md (ID-a, ID-b, ...)',
    tasks: `
ID-a (High) Path/To/File.cs SomeMethod (L120): <required fix in one line — the concrete thing that must be present in the current code>.
ID-b (Medium) Path/To/Other.cs Other.Method (L40): <required fix>.` },
  // ...
]

function verifyPrompt(u) {
  return `You are verifying that previously-filed, marked-DONE fixes are ACTUALLY implemented in the current codebase. Findings only; fix nothing.
${SHARED}
## Cluster: ${u.key}
Full original detail (read on demand if needed): ${u.refs}
## Issues to re-verify (each was marked DONE [x]):
${u.tasks}
## Process
1 For each issue: locate the cited symbol via the graph (search_graph / query_graph), read the CURRENT body with get_code_snippet, trace_path for reachability/seam items, Read test files for test-vacuity items.
2 Decide: is the Required Fix genuinely present and correct now?
3 Emit a finding ONLY when the fix is NOT properly implemented (NOT_IMPLEMENTED / PARTIAL / INCORRECT), most-severe first, with the exact symbol + concrete current-code evidence.
4 List every issue whose fix you confirmed present+correct in verifiedOk, and summarize.`
}
function refutePrompt(f, unit) {
  return `Adversarial verifier. A prior agent claims a previously-DONE fix in cluster "${unit}" is STILL not properly implemented. REFUTE this — DEFAULT isReal=false (the fix IS actually present and correct) unless you positively re-confirm, by reading the actual current code + design, that the fix is genuinely missing/partial/incorrect.
${SHARED}
## Claimed regression
Task: ${f.taskId}
Title: ${f.title}
Reported status: ${f.status} | Severity: ${f.severity} | Reporter confidence: ${f.confidence}
Code ref: ${f.codeRef}
Evidence: ${f.evidence}
## Process
1 Re-open the cited code via get_code_snippet (+ trace_path for reachability/seam, Read for test bodies). 2 Look hard for reasons the fix IS actually present (implemented elsewhere, intentional documented deviation, reporter misread, re-scoped to a DEBT entry). 3 Set isReal (true ONLY if genuinely still missing/partial/incorrect), confidence, reasoning citing what you read, correctedStatus + correctedSeverity.`
}

phase('Verify')
log(`Fix-verification audit: ${UNITS.length} clusters, verify DONE fixes + adversarial refute.`)
const perUnit = await pipeline(
  UNITS,
  (u) => agent(verifyPrompt(u), { label: `verify:${u.key}`, phase: 'Verify', schema: FINDINGS_SCHEMA, model: 'sonnet' }),
  (review, u) => {
    const out = { unit: u.key, summary: (review && review.summary) || '', verifiedOk: (review && review.verifiedOk) || [], candidates: [] }
    if (!review || !review.findings || review.findings.length === 0) return out
    return parallel(review.findings.map((f) => () =>
      agent(refutePrompt(f, u.key), { label: `refute:${u.key}:${(f.taskId || '').slice(0, 16)}`, phase: 'Refute', schema: VERDICT_SCHEMA, model: 'sonnet' })
        .then((v) => ({ ...f, unit: u.key, verdict: v }))
        .catch(() => null)))
      .then((verdicts) => { out.candidates = verdicts.filter(Boolean); return out })
  }
)
const units = perUnit.filter(Boolean)
const all = units.flatMap((u) => u.candidates)
const confirmed = all.filter((f) => f.verdict && f.verdict.isReal)
log(`Verify produced ${all.length} candidate regressions; ${confirmed.length} survived adversarial refutation.`)
const rank = { Critical: 0, High: 1, Medium: 2, Low: 3, none: 4 }
const sevOf = (f) => f.verdict && f.verdict.correctedSeverity && f.verdict.correctedSeverity !== 'none' ? f.verdict.correctedSeverity : f.severity
confirmed.sort((a, b) => (rank[sevOf(a)] ?? 5) - (rank[sevOf(b)] ?? 5))
return {
  totalCandidates: all.length, confirmedCount: confirmed.length,
  byCluster: units.map((u) => ({ cluster: u.unit, confirmed: confirmed.filter((f) => f.unit === u.unit).length, verifiedOk: u.verifiedOk, summary: u.summary })),
  confirmed,
}
```

### 3.2 Cluster design tips
- One cluster per subsystem/file group (e.g. `compiler-emit`, `debug-session`, `editor-windows`, `hsm-host`,
  `nav`, `squad`). Aim for ~4-10 items per cluster; ~10-15 clusters total is comfortable (concurrency auto-caps
  ~10-16, excess queues).
- Put the **exact symbol + the one-line required fix** in each `tasks` line. The verifier's quality is bounded
  by how concrete that line is.
- The `byCluster[].verifiedOk` + `summary` are part of the deliverable (the "do not re-open" list) — the script
  threads them through the pipeline's second stage so they survive into the result JSON.

---

## 4. Fold results into the deliverables

The workflow returns a task id and writes the full result JSON to a temp output file (path in the completion
notification). Read it (page through — it is large), then write to `<output-folder>/`:

1. **`TASK-DETAIL.md`** — one entry per **confirmed** finding, grouped by the refuter's corrected severity.
   Give each a new stable verification id (e.g. `VFX-NN`) AND cite the original id, the **status**
   (NOT_IMPLEMENTED / PARTIAL), the lens, the code ref, the gap (which half landed vs what's still missing),
   and a one-line fix direction. Add a **Tracker status** tag per item:
   - `REG` — genuine regression: the original row was `[x]` with no deferral note.
   - `OPEN` — the original row was `[ ]`; confirmed still open (expected).
   - `DEF` — documented/deferred: the row note or a DEBT entry already flagged it (verify the DEBT row exists + status).
2. **`TASK-TRACKER.md`** — matching checkbox rows linking to the detail anchors, grouped by severity, with the
   tracker-status legend. **Verify your anchor links** — GitHub slugs lowercase the heading, drop punctuation
   (backticks, `.`, `/`, `()`, `<>`, em-dashes), keep underscores, and turn each space into a hyphen (so
   `VFX-01 — BPF-003` → `#vfx-01--bpf-003-…` with the double hyphen).
3. **Record the positives.** Add a "Confirmed CLEAN — do not re-open" section listing every `verifiedOk` id by
   cluster, and call out **clusters with ZERO surviving findings** (a real signal that batch held up).
4. **Honesty caveats to include:**
   - Findings are adversarially verified by the agents, not necessarily re-read by you. Each carries its
     verifier's reasoning + exact refs so the fixing agent can confirm.
   - **Refuter overturns:** when a verifier flags an item but its refuter sets `isReal=false`, that item is
     dropped from the confirmed list. If it sits in a cluster where *sibling* items are confirmed-broken
     (e.g. the rest of the editor windows are dead), add a short **"Re-check (hunter-flagged, refuter did not
     confirm)"** section so the overturn isn't silently trusted.

### Severity guidance (use the refuter's corrected severity)
- **Critical** = wrong runtime behavior / uncompilable generated code / crash / data garble that the "fix" was
  supposed to remove but didn't.
- **High** = a designed feature is still non-functional / dead-wired; the fix is entirely absent on a real path.
- **Medium** = partial fix (one of two paths), failure-path-only, determinism gap, still-fake-green test,
  undocumented reduced surface.
- **Low** = perf-only (correctness-neutral), missing-test-only, cosmetic, or already-documented-backlog.

---

## 5. Closing recommendation to always make

The gaps this pass finds cluster exactly where unit-tests-around-stubs structurally cannot reach: **built-but-
unwired** features, **session→asset / DI wiring** seams, **consumer gates that ignore a flag**, and
**one-of-two-paths** fixes. After the audit, recommend the highest-leverage prevention: **end-to-end
integration tests that exercise the real seams** (e.g. "open the editor → assert windows register + populate";
"toggle a breakpoint disabled → assert it does NOT fire"; "load an asset → assert its debug overlay
symbolicates"). Those catch the entire "checked the box but it only landed in a test/comment/one path" class
that this verification pass had to find by hand.

---

## 6. Operational notes (lessons from the last run)
- **Read the trackers + detail docs fully first** — they are small and they ARE the checklist. Don't fan out
  before you've built the embedded `UNITS`.
- **Always `list_projects` first.** The graph project name tracks the cwd; an older guide may name a sibling
  checkout (`-FDP` vs `-FDP-2`).
- **Stalls auto-retry.** Large source files occasionally stall an agent ~5-15 min; the runtime retried 7 of 37
  last time and recovered all — coverage stays complete. Run in background and wait for the notification rather
  than polling.
- **Persist the script** to `.dev/.guides/_verify_workflow_<output-folder>.js` (or let the tool persist it) so
  the run is reproducible and resumable via `Workflow({scriptPath, resumeFromRunId})`.
- **Don't trust a lone refuter overturn in a broken neighborhood** — see §4 caveat 2.
