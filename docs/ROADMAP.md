# Roadmap

Work that is agreed or proposed but not yet built. Each item has a status,
the reason it exists and what done looks like. Items move to "Done" with a
link to the PR that closed them.

Status values: planned (agreed, waiting for its turn), parked (worth doing,
not now), idea (proposed, not yet agreed).

## Planned

### R1. Value metric: quality per dollar
Status: planned, ships with the first real run.
Why: three columns (accuracy, completeness, cost) start a debate; one number
answers "which model to take".
Done when: report has a `value` column = weighted quality / cost per 1K
source words, sorted by it. Weights in config.yaml, default meaning 0.4,
completeness 0.2, data 0.2, naturalness 0.2.

### R2. Commit source JSON of each run
Status: planned, ships with the first real run.
Why: a run must be reproducible; the converted sources are its input.
Done when: data/source/a*.json of the run is committed through a PR, images
stay out of git.

## Parked

### R3. Noise floor measurement
Status: parked (tuning).
Why: with three articles the main risk is mistaking run-to-run noise for a
difference between models.
Idea: translate one article twice with the same model, let the judges score
both as different translators. The gap between the two runs is the noise
floor; a gap between models below it is not a gap.
Done when: report shows the noise floor next to the ranking.

### R4. Owner's blind reading
Status: parked, after the first run.
Why: checks that the judges' taste matches the owner's. If it does not, the
criteria or the weights are tuned to the wrong reader.
Idea: the owner reads the two best translations of one article, codes only,
and gives his own order. No code needed beyond a small helper that prints
the two texts side by side.
Done when: agreement or disagreement with the judges is recorded here.

### R5. Branch protection on main
Status: parked, needs the owner's explicit go-ahead.
Why: the PR-only rule in CLAUDE.md is held by discipline, not by GitHub.
Note: classic branch protection on a private repository may require GitHub
Pro; check before enabling.

## Ideas

### R6. Two-column PDF and tables
Status: idea.
Why: the PDF converter reads layout heuristically; two-column pages and
tables may come out in the wrong order.
Done when: converter detects columns by block x-position and emits tables
as one segment per row.

### R7. Calibration on more than one article
Status: idea.
Why: one decoy is a cheap sanity check, not a measurement of judge recall.
Done when: calibration takes a list of articles and reports catch rate.

## Done

- PR-only rule, README, CLAUDE.md: PR #1.
- PDF input, judge calibration with planted decoy, docx assembly, CI smoke
  test and Claude review: PR #2.
