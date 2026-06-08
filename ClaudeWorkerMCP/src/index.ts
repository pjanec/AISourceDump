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

type WorkerStatus = 'idle' | 'running' | 'completed' | 'failed';

class ClaudeOrchestratorServer {
  private server: Server;
  private currentWorkerProcess: ChildProcess | null = null;
  private workerStatus: WorkerStatus = 'idle';
  private workerOutput: string = '';
  private workerError: string = '';

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
   * Hard kills the Windows process tree.
   * Required because shell: true spawns a cmd.exe which spawns the actual tool.
   */
  private async killWorkerProcess(): Promise<void> {
    if (this.currentWorkerProcess && this.currentWorkerProcess.pid) {
      try {
        console.error(`[Orchestrator] Killing process tree for PID ${this.currentWorkerProcess.pid}`);
        // Windows specific task kill
        await execAsync(`taskkill /pid ${this.currentWorkerProcess.pid} /t /f`);
      } catch (e) {
        console.error('[Orchestrator] Failed to kill process:', e);
      }
      this.currentWorkerProcess = null;
      this.workerStatus = 'idle';
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
      // Wrap prompt in quotes for Windows cmd.exe (shell: true) to preserve spaces
      const quotedPrompt = `"${prompt.replace(/"/g, '\\"')}"`;
      const args = ['-p', quotedPrompt, '--dangerously-skip-permissions'];

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
      ],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      switch (request.params.name) {
        
        case 'start_worker': {
          const { prompt, mode, model } = request.params.arguments as { prompt: string; mode: 'blocking' | 'non-blocking'; model?: 'pro' | 'flash' };

          // Auto-kill previous worker
          if (this.currentWorkerProcess || this.workerStatus === 'running') {
            await this.killWorkerProcess();
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
          await this.killWorkerProcess();
          return {
            content: [{ type: 'text', text: 'Worker process forcefully terminated.' }],
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
