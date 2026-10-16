# translation-bench

Blind benchmark of LLM translators (RU to EN) with external LLM judges.

## Design

- Articles are .docx. The converter flattens them into JSON segments with
  structural ids (S2-p3 = section 2, paragraph 3). Images become [IMAGE_n]
  placeholders; put them back after choosing the winner.
- 5 translator models (blind codes M1..M5, see config.yaml) each translate
  every article. The code-to-model mapping never enters any prompt.
- Deterministic checks (numbers, URLs, placeholders) cover the data
  criterion without spending judge attention on it.
- 3 judge models each see one article plus all its translations in a
  per-round shuffled order and return scores on 6 criteria, a ranking and
  violation flags per segment.
- Aggregation is pure arithmetic: averages, Borda points from rankings,
  cost per model from real token usage, and a self-scoring check for the
  judge that is also a participant.

## Run

    pip install -r requirements.txt
    cp .env.example .env   # put your OpenRouter key there
    export $(cat .env)

    python run_all.py full articles/1.docx articles/2.docx articles/3.docx

Or stage by stage: convert, translate, check, judge, report.
Translate and judge skip already existing outputs, so a failed run is
resumed by running the same command again.

The report lands in data/report/summary.md.

## Interpreting results

- 3 articles is a small sample: a 1-2 point gap in totals is noise, a gap
  in Borda plus agreement of all judges is signal.
- Trust a flag only if two judges raised it or you verified the quote.
- The self-scoring section shows whether the participant-judge inflates
  its own translation; if it does, read the per-judge table instead of
  the overall one.

## Skills

The prompt texts live in skills/translator.md and skills/judge.md as
string.Template files ($placeholders). Edit the wording there; the code
only substitutes values. config.yaml holds the model lineup (blind codes
M1..M5, judges J1..J3) and prices; swapping a model is a one-line change
and does not touch any prompt or code.
