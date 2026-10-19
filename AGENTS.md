# AGENTS.md

Read this first, whatever tool you are.

translation-bench is a blind benchmark of LLM translators on your own
documents. It finds the cheapest setup that holds each of three quality tiers
and reports the result as tables and prices.

- Process: docs/PROCESS.md (take a task, plan, critique, change, checkpoint,
  pull request, report).
- State: the task on the board and its last checkpoint comment; the code state
  is the pushed branch. Do not rely on chat history.
- Rules: CLAUDE.md applies to every executor, not only to Claude (changes by
  pull request, ASCII only in code and config, models never see their names,
  tests stay green).
- Methodology: docs/METHODOLOGY.md. Plan: docs/PLAN.md.
- Run the checks: python tests/smoke.py and python -m pytest.
- Stop and ask the owner in the cases of section 4 of docs/PROCESS.md.
