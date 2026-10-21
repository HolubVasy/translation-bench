# translation-bench

Blind benchmark of LLM translators (English to Russian) judged by other
LLMs, each judge checked first on planted errors. The goal is not to crown the
strongest model but to find who is good enough for a given level of service,
and what that costs. Run it on your own documents and you get your own answer.

Live results: https://holubvasy.github.io/translation-bench/

## Before you start

1. Python 3.10 or newer (tested on 3.12). Check with `python3 --version`.
2. An OpenRouter account with credit and an API key (openrouter.ai, Keys).
   One key opens every model in `config.yaml`. With the current lineup a full
   run on three papers of about 6000 words each costs about 6.5 USD
   (15 translations, 45 verdicts, judge calibration).
3. Git, to clone the repository.
4. Optional: a GitHub account if you fork it. GitHub Actions runs the offline
   tests on every pull request and needs no key.

## How it works

1. Convert. Each `.pdf` (or `.docx`) article is flattened into a JSON list of segments
   with structural ids (`S2-p3` = section 2, paragraph 3). Images become
   `[IMAGE_n]` placeholders and are restored by hand after the winner is chosen.
2. Translate. Every translator model (blind codes such as `M2`, `M5`) translates every
   article, returning the same JSON with translated `text` fields. Structure
   is validated and broken replies are retried.
3. Check and gate. Numbers, URLs, placeholders, list markers, glossary
   terms and source-script residue are compared segment by segment,
   deterministically. Gates (length ratio, residue, glossary violations,
   missing segments) disqualify a translation before any judge sees it.
4. Judge. Every judge model (`J1`, `J3`, `J4`) sees one article plus all its
   admitted translations in a seeded shuffled order, scores six criteria,
   ranks them and flags concrete violations with segment ids. With
   `judging.double_pass` the judge sees the same set again in reversed order,
   so the report can measure position bias.
5. Calibrate. A copy of one real translation gets planted errors, coarse and
   subtle (number, omission, negation, modality, quantifier). Every judge
   reviews it blind; a judge that misses too many is left out of the
   overall tables, and the report shows which kinds each judge caught.
6. Report. Pure arithmetic: criterion averages, Borda points from rankings,
   mechanical issue counts, real token spend per model and per judge, and a
   self-scoring check for any judge that is also a participant.
7. Assemble. The winning translation is written back into a .docx with the
   original images restored.

The code-to-model mapping lives only in `config.yaml` and never enters a prompt.

## Layout

    config.yaml          model lineup, prices, gates, judging, budget, calibration
    glossary.example.yaml  term list format; copy to glossary.yaml and set `glossary:`
    skills/              prompt templates (string.Template, $placeholders)
      translator.md
      judge.md
    src/
      preflight.py       config and skill validation, cost estimate, run manifest
      convert.py         pdf or docx -> data/source/a{n}.json
      translate.py       -> data/translations/tr__a{n}__M{k}.json
      mech_check.py      -> data/checks/mech__a{n}__M{k}.json
      judge.py           -> data/judgments/ev__a{n}__by__J{k}.json
      calibrate.py       -> data/calibration/ (answer key, judge results)
      aggregate.py       -> data/report/summary.md
      assemble.py        -> data/report/assembled__a{n}__M{k}.docx
      openrouter.py      API client, JSON extraction
      prompts.py         fills the skill templates
    scripts/
      read_openrouter_key.sh   reads the key LibreChat already uses (masked)
      write_env.sh             copies it into .env and validates it
    tests/               unit tests (pytest) and smoke.py, offline, run in CI on every PR
    docs/STYLE.md        code style, five rules
    docs/ROADMAP.md      agreed and parked work
    tools/
      export_session.py  run results -> docs/data/sessions/<date>/ (public protocol, no text)
      build_report.py    page plus latest session -> data/report/report.html
    docs/index.html      the showcase page, served by GitHub Pages
    run_all.py           stage runner

## Run

    git clone https://github.com/HolubVasy/translation-bench.git
    cd translation-bench
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    cp .env.example .env                 # put your OpenRouter key into .env
    export $(cat .env)

    # put your documents (.pdf or .docx) into articles/
    .venv/bin/python run_all.py full articles/1.pdf articles/2.pdf articles/3.pdf

On Windows use `.venv\Scripts\python` instead of `.venv/bin/python` and set
the key with `set OPENROUTER_API_KEY=...`.

What you get:

- `data/report/report.html` is the same interactive page as the live one,
  with your numbers. It opens with a double click, no server needed.
- `data/report/summary.md` holds the full tables, spend and judge checks.
- `docs/data/sessions/<date>/` is the public protocol of the run: scores,
  remark types, prices and token counts, no source or translated text.

Cost warning. Preflight prints a cost estimate and stops above
`budget.max_usd`. The estimate is currently too low for Russian output, by
about five times (issue #74). Plan for the real cost from "Before you start"
and set `budget.max_usd` with that margin.

Stages can be run one at a time: `convert`, `preflight`, `translate`, `check`,
`judge`, `calibrate`, `report`, `assemble`. Preflight validates config and
skills, prints a cost estimate and stops when it exceeds `budget.max_usd`
(`--force` overrides). Review `data/source/a*.json` once after
`convert`: PDF structure is recovered from layout. Translate and judge skip outputs that already exist, so a failed
run is resumed by repeating the same command.

## Changing the lineup

Add or swap a model by editing `config.yaml` only: one line in `translators`
or `judges`, one line in `prices` or `judge_prices`. The code adapts to any
number of models. Verify exact OpenRouter model ids before the first run.

## Reading the report

- Three articles is a small sample. A gap of one or two points in totals is
  noise; a gap in Borda confirmed by all judges is signal.
- Trust a flag only if two judges raised it or the quote was checked by hand.
- If the self-scoring section shows a judge inflating its own translation,
  read the per-judge table instead of the overall one.
- Spend is computed from real token usage and the prices in `config.yaml`;
  a missing price produces a warning, not a silent zero.

## Contributing

- Every change goes through a Pull Request into `main`. The assistant
  merges it once CI and the Claude review are clean (see `CLAUDE.md`). The only exception
  is secret configuration (`.env`), which is never committed at all.
- Code, prompts and config are ASCII only.
- Every change keeps `python -m pytest` and `python tests/smoke.py` green; CI
  runs both on each PR, plus an ASCII check and an automatic Claude review.
- Code follows `docs/STYLE.md`.
- See `CLAUDE.md` for the working agreement with the assistant.
