# MCP Server Setup Guide

## Prerequisites

- Node.js 18+ installed
- `claude` CLI available on your PATH (the Anthropic Claude Code CLI)
- Claude Desktop (or another MCP client)
- `DEEPSEEK_AUTH_TOKEN` environment variable set to your DeepSeek API key
  - **PowerShell:** `$env:DEEPSEEK_AUTH_TOKEN = "sk-your-key-here"`
  - **Cmd:** `set DEEPSEEK_AUTH_TOKEN=sk-your-key-here`
  
  > The worker is configured to route through DeepSeek's Anthropic-compatible endpoint. The server will **refuse to start** a worker if this variable is missing.

## 1. Build the Server

```bash
cd c:/Utils/ClaudeWorkerMCP
npm install
npm run build
```

This compiles TypeScript from `src/` into `dist/`.

## 2. Register with Claude Desktop

Add the server entry to your `claude_desktop_config.json`:

**Windows path:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "claude-worker-orchestrator": {
      "command": "node",
      "args": ["c:/Utils/AITools/ClaudeWorkerMCP/dist/index.js"],
      "env": {}
    }
  }
}
```

> **Note:** If using PowerShell or a different Node version manager (nvm, fnm), adjust the `command` to the full path of `node.exe`.

## 3. Verify

Restart Claude Desktop. The orchestrator tools (`start_worker`, `get_worker_status`, `kill_worker`) should appear as available MCP tools.

### Smoke Test

You can also test the server directly via CLI:

```bash
node dist/index.js
```

The server will start on stdio and log to stderr:
```
Claude Orchestrator MCP Server running on stdio
```

## Tools Reference

| Tool | Arguments | Description |
|------|-----------|-------------|
| `start_worker` | `prompt` (string), `mode` ("blocking" \| "non-blocking") | Launch a background Claude CLI worker with a task |
| `get_worker_status` | none | Poll worker state: `idle`, `running`, `completed`, `failed` |
| `kill_worker` | none | Force-terminate the current worker process |

## Troubleshooting

- **"claude not found"**: Ensure the `claude` CLI is installed and on your PATH
- **Worker seems stuck**: Use `kill_worker` to terminate, then check stderr for clues
- **No tools appear in Claude Desktop**: Check the MCP server path in `claude_desktop_config.json` is absolute and correct
