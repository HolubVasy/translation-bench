# CLAUDE.md

Working agreement for Claude (and any other assistant) in this repository.

## What this project is

A blind benchmark of LLM translators (RU to EN) with external LLM judges.
Read `README.md` first: it describes the five stages, the file layout and
how to read the report. This file covers how to work on the code.

## Rules

1. Pull Requests only. Every change that is not secret configuration goes
   through a branch and a Pull Request into `main`. No direct pushes to
   `main`, including documentation and config edits. Secret configuration
   means `.env` and nothing else; it is gitignored and is never committed,
   so it never needs a PR either.
2. Secrets never enter git, logs, reports or chat. Keys are read from the
   environment. When a key must be shown, show it masked
   (`scripts/read_openrouter_key.sh` does this).
3. ASCII only in code, prompts, config and generated files. No Cyrillic, no
   em-dashes, no unicode arrows or symbols. Russian is for conversation, not
   for the repository.
4. Follow the patterns already next to the change. Reuse the existing
   mechanisms (config dictionaries, skill templates, stage runner). A new
   table, module, stage or external dependency needs explicit approval from
   the owner before it is written.
5. Every code change comes with a check. `tests/smoke.py` stays green and
   is extended when a stage changes; CI runs it on each PR. `data/`
   subfolders stay empty in git.
6. Config over code. Models, prices, languages and request settings live in
   `config.yaml`; prompt wording lives in `skills/`. If a change can be made
   there, it is not made in `src/`.
7. Blindness is a hard invariant. Real model names never appear in anything
   a translator or judge model receives: not in prompts, not in file names
   passed along, not in segment text. Only `M` and `J` codes.
8. Determinism where possible. Arithmetic (averages, Borda, spend) is done by
   `aggregate.py`, never delegated to a model. Shuffles are seeded.
9. Planned and parked work lives in `docs/ROADMAP.md`. Ideas found while
   working go there instead of into the current PR.
10. Merge policy. The assistant merges its own PRs without asking, once
    the smoke test and the ASCII check are green and the Claude review has
    0 confirmed findings (a VERIFIED comment with C = 0, or a REVIEW with
    0 findings). Any confirmed finding, a red check, or a review that did
    not actually run (step finished in seconds) stops the merge and goes
    to the owner.
11. Findings are tasks, in GitHub Issues. Every confirmed review finding
    and every bug found while working becomes an issue in this repository
    (title, file:line, scenario). The fixing PR says `Fixes #N` so the
    issue closes on merge. Fixing continues until the review is clean;
    only then the merge policy applies. Issues are the task list; the plan
    lives in `docs/ROADMAP.md` and links to issues, never the other way.
12. Review loop limit. After three review rounds on one PR that each
    produce only Low findings, the remaining Lows become issues and the
    PR merges. A Medium or High finding always blocks.
13. Code style is `docs/STYLE.md`. In short: one function does one job and
    fits on a screen, names are verbs for functions and nouns for data,
    IO at the edges and logic in the middle, extend by adding a registry
    entry rather than a class, every logic function has an offline test.

## Before proposing a change

- State the problem in one or two lines, then two implementation options
  with a risk for each, and wait for the owner's choice.
- Name the files to be touched and whether a config-only solution exists.

## Working on the VPS

- Repository path: `~/workspace/translation-bench`, virtualenv in `.venv`.
- Checks: `python -m pytest` (unit) and `python tests/smoke.py` (end to end, offline).
- The OpenRouter key is taken from the LibreChat container with
  `scripts/write_env.sh`. Do not copy it anywhere else.
- Remote: `https://github.com/HolubVasy/translation-bench` (private).
- Branch naming: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`.

## Definition of done for a PR

- Unit tests and the smoke test pass; a new logic function brings its test.
- `README.md` updated if the workflow or layout changed.
- Commit message says what changed and why, in one line plus bullets.
