# Process

How work is done on this repository by any executor, a person or an agent of
any vendor. The tool does not matter; the board and the repository carry the
state.

## 1. Definitions

- Executor: whoever does the work, a person or an agent of any vendor.
- Board: the single list of tasks with priority and status. Today GitHub
  Issues; Azure Boards after issue #125.
- Task: one item on the board with a goal, acceptance criteria and a status.
- Success: a step whose check has passed (a test is green, a command has run,
  a pull request is open), never "worked for an hour".
- Checkpoint: a comment on the task written after every success, with the
  fields of section 3.
- Escalation: a message to the owner that stops the executor on that task.

## 2. Loop

1. Take the next task by priority. Set it In progress.
2. Read the context: the task, its last checkpoint, linked pull requests,
   AGENTS.md.
3. Write the plan of the change and the acceptance criteria into the task if
   they are missing.
4. Critique the plan once: risks, five possible improvements, keep only those
   that serve the goal of the task.
5. Make the change on a branch. Every change comes with tests.
6. After every success write a checkpoint and push the branch.
7. Open a pull request that names the task. Merge by rule 10 of CLAUDE.md:
   CI green and a review with no confirmed findings.
8. Check every acceptance criterion. Close the task and set its status.
9. Report to the owner in one line: task, result, link.
10. If the process or the layout of the repository changed, update AGENTS.md.
11. A failure goes into a comment (what failed, what was tried). The same
    attempt is not repeated a third time.

## 3. Checkpoint fields

- Done: what is finished and verified.
- Next: the one next step.
- Blockers: what is in the way, or none.
- Branch and PR: where the code is.
- How to verify: the command or the check that proves the Done line.

Uncommitted work is invisible to the next executor, so the branch is pushed
before the checkpoint is written.

## 4. Escalation

The executor stops and asks the owner when the work would:

- spend money above the cap of section 5;
- add a mechanism that the task does not describe;
- contradict a recorded principle;
- need a secret or an authorization only the owner can give;
- fail twice in the same way;
- carry a legal or copyright risk.

## 5. Spend

Every paid run has an estimate and a cap before it starts. Unless the task
says otherwise the caps are 1 USD per task and 5 USD per day. Above a cap the
executor stops and asks. Expensive models are not used without a measured
reason.

## 6. Where things live

- Tasks and checkpoints: the board.
- Code, branches, pull requests, approved decisions: this repository.
- Drafts, analysis and results for reading: Notion. An executor needs nothing
  from Notion to do a task; the task points to what is needed.
