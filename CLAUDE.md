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
10. Merge policy. The assistant merges its own PRs without asking, once
    the smoke test and the ASCII check are green and the Claude review has
    0 confirmed findings (a VERIFIED comment with C = 0, or a REVIEW with
    0 findings). Any confirmed finding, a red check, or a review that did
    not actually run (step finished in seconds) stops the merge and goes
    to the owner.
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
9. Planned and parked work lives in `docs/ROADMAP.md`. Ideas found while
   working go there instead of into the current PR.
6. Config over code. Models, prices, languages and request settings live in
   `config.yaml`; prompt wording lives in `skills/`. If a change can be made
   there, it is not made in `src/`.
7. Blindness is a hard invariant. Real model names never appear in anything
   a translator or judge model receives: not in prompts, not in file names
   passed along, not in segment text. Only `M` and `J` codes.
8. Determinism where possible. Arithmetic (averages, Borda, spend) is done by
   `aggregate.py`, never delegated to a model. Shuffles are seeded.

## Before proposing a change

- State the problem in one or two lines, then two implementation options
  with a risk for each, and wait for the owner's choice.
- Name the files to be touched and whether a config-only solution exists.

## Working on the VPS

- Repository path: `~/workspace/translation-bench`, virtualenv in `.venv`.
- The OpenRouter key is taken from the LibreChat container with
  `scripts/write_env.sh`. Do not copy it anywhere else.
- Remote: `https://github.com/HolubVasy/translation-bench` (private).
- Branch naming: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`.

## Definition of done for a PR

- Stage smoke run passed and artifacts cleaned.
- `README.md` updated if the workflow or layout changed.
- Commit message says what changed and why, in one line plus bullets.
