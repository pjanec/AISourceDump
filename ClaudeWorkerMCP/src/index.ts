import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from '@modelcontextprotocol/sdk/types.js';
import { spawn, ChildProcess, exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

/**
 * Sanitizes an untrusted string to be safely passed as a double-quoted argument
 * in cmd.exe. The caller MUST wrap the result in outer double quotes.
 *
 * Order of operations matters:
 *  1. Strip newlines/carriage returns (execution vector)
 *  2. Replace double quotes and backticks with single quotes (breakout + downstream)
 *  3. Escapes % for cmd variable expansion; strips ! for delayed expansion
 *  4. Strip non-printable control characters
 */
function sanitizeForCmd(input: string): string {
  if (!input) return '';

  let sanitized = input;

  // 1. Strip newlines and carriage returns — replace with space
  sanitized = sanitized.replace(/[\r\n]+/g, ' ');

  // 2. Replace double quotes and backticks with single quotes
  sanitized = sanitized.replace(/["`]/g, "'");

  // 3. Neutralize variable expansion vectors
  sanitized = sanitized.replace(/%/g, '%%'); // Escapes % in cmd
  sanitized = sanitized.replace(/!/g, '');   // Strips ! to prevent delayed expansion

  // 4. Strip non-printable control characters (0x00-0x1F, 0x7F)
  sanitized = sanitized.replace(/[\x00-\x1F\x7F]/g, '');

  return sanitized;
}

type WorkerStatus = 'idle' | 'running' | 'completed' | 'failed';

class ClaudeOrchestratorServer {
  private server: Server;
  private currentWorkerProcess: ChildProcess | null = null;
  private workerStatus: WorkerStatus = 'idle';
  private workerOutput: string = '';
  private workerError: string = '';
  private lastStatusPollTime: number = 0;

  constructor() {
    this.server = new Server(
      {
        name: 'claude-orchestrator-mcp',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupToolHandlers();
    
    // Error handling
    this.server.onerror = (error) => console.error('[MCP Error]', error);
    process.on('SIGINT', async () => {
      await this.killWorkerProcess();
      await this.server.close();
      process.exit(0);
    });
  }

  /**
   * Hard kills the Windows process tree and waits for the process to actually exit.
   * Required because shell: true spawns a cmd.exe which spawns the actual tool.
   * Returns true if the process was killed (or wasn't running), false if it failed to die within 30 seconds.
   */
  private async killWorkerProcess(): Promise<boolean> {
    if (!this.currentWorkerProcess || !this.currentWorkerProcess.pid) {
      this.currentWorkerProcess = null;
      this.workerStatus = 'idle';
      return true;
    }

    const processRef = this.currentWorkerProcess;
    const pid = processRef.pid;

    try {
      console.error(`[Orchestrator] Killing process tree for PID ${pid}`);

      // If already dead, just clean up
      if (processRef.exitCode !== null || processRef.killed) {
        console.error(`[Orchestrator] Process ${pid} already exited`);
        this.currentWorkerProcess = null;
        this.workerStatus = 'idle';
        return true;
      }

      // Issue the kill
      await execAsync(`taskkill /pid ${pid} /t /f`);

      // Wait for the process to actually exit (up to 30 seconds)
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error(`Worker process ${pid} did not terminate within 30 seconds`));
        }, 30000);

        const onClose = () => {
          clearTimeout(timeout);
          resolve();
        };

        processRef.once('close', onClose);

        // Check if it already died while we were setting up the listener
        if (processRef.exitCode !== null || processRef.killed) {
          clearTimeout(timeout);
          processRef.removeListener('close', onClose);
          resolve();
        }
      });

      console.error(`[Orchestrator] Process ${pid} confirmed dead`);
      this.currentWorkerProcess = null;
      this.workerStatus = 'idle';
      return true;
    } catch (e) {
      console.error('[Orchestrator] Failed to kill process:', e);
      // Don't null out currentWorkerProcess on failure — the process is still running
      return false;
    }
  }

  /**
   * Internal function to launch the Claude Code CLI worker
   * Configured to route through DeepSeek API (see SETUP.md for prerequisites).
   */
  private launchWorker(prompt: string, model: 'pro' | 'flash' = 'pro'): Promise<string> {
    // Fail loudly if DEEPSEEK_AUTH_TOKEN is not set
    const authToken = process.env.DEEPSEEK_AUTH_TOKEN;
    if (!authToken) {
      const errMsg = 'DEEPSEEK_AUTH_TOKEN environment variable is not set. '
        + 'Set it to your DeepSeek API key before starting the server. '
        + 'Example: $env:DEEPSEEK_AUTH_TOKEN="sk-..."';
      console.error(`[Orchestrator] ${errMsg}`);
      this.workerStatus = 'failed';
      this.workerError = errMsg;
      return Promise.reject(new Error(errMsg));
    }

    const modelId = model === 'flash' ? 'deepseek-v4-flash' : 'deepseek-v4-pro[1m]';

    return new Promise((resolve, reject) => {
      this.workerStatus = 'running';
      this.workerOutput = '';
      this.workerError = '';

      // Spawning the Claude CLI, routed through DeepSeek API.
      // Sanitize the prompt for cmd.exe safety, then wrap in double quotes
      const safePrompt = sanitizeForCmd(prompt);
      const quotedPrompt = `"${safePrompt}"`;
      const args = ['--dangerously-skip-permissions', '-p', quotedPrompt];

      // shell: true is required on Windows to run .cmd executables properly
      this.currentWorkerProcess = spawn('claude', args, {
        shell: true,
        cwd: process.cwd(), // Runs in the same project directory
        stdio: ['ignore', 'pipe', 'pipe'], // DO NOT inherit stdout, it breaks MCP
        env: {
          ...process.env,
          ANTHROPIC_BASE_URL: 'https://api.deepseek.com/anthropic',
          ANTHROPIC_AUTH_TOKEN: authToken,
          ANTHROPIC_API_KEY: '',
          ANTHROPIC_MODEL: modelId,
          ANTHROPIC_DEFAULT_OPUS_MODEL: modelId,
          ANTHROPIC_DEFAULT_SONNET_MODEL: modelId,
          ANTHROPIC_DEFAULT_HAIKU_MODEL: 'deepseek-v4-flash',
          CLAUDE_CODE_SUBAGENT_MODEL: 'deepseek-v4-flash',
          CLAUDE_CODE_EFFORT_LEVEL: 'max',
          CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: '1',
        },
      });

      const pid = this.currentWorkerProcess.pid;
      console.error(`[Orchestrator] Worker started with PID ${pid}`);

      this.currentWorkerProcess.stdout?.on('data', (data) => {
        this.workerOutput += data.toString();
      });

      this.currentWorkerProcess.stderr?.on('data', (data) => {
        this.workerError += data.toString();
        // Log to server stderr for debugging (invisible to MCP client data stream)
        console.error(`[Worker STDERR]: ${data.toString()}`); 
      });

      this.currentWorkerProcess.on('close', (code) => {
        console.error(`[Orchestrator] Worker ${pid} exited with code ${code}`);
        // Guard: if killWorkerProcess() already cleaned up, don't overwrite status
        if (this.currentWorkerProcess === null) {
          return;
        }
        this.currentWorkerProcess = null;

        if (code === 0) {
          this.workerStatus = 'completed';
          resolve(this.workerOutput);
        } else {
          this.workerStatus = 'failed';
          reject(new Error(`Worker exited with code ${code}.\nError Output:\n${this.workerError}`));
        }
      });

      this.currentWorkerProcess.on('error', (err) => {
        console.error(`[Orchestrator] Worker process error:`, err);
        // Guard: if killWorkerProcess() already cleaned up, don't overwrite status
        if (this.currentWorkerProcess === null) {
          return;
        }
        this.workerStatus = 'failed';
        this.currentWorkerProcess = null;
        reject(err);
      });
    });
  }

  private setupToolHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'start_worker',
          description: 'Starts the Worker Claude Code instance with a given prompt/batch task.',
          inputSchema: {
            type: 'object',
            properties: {
              prompt: { type: 'string', description: 'The task description or prompt to give the worker.' },
              mode: { type: 'string', enum: ['blocking', 'non-blocking'], description: 'Whether to wait for the worker to finish before responding.' },
              model: { type: 'string', enum: ['pro', 'flash'], description: 'Optional. Model to use: "pro" = deepseek-v4-pro[1m] (default), "flash" = deepseek-v4-flash (faster, lighter).' }
            },
            required: ['prompt', 'mode'],
          },
        },
        {
          name: 'get_worker_status',
          description: 'Checks the status of the background worker. Returns output if finished.',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'kill_worker',
          description: 'Forcefully terminates the currently running worker process.',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'wait',
          description: 'Blocks execution for the specified number of seconds. Use this to wait before polling for worker status in non-blocking mode (e.g., wait 5 seconds, then call get_worker_status).',
          inputSchema: {
            type: 'object',
            properties: {
              seconds: { type: 'number', description: 'Number of seconds to wait (max 300, i.e. 5 minutes).' },
            },
            required: ['seconds'],
          },
        },
      ],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      switch (request.params.name) {
        
        case 'start_worker': {
          const { prompt, mode, model } = request.params.arguments as { prompt: string; mode: 'blocking' | 'non-blocking'; model?: 'pro' | 'flash' };

          // Auto-kill previous worker and wait for it to fully die
          if (this.currentWorkerProcess || this.workerStatus === 'running') {
            const killed = await this.killWorkerProcess();
            if (!killed) {
              return {
                content: [{ type: 'text', text: 'Error: Failed to kill the previous worker process within 30 seconds. It may be stuck. Please try kill_worker again or manually terminate it.' }],
                isError: true,
              };
            }
          }

          // Validate prompt length after sanitization (2KB = 2048 bytes limit)
          const MAX_PROMPT_BYTES = 2048;
          const safePrompt = sanitizeForCmd(prompt);
          const promptByteLength = Buffer.byteLength(safePrompt, 'utf8');
          if (promptByteLength > MAX_PROMPT_BYTES) {
            return {
              content: [{
                type: 'text',
                text: `Error: The sanitized prompt is ${promptByteLength} bytes, which exceeds the ${MAX_PROMPT_BYTES}-byte (2KB) limit. `
                  + `Please write your detailed instructions to a file in the project directory (e.g., using the Write tool) and pass a short prompt that points the worker to that file instead. `
                  + `Example: "Read the instructions from .claude/worker-task.md and execute them."`,
              }],
              isError: true,
            };
          }

          if (mode === 'non-blocking') {
            // Launch and return immediately
            this.launchWorker(prompt, model).catch((err: Error) => {
              console.error(`[Orchestrator] Non-blocking worker failed: ${err.message}`);
            });
            return {
              content: [
                {
                  type: 'text',
                  text: `Worker successfully launched in background (Status: ${this.workerStatus}). Use get_worker_status to poll for results.`,
                },
              ],
            };
          } else {
            // Blocking mode
            try {
              const output = await this.launchWorker(prompt, model);
              return {
                content: [{ type: 'text', text: `Worker completed successfully.\n\nOutput:\n${output}` }],
              };
            } catch (error: any) {
              return {
                content: [{ type: 'text', text: `Worker failed:\n${error.message}` }],
                isError: true,
              };
            }
          }
        }

        case 'get_worker_status': {
          // Rate limit: don't allow polling more often than once every 15 seconds
          const now = Date.now();
          const POLL_COOLDOWN_MS = 15000;
          const elapsed = now - this.lastStatusPollTime;
          if (this.lastStatusPollTime !== 0 && elapsed < POLL_COOLDOWN_MS) {
            const waitSeconds = Math.ceil((POLL_COOLDOWN_MS - elapsed) / 1000);
            return {
              content: [{
                type: 'text',
                text: `Error: Polling too frequently. Only ${elapsed}ms since last status check — minimum cooldown is ${POLL_COOLDOWN_MS / 1000}s. `
                  + `Please use the wait command with seconds: ${waitSeconds} to wait before polling again, rather than calling get_worker_status in a tight loop.`,
              }],
              isError: true,
            };
          }
          this.lastStatusPollTime = now;

          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify({
                  status: this.workerStatus,
                  output: this.workerOutput.substring(this.workerOutput.length - 2000), // Return up to last 2000 chars to avoid massive payloads
                  error: this.workerError,
                }, null, 2),
              },
            ],
          };
        }

        case 'kill_worker': {
          const killed = await this.killWorkerProcess();
          if (killed) {
            return {
              content: [{ type: 'text', text: 'Worker process forcefully terminated.' }],
            };
          } else {
            return {
              content: [{ type: 'text', text: 'Error: Failed to kill the worker process within 30 seconds. It may be stuck. Please try again or manually terminate it.' }],
              isError: true,
            };
          }
        }

        case 'wait': {
          const { seconds } = request.params.arguments as { seconds: number };

          if (typeof seconds !== 'number' || seconds < 0 || seconds > 300) {
            return {
              content: [{ type: 'text', text: 'Error: seconds must be a number between 0 and 300 (5 minutes).' }],
              isError: true,
            };
          }

          console.error(`[Orchestrator] Waiting for ${seconds} seconds...`);
          await new Promise<void>(resolve => setTimeout(resolve, seconds * 1000));
          console.error(`[Orchestrator] Wait complete.`);

          return {
            content: [{ type: 'text', text: `Waited for ${seconds} second(s).` }],
          };
        }

        default:
          throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${request.params.name}`);
      }
    });
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('Claude Orchestrator MCP Server running on stdio');
  }
}

const server = new ClaudeOrchestratorServer();
server.run().catch(console.error);
