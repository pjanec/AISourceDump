# 🛠️ dump.py: The Smart Source Code Dumper

`dump.py` is a command-line tool that scans one or more directories and concatenates all desired source files into a single, large text file.

Its powerful filtering system works just like `.gitignore`, allowing you to create highly specific file dumps for any purpose.

`dump.py` can be used for:

* LLM context creation
* Lightweight project archiving
* API documentation dumps
* Code review preparation
* Deterministic subset packaging

It’s designed to be **fast**, **flexible**, and **git-aware**.

---

## ✨ Features

* **Simple by Default**

  ```bash
  python dump.py src/ my_dump.txt
  ```
* **Git-Aware** — Automatically respects your project’s `.gitignore` file.
* **Powerful Filtering** — Uses the same syntax and logic as `.gitignore`, including exclusions (`*.log`) and re-inclusions (`!important.log`).
* **Hierarchical** — Looks for `.dumpignore` files in subdirectories, just like Git.
* **Flexible & Explicit** — Override defaults using `--rule` or `--filter-file` for predictable, repeatable dumps.
* **Smart Output** — Automatically creates unique, numbered output files (e.g., `my_dump_1.txt`) if the target already exists.

---

## ⚙️ Command-Line Reference

`python dump.py [OPTIONS] <input_dir> [<input_dir> ...] <output_file>`

### Arguments

| Argument      | Description                                                                                       |
| ------------- | ------------------------------------------------------------------------------------------------- |
| `input_dirs`  | One or more input directories to scan *(required)*                                                |
| `output_file` | Base name for the output file (e.g., `dump.txt`). Automatically made unique if it already exists. |

---

### Filtering Arguments

| Flag                   | Description                                                                     |
| ---------------------- | ------------------------------------------------------------------------------- |
| `--filter-file <path>` | Use a `.dumpignore`-style filter file. Can be repeated. Triggers Explicit Mode. |
| `--rule "<pattern>"`   | Add inline rules (multiple allowed). Triggers Explicit Mode.                    |
| `--no-gitignore`       | Disable `.gitignore` usage.                                                     |
| `--no-dumpignore`      | Disable hierarchical `.dumpignore` search (default mode only).                  |

---

### Other Arguments

| Flag            | Description                                                                                            |
| --------------- | ------------------------------------------------------------------------------------------------------ |
| `--exts <path>` | Path to file listing allowed extensions (e.g., `.py`, `.js`, `.md`). Adds an extra layer of filtering. |

---



## ⚡ Quick Start

### 1️⃣ Dump a Folder

Dumps all files from `src/` that are not ignored by `.gitignore`.

```bash
python dump.py src/ project_dump.txt
```

---

### 2️⃣ Dump a Project Using a Custom "Allow-List"

**File: `api.dumpignore`**

```bash
# 1. Ignore everything
*
# 2. Re-include only the api folder and the main readme
!api/
!README.md
```

**Command:**

```bash
python dump.py . api_dump.txt --filter-file api.dumpignore
```

---

### 3️⃣ Dump Using a Quick Command-Line Rule

Dump *only* Python files from the entire project, while still respecting `.gitignore`.

> Note: Using `*` first ensures we switch to “allow-list” mode.

```bash
python dump.py . py_dump.txt --rule "*" --rule "!*.py"
```

---

## 🧠 How Filtering Works

The filtering logic is **identical** to `.gitignore`.

### 🔸 The Golden Rule: “Last Match Wins”

1. Every file is **included** by default.
2. The script builds a list of rules from `.gitignore` and `.dumpignore`.
3. The **last matching rule** determines inclusion or exclusion.

### 🔸 Rule Syntax

* **Comments:** Lines starting with `#` are ignored.
* **Exclusions:**

  ```bash
  build/
  *.log
  ```
* **Re-Inclusions:**

  ```bash
  !src/important.log
  ```

---

## 📖 Filtering Modes

### 🧩 Mode 1: Hierarchical Mode (Default)

* **When:** No `--rule` or `--filter-file` provided.
* **Behavior:** Works like Git — merges `.gitignore` and `.dumpignore` hierarchically.
* **Use Case:** Default mode for multi-directory projects.

```bash
python dump.py . my_project_dump.txt
```

---

### ⚙️ Mode 2: Explicit Filter Mode (Static)

* **When:** At least one `--rule` or `--filter-file` is used.
* **Behavior:** Uses one static rule list and ignores subdirectory `.dumpignore`.
* **Rule Loading Order:**

  1. `.gitignore` (unless `--no-gitignore`)
  2. `--filter-file` (in order given)
  3. `--rule` (in order given)
* **Use Case:** Deterministic “build-only” or “API-only” dumps.

---

## 🚀 Examples

### Example 1: Basic Project Dump

```bash
python dump.py src/ docs/ project.txt
```

---

### Example 2: Using a Default `.dumpignore`

**File: `.dumpignore`**

```bash
# Exclude local folders
_data/
_build/
*.tmp
```

**Command**

```bash
python dump.py . my_clean_dump.txt
```

---

### Example 3: The “Allow-List” (Minimal Package)

**File: `api_package.dumpignore`**

```bash
*
!src/api/
!docs/api/
!README.md
```

**Command**

```bash
python dump.py . api_package.txt --filter-file api_package.dumpignore
```

---

### Example 4: Complex Filtering

**File: `complex.dumpignore`**

```bash
*
!a/
!b/
a/sub1/*
!a/sub1/*.cs
```

**Command**

```bash
python dump.py . complex_dump.txt --filter-file complex.dumpignore
```

---

### Example 5: Overriding `.gitignore`

**File: `include_log.dumpignore`**

```bash
!config/production.log
```

**Command**

```bash
python dump.py . dump_with_log.txt --filter-file include_log.dumpignore
```

Or inline:

```bash
python dump.py . dump_with_log.txt --rule "!config/production.log"
```

---

### Example 6: Disabling Git-Awareness

Dump everything, including files in `node_modules` or `build/`.

```bash
python dump.py . full_dump.txt --no-gitignore
```

---


# 🕉️ dump.py — Real-World Usage Guide

This guide shows practical scenarios for `dump.py` in real projects — from building small archives to creating filtered context datasets for AI or reviews.

---

## 🎯 1. Generate a Clean LLM Context Dump

Create a minimal, dependency-free code dump for an LLM to analyze your project’s core logic.

```bash
# Ignore everything first, then re-include only source code and main README
echo "*" > llm.dumpignore
echo "!src/" >> llm.dumpignore
echo "!README.md" >> llm.dumpignore

python dump.py . llm_context.txt --filter-file llm.dumpignore
```

✅ *Produces a single file containing only your main source tree and docs.*

---

## 🧱 2. Archive a Project for Offline Storage

Want to store only editable files and scripts, ignoring binaries or build artifacts?

```bash
# archive.dumpignore
*.exe
*.dll
*.zip
*.tar.gz
node_modules/
build/
```

**Command**

```bash
python dump.py . project_archive.txt --filter-file archive.dumpignore
```

---

## 🧩 3. Dump Only API Code and Documentation

```bash
# api_only.dumpignore
*
!src/api/
!docs/api/
!README.md

python dump.py . api_only.txt --filter-file api_only.dumpignore
```

✅ Ideal for publishing a smaller developer-facing subset of your repo.

---

## 🧰 4. Create a Review Package

Generate a dump containing only `.py` and `.md` files for code review or audits.

```bash
# allowed_exts.txt
.py
.md

python dump.py src/ review.txt --exts allowed_exts.txt
```

---

## 🔍 5. Combine Filters for Complex Use Cases

Merge multiple `.dumpignore` files in sequence. Later rules override earlier ones.

```bash
python dump.py . combined.txt \
  --filter-file base.dumpignore \
  --filter-file api.dumpignore \
  --filter-file docs.dumpignore
```

✅ Useful for large repos where teams manage their own `.dumpignore` sets.

---

## 🧪 6. Include One Log File from .gitignore

If `.gitignore` excludes `*.log`, but you need one file:

```bash
python dump.py . debug_dump.txt --rule "!logs/startup.log"
```

---

## 🗃️ 7. Full Unfiltered Snapshot

For full replication — includes everything Git normally ignores.

```bash
python dump.py . everything.txt --no-gitignore
```

---

## 🔧 8. Selectively Dump a Subtree

```bash
python dump.py src/plugins/ plugin_dump.txt
```

Or add filters:

```bash
python dump.py src/plugins/ plugin_dump.txt --rule "!*/tests/*"
```

---

## 💡 9. Dry Run and Debug (Optional Feature)

Preview what would be included without writing output:

```bash
python dump.py src/ preview.txt --dry-run
```

Or trace rule application (if supported):

```bash
python dump.py src/ debug.txt --debug
```

---

## 10. Extensions filtering

The `--exts` flag is a great way to filter for *only* the file types you care about, after the main `.dumpignore` logic has run.

### What the Extension File Should Look Like

The file is just a plain text file with one file extension per line.

- The leading dot (`.`) is optional (both `.py` and `py` work).
- Lines starting with `#` are ignored as comments.
- Blank lines are ignored.
- It's case-insensitive (`.py` will match `.PY`).

------

### Example

Let's say you only want to dump Python files, C# files, and Markdown files.

**1. Create your extensions file (e.g., `my_code.exts`):**

```
# my_code.exts
# Include Python and C# source files
.py
.cs

# Also include documentation
.md
txt
```

**2. Run the `dump.py` command using the `--exts` flag:**

Bash

```
python dump.py src/ my_code_dump.txt --exts my_code.exts
```

### What Happens:

The script will first use its normal filtering logic (respecting `.gitignore`, `.dumpignore`, etc.). Then, from that list of "allowed" files, it will do a *second* pass:

- `src/main.py` -> **INCLUDED** (matches `.py`)
- `src/README.md` -> **INCLUDED** (matches `.md`)
- `src/utils/helper.cs` -> **INCLUDED** (matches `.cs`)
- `src/config.json` -> **SKIPPED** (not in the `.exts` file)
- `src/tests/data.bin` -> **SKIPPED** (not in the `.exts` file)

