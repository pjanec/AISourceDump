These are the architecture and design documents of the system we are going to break into tasks:

  architecture.md
  detailed_design.md


Process these according to Design-From-Talk.md  guide.

Do not create new design documents, use the already existing ones.
Create just TASK-DETAIL.md and TASK-TRACKER.md in the same folder as the design docs.
If the TASK-DETAIL.md and TASK-TRACKER.md  already exists, update/append.

Generate tasks for each detailed design document. Group tasks into phases as necessary
(if not already prescribed in the design docs).

Do not process long design doc at once, the subagent might hit the output leght limit - the
blocks must me reasonably sized. Give instruction to create a set of tasks (the block) for selected part
of the design document at a time by delegating to a development subagent, use model Claude Sonnet 4.6;
tell him the context (architecture, previous design doc) so he knows what he is designing;
he should continue adding task to the shared TASK-DETAIL and TASK-TRACKER.

If subagent is done with one block, you move to next part of design and repeat this delegating process
until all design documents are covered.

Pay attantion to defining clear success conditions (test cases) so that the developer who will be implementing
the tasks knows exactly when his job is considered done.

At the end of each block, do not forget to continue by delegating the next one to another subagent using same model.

Reference the individual detailed design documents from the tasks,
do not duplicate information to the tasks if the can be referenced.

Similarly reference the architecture document (together with its inline patches) wherever needed,
no duplication.
