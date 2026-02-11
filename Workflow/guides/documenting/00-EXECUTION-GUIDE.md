# Documentation Execution Guide

**Role**: Standard Operating Procedure (SOP)
**When to use**: At the start of EVERY work session (Day 1, Mid-project, or Finalization).
**Constraint**: Do NOT modify this file. Update `00-PROJECT-CHECKLIST.md` instead.

---

## 1. The Core Workflow

**Execute this loop until the Checklist is fully marked `[X]`.**

1.  **LOAD**: Open `00-PROJECT-CHECKLIST.md`.
2.  **SELECT**: Find the first item marked `[ ]` (Pending).
3.  **ANALYZE**: Read the source code, directory structure, and existing READMEs.
4.  **WRITE**: Create the documentation file (Standards defined below).
5.  **DISCOVER**: If you find complex patterns spanning multiple projects, add a new item to the "Emerging Relationships" section of the Checklist.
6.  **VERIFY**: Check line count (>500) and diagram count (2-3).
7.  **UPDATE**: Mark the item `[X]` in the Checklist.
8.  **REPEAT**: Go to Step 1.

---

## 2. Documentation Standards (Per Project)

**File Location**: `Docs/projects/[Category]/[ProjectName].md`

### Required Structure
1.  **Header**: Project Name, Path, Date.
2.  **README Validation**: Explicitly state if the existing project README is "Up-to-date", "Diverged", or "Missing" based on your code analysis.
3.  **Overview**: Purpose, Key Features, Architectural Layer.
4.  **Architecture**: High-level design, Components, Constraints (e.g., "Zero-Allocation").
5.  **ASCII Diagrams (Mandatory)**: Minimum 2-3 diagrams (Block, Flow, or State).
6.  **Source Analysis**: Key files, Namespaces, Core Classes.
7.  **Dependencies**: Internal and External (NuGet).
8.  **Usage Examples**: Minimum 3 code blocks showing how to init and use the library.
9.  **Best Practices**: Thread safety, Performance tips.
10. **Relationships**: Links to dependent projects.

### ASCII Art Guidelines
Use box-drawing characters for all diagrams:
```text
┌───────────┐       ┌───────────┐
│ Component │──────▶│ Dependency│
└───────────┘       └───────────┘
