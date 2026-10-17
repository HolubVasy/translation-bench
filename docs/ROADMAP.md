# Roadmap

The plan, in waves. Each wave is a GitHub issue with one sub-issue per
item; this file is the map, the issues are the tasks. Numbers in
parentheses refer to the owner's review of the 55 proposals (October 2026).

## Wave 0. Baseline run

Run the benchmark on three real PDF articles with the code as it stands.
Every later decision is checked against these numbers.

## Wave 1. Validity (release 1, in progress)

Shipped in release 1:
- Deterministic gates before judging: length ratio, source-script
  residue, glossary violations, missing segments; list marker and glossary
  segment checks (4', 13, 29).
- Glossary in the translator and judge prompts and checked by script (7, 31).
- Reversed second judge pass and Kendall tau between judges and between a
  judge's two passes (5, 6).
- Subtle decoys: modality and quantifier planters next to the coarse ones;
  catch rate per kind in the report (10).
- Latency per call in the report (40).
- Preflight: config and skill validation, cost estimate, budget guard, run
  manifest with model ids and skill hashes (16, 17, 20, 21).
- Hardened JSON extraction and unit tests for every logic function.

Still in wave 1:
- Prices pulled from the OpenRouter models endpoint (12).
- DeepL and Google Translate as extra translators M7, M8 (54).
- Cheap-model pre-screen of critical errors before expensive judges (13).

## Wave 2. Scale and robustness

MQM error categories with severity weights (8, 9), back-translation check
(2), structured output where the provider supports it (18), Pydantic
protocols (24), retries with jitter (23), parallel requests (19), PDF
converter tests on real pages (25), Dependabot, pre-commit hook, skill
versioning (42, 43, 45).

## Wave 3. Accumulation

SQLite index and a folder per run (22), pairwise comparisons so a new
model does not require re-judging old ones (1), reference translation and
COMET or chrF (3, 4), static HTML pages: segmentation preview, report,
quality-vs-cost chart, side-by-side view (26, 37, 38, 39), tables in PDF,
captions, PDF output (27, 35, 36).

## Wave 4. Product

Web UI on the VPS (48), the two-pass pipeline registered as a translator
and later as its own product (33, 52), three variants per paragraph (53),
style guide as a prompt setting (32), quality by text length (51), more
input formats (28), notifications and Telegram (49, 55), Notion page per
run (41), other language pairs (50).

## Dropped

PR template (44) and a GitHub Actions run button (46): the owner valued
them below the web UI.

## Done

- PR-only rule, README, CLAUDE.md: PR #1.
- PDF input, judge calibration with planted decoy, docx assembly, CI smoke
  test and Claude review: PR #2.
- Roadmap and docs: PR #3. Merge policy: PR #4.
- Review findings on spend, self-scoring, calibration fallback, actual
  spend from the OpenRouter key: PR #5.
