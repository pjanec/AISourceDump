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
- **Keep the prompt concise.** Windows `cmd.exe` has a command-line length limit of ~8191 characters. If your prompt is too long, the worker launch will fail. Break large tasks into smaller, sequential worker invocations rather than packing everything into one giant prompt.
- **Note:** Launching a new worker automatically kills any currently running worker. If the previous worker fails to die within 30 seconds, `start_worker` will return an error — in that case, try calling `kill_worker` to force-terminate it, then retry `start_worker`.

### 2. `get_worker_status`

**Purpose:** Checks the status of a worker launched in `non-blocking` mode.

**Arguments:** None.

**Returns:** A JSON object containing `status` (`idle`, `running`, `completed`, `failed`), `output`, and `error`.

**How to use effectively:**

- Poll this tool periodically (e.g., after doing some analysis or talking to the user) to see if the `non-blocking` worker has finished.
- Once the status is `completed`, read the `output` to see what the worker did, and then inspect the files it modified to verify its work.

### 3. `kill_worker`

**Purpose:** Forcefully terminates the currently running worker process.

**Arguments:** None.

**How to use effectively:**

- Use this if the worker appears stuck (e.g., `get_worker_status` has shown `running` for an unusually long time with no file changes).
- Use this if the user changes their mind about the current objective and you need to stop the worker immediately to assign a different task.
- Use this if `start_worker` returned an error about failing to kill the previous worker — it means the old process didn't die within the 30-second grace period. Call `kill_worker` to attempt another forced termination, then retry `start_worker`.