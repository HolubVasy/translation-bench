# translation-bench

Blind benchmark of LLM translators (Russian to English) judged by external
LLM reviewers. The goal is to pick the cheapest model that still translates
accurately and reads naturally, not to crown the strongest flagship.

## How it works

1. Convert. Each `.pdf` (or `.docx`) article is flattened into a JSON list of segments
   with structural ids (`S2-p3` = section 2, paragraph 3). Images become
   `[IMAGE_n]` placeholders and are restored by hand after the winner is chosen.
2. Translate. Every translator model (blind codes `M1..M5`) translates every
   article, returning the same JSON with translated `text` fields. Structure
   is validated and broken replies are retried.
3. Check. Numbers, URLs and placeholders are compared segment by segment,
   deterministically. The data criterion is covered without spending judge
   attention on it.
4. Judge. Every judge model (`J1..J3`) sees one article plus all its
   translations in a per-round shuffled order, scores six criteria, ranks the
   translations and flags concrete violations with segment ids.
5. Calibrate. A copy of one real translation gets three planted errors
   (negation, number, omission). Every judge reviews it blind; a judge that
   misses too many is left out of the overall tables.
6. Report. Pure arithmetic: criterion averages, Borda points from rankings,
   mechanical issue counts, real token spend per model and per judge, and a
   self-scoring check for any judge that is also a participant.
7. Assemble. The winning translation is written back into a .docx with the
   original images restored.

The code-to-model mapping lives only in `config.yaml` and never enters a prompt.

## Layout

    config.yaml          model lineup (M codes, J codes), prices, request settings
    skills/              prompt templates (string.Template, $placeholders)
      translator.md
      judge.md
    src/
      convert.py         docx -> data/source/a{n}.json
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
    tests/smoke.py       offline end-to-end test, runs in CI on every PR
    docs/ROADMAP.md      agreed and parked work
    run_all.py           stage runner

## Run

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    scripts/write_env.sh                 # on the VPS; elsewhere, fill .env by hand
    export $(cat .env)

    .venv/bin/python run_all.py full articles/1.pdf articles/2.pdf articles/3.pdf

Stages can be run one at a time: `convert`, `translate`, `check`, `judge`,
`calibrate`, `report`, `assemble`. Review `data/source/a*.json` once after
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
- Every change keeps `python tests/smoke.py` green; CI runs it on each PR,
  plus an ASCII check and an automatic Claude review.
- See `CLAUDE.md` for the working agreement with the assistant.
