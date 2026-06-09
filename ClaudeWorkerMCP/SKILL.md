---
name: claude-worker-orchestration
description: "Orchestrate a background Worker Claude Code CLI instance for dev-lead workflows: delegate large tasks, refactoring, and scaffolding while focusing on architecture, review, and user interaction. WHEN: delegate task to worker, run background worker, start worker, check worker status, kill worker, orchestrate Claude Code, dev lead workflow, parallel development."
license: MIT
metadata:
  author: Zoo
  version: "1.0.0"
---

# Skill: Claude Worker Orchestration

You have access to an MCP server 'claude-worker-orchestrator' that allows you to act as a "Dev Lead" and orchestrate a background "Worker" Claude Code instance. Both you and the Worker operate in the same local directory.

Use these tools to delegate large tasks, refactoring, or scaffolding so you can focus on architecture, review, and user interaction.

## Available MCP Tools

### 1. `start_worker`

**Purpose:** Launches the Worker Claude instance to execute a specific task.

**Arguments:**

- `prompt` (string): The highly specific instruction for the worker (e.g., "Implement the login form in `src/Login.jsx` using the API definitions in `docs/api.md`").
- `mode` (string): `"blocking"` or `"non-blocking"`.
- `model` (string, optional): `"pro"` (default) or `"flash"`. `"pro"` uses `deepseek-v4-pro[1m]` for maximum capability; `"flash"` uses `deepseek-v4-flash` for faster, lighter tasks.

**How to use effectively:**

- **Use `non-blocking` for almost everything.** This is your superpower. While the worker is building the feature, you remain free to answer user questions, review other files, or prepare the next task.
- **Use `blocking` only for trivial, fast tasks** (e.g., "Run the linter and auto-fix errors in the `src` directory").
- **Always provide context.** The worker does not share your chat history. Tell it exactly which files to read and edit.
- **Keep the prompt concise.** The sanitized prompt is limited to **2048 bytes (2KB)** after sanitization. If your instructions are too long, write them to a file (e.g., `.claude/worker-task.md`) and pass a short prompt pointing the worker to that file. See **Prompt Length Limit** below for details.
- **Note:** Launching a new worker automatically kills any currently running worker. If the previous worker fails to die within 30 seconds, `start_worker` will return an error — in that case, try calling `kill_worker` to force-terminate it, then retry `start_worker`.

### 2. `get_worker_status`

**Purpose:** Checks the status of a worker launched in `non-blocking` mode.

**Arguments:** None.

**Returns:** A JSON object containing `status` (`idle`, `running`, `completed`, `failed`), `output`, and `error`.

**How to use effectively:**

- Poll this tool periodically (e.g., after doing some analysis or talking to the user) to see if the `non-blocking` worker has finished.
- **Do not poll in a tight loop.** `get_worker_status` enforces a **15-second cooldown** between calls. If you call it too soon, it will return an error telling you how many seconds to wait. Use the `wait` command to pause before polling again (e.g., `wait` 10 seconds, then call `get_worker_status`).
- Once the status is `completed`, read the `output` to see what the worker did, and then inspect the files it modified to verify its work.

### 3. `kill_worker`

**Purpose:** Forcefully terminates the currently running worker process.

**Arguments:** None.

**How to use effectively:**

- Use this if the worker appears stuck (e.g., `get_worker_status` has shown `running` for an unusually long time with no file changes).
- Use this if the user changes their mind about the current objective and you need to stop the worker immediately to assign a different task.
- Use this if `start_worker` returned an error about failing to kill the previous worker — it means the old process didn't die within the 30-second grace period. Call `kill_worker` to attempt another forced termination, then retry `start_worker`.

### 4. `wait`

**Purpose:** Blocks execution for a specified number of seconds. Designed for use by the calling model to wait before polling for worker status in non-blocking mode.

**Arguments:**

- `seconds` (number): Number of seconds to wait. Must be between 0 and 300 (5 minutes).

**How to use effectively:**

- **Use after launching a non-blocking worker** to give it time before checking status. For example: start a non-blocking worker, call `wait` with `seconds: 5`, then call `get_worker_status`.
- **Don't use in blocking mode** — blocking mode already waits for the worker to complete.
- **Keep waits reasonable** — shorter waits (15 seconds) are good for quick tasks; longer waits (60 seconds) for larger tasks.

## Prompt Length Limit

The sanitized prompt passed to the worker must be **no longer than 2048 bytes (2KB)**. If your prompt exceeds this limit, `start_worker` will return an error.

**When your instructions are too long:**

1. Write the detailed instructions to a file in the project directory (e.g., `.claude/worker-task.md`)
2. Pass a short prompt that points the worker to that file, for example: `"Read the instructions from .claude/worker-task.md and execute them."`

This keeps the command line short, avoids Windows cmd.exe length limits, and ensures the worker has access to the full task specification.