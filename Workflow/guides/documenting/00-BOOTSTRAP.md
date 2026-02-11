# Documentation Initiative - Initial Setup Protocols

**Role**: Bootstrap Instruction
**When to use**: ONLY at the very beginning of the documentation effort.
**Constraint**: Do NOT modify this file.

---

## Phase 1: Environment Scan

1.  **Traverse Directory**: Recursively scan the root folder and all subfolders.
2.  **Identify Targets**: List every `.csproj` file found.
3.  **Filter Targets**:
    * **INCLUDE**: All functional application projects (Core, Infrastructure, UI, Toolkits, etc.).
    * **EXCLUDE**: All Test projects (names containing `Test`, `UnitTests`, `IntegrationTests`, `Specs`, `Benchmark`).

## Phase 2: Tracker Creation

1.  **Create File**: Create a new file named `00-PROJECT-CHECKLIST.md` in the root documentation folder.
2.  **Apply Template**: Copy the content from `00-CHECKLIST-TEMPLATE.md` into this new file.
3.  **Populate Projects**:
    * Group the filtered `.csproj` files by their architectural layer (e.g., Core, Infrastructure, Domain, Presentation).
    * Fill the respective sections in `00-PROJECT-CHECKLIST.md` with these projects.
    * Format: `- [ ] [Project Name] (Path: relative/path/to.csproj)`
4.  **Save Tracker**: Ensure `00-PROJECT-CHECKLIST.md` is saved.

## Phase 3: Handover

1.  **Close** this file.
2.  **Open** `00-EXECUTION-GUIDE.md`.
3.  **Begin** the documentation work loop defined in the Execution Guide.