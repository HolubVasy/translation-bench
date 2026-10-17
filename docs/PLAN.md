# Plan, MVP-1

Approved by the owner on 17 Oct 2026. The GitHub milestone MVP-1 holds the P1
issues; this file is the readable map, issues are the tasks.

## Goals

| Code | Issue | Goal | Done when |
|---|---|---|---|
| G1 | #87 | Translation pipeline for real use | one command turns a PDF into a typeset Russian docx |
| G2 | #88 | Known price and quality for every job | price list of four tiers, actual cost within 30 percent |
| G3 | #89 | Fast test of a new model | a newcomer gets its tier in an hour for about 2 USD |
| G4 | #90 | Cost optimisation without quality loss | each tier served by its cheapest qualifying setup |

Priority: P1 next, P2 soon, P3 later. Principle: Python = deterministic
code; LLM = model or external translator call, costs money.

## Plan

| # | What | Goal | Prio | Principle | API USD | How it is tested |
|---|---|---|---|---|---|---|
| 91 | Number check audit | G2 | P1 | Python | 0 | regression set #108 |
| 99 | Qualification mode in the judge | G3 | P1 | Python | 0 | unit test: old judgments untouched |
| 100 | Judge M6 with Argon and Opus | G3 | P1 | LLM | ~0.65 | decoy calibration, spend cap 1 USD |
| 101 | Tier and price of M6 | G2, G3 | P1 | Python | 0 | unit test of thresholds on fixtures |
| 102 | M6 against the tier holder | G4 | P1 | Python | 0 | result line checked against #101 |
| 72 | Assemble docx, control characters | G1 | P1 | Python | 0 | unit test plus three real articles |
| 73 | Converter: headings, references, images | G1 | P1 | Python | 0 | golden files #107 |
| 74 | Price estimate and account balance | G2 | P1 | Python | 0 | estimate vs bill #109 |
| 93 | Process documentation | all | P1 | Python | 0 | owner review |
| 62 | Issue rule in CLAUDE.md | all | P1 | Python | 0 | owner review |
| 20 | Baseline Google Translate and DeepL | G3, G4 | P1 | LLM | 0 | live smoke #111, deterministic checks |
| 60 | Sortable report table | G2 | P1 | Python | 0 | snapshot #110 |
| 105 | Testing by checks (umbrella) | all | P1 | Python | 0 | closes with #107-#111 |
| 107 | Check: converter golden files | G1 | P1 | Python | 0 | seeded failing case |
| 108 | Check: number regression set | G2 | P1 | Python | 0 | seeded failing case |
| 109 | Check: estimate vs bill | G2 | P1 | Python | 0 | seeded failing case |
| 110 | Check: report snapshot | G2 | P1 | Python | 0 | seeded failing case |
| 111 | Check: live API smoke | G3 | P1 | LLM | <0.01 | wrong model id must stop preflight |
| 67 | Two-pass cheap pipelines | G4 | P1 | LLM | ~1.5 | tier thresholds, vs single Sonnet |
| 68 | Argon plus Opus, tier best | G1, G4 | P1 | LLM | ~1.2 | tier thresholds, vs single Argon |
| 76 | Argon against Sonnet before 30 Nov | G4 | P1 | LLM | ~1.0 | qualification of both on one article |
| 75 | Price per vendor tokenizer | G2 | P2 | Python | 0 | estimate vs bill #109 |
| 65 | Terminology consistency script | G2 | P2 | Python | 0 | unit tests on seeded inconsistencies |
| 71 | Blind reading for the owner | G2 | P2 | Python | 0 | key opens only after the verdict |
| 66 | Pre-filter of weak candidates | G3 | P2 | Python + LLM | ~0.3 | replay on 17 Oct data |
| 19 | Prices from the OpenRouter API | G2 | P2 | Python | 0 | unit test, network mocked |
| 22 | Gate thresholds | G2 | P2 | Python | 0 | replay on 17 Oct data |
| 61 | Owner-guided chief editor | G1 | P2 | LLM | ~1 per article | owner reading |
| 64 | Ten criteria | G2 | P3 | LLM | as judging | judge agreement per criterion |
| 70 | Summary mode | G1 | P3 | LLM | ~0.01 per article | owner reading |
| 63 | Pairwise judging | G3 | P3 | LLM | 8..10 | agreement with listwise ranking |
| 92 | Judges per aspect | G2 | P3 | LLM | x aspects | agreement with the general judge |

P1 total: about 4.4 USD of API spend.

## Codes

| Code | Meaning |
|---|---|
| M2 | Gemini 4 Argon |
| M6 | Gemini 3.8 Flash |
