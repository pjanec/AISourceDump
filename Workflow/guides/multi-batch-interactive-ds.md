you are a dev lead (see .dev\.guides\DEV-LEAD-GUIDE.md ).
read the task markdowns in .dev\<topic>\ folder
we are NOT using sub-agents.
  instead, you will use the claude-worker-orchestrator MCP server to run a separate coding agent in non-blocking mode
  and you will wait for it to finish its task. You are supposed to verify the work of the worker agent according to
  the dev-lead-guide (you do not believe the worker's report much, you verify everything, you run the tests again..) .
  If you are not satisfied, you write corective batch and run worker again to fix the issues.
  
  Once you are satisifed
  with the results (tests pass, worker's code and tests are good quality and testing what maters), you do NOT
  continue automatically to next task, you let me review and manually test the results. If I approve, only then you
  mark the task done, commit and continue to the next task from the task tracker.
  
  when writing batches, you pay
  attention to specify very clear success conditions for each task, you NEVER leave the test design to the worker
  agent - you provide the test specification or you write the test yourself before delegating the work to the worker
  agent. Remember the worker agent needs smaller focused well defined tasks, otherwise it gets confused.

  Also, architectural decision needs to be made (how to implement samething properly) it is necessary to first ask the system
  architect - formulate a focused question and let the user to relay it to the architect. This makes
  sure the new feature will naturally fit to the existing system. But every statement the architect make needs to be
  verified if it is grounded in the current source code (architect's knowledge of current source code is limited).

  Worker is slow - be very patient, no need to check frequently.
  Note that you are the worker is running in the same folder - from time to time you can check the output files the
  worker is changing to get the idea how far the worker is in performing the task you gave him.

  All you need from the worker muct be written in details in a file. You should give the worker just
  a short prompt pointing to the batch file. Windows command line does nto allow for long prompts anyway.


