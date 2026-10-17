# Plan, MVP-1

Approved by the owner on 17 Oct 2026. The milestone MVP-1 on GitHub holds
the P1 issues below; this file is the readable map, issues are the tasks.

Goals: G1 translation pipeline (#87), G2 known price and quality (#88),
G3 fast newcomer test (#89), G4 cost optimisation without quality loss (#90).
Priority: P1 next, P2 soon, P3 later. Principle: Python = deterministic
code, LLM = model or external translator call, costs money.

| # | What | Goal | Prio | Principle | API USD |
|---|---|---|---|---|---|
| 91 | Number check audit, false positives | G2 | P1 | Python | 0 |
| 99 | Qualification mode in the judge | G3 | P1 | Python | 0 |
| 100 | Judge M6 with Argon and Opus | G3 | P1 | LLM | ~0.65 |
| 101 | Tier and price of M6 | G2, G3 | P1 | Python | 0 |
| 102 | M6 against the tier holder | G4 | P1 | Python | 0 |
| 72 | Assemble docx, control characters | G1 | P1 | Python | 0 |
| 73 | Converter: headings, references, images | G1 | P1 | Python | 0 |
| 74 | Price estimate and account balance | G2 | P1 | Python | 0 |
| 93 | Process documentation | all | P1 | Python | 0 |
| 62 | Issue rule in CLAUDE.md | all | P1 | Python | 0 |
| 20 | Baseline Google Translate and DeepL | G3, G4 | P1 | LLM | 0 |
| 60 | Sortable report table | G2 | P1 | Python | 0 |
| 105 | Testing by checks | all | P1 | Python | 0 |
| 67 | Two-pass cheap pipelines | G4 | P1 | LLM | ~1.5 |
| 68 | Argon plus Opus, tier best | G1, G4 | P1 | LLM | ~1.2 |
| 76 | Argon against Sonnet before 30 Nov | G4 | P1 | LLM | ~1.0 |
| 75 | Price per vendor tokenizer | G2 | P2 | Python | 0 |
| 65 | Terminology consistency script | G2 | P2 | Python | 0 |
| 71 | Blind reading for the owner | G2 | P2 | Python | 0 |
| 66 | Pre-filter of weak candidates | G3 | P2 | Python + LLM | ~0.3 |
| 19 | Prices from the OpenRouter API | G2 | P2 | Python | 0 |
| 22 | Gate thresholds | G2 | P2 | Python | 0 |
| 61 | Owner-guided chief editor | G1 | P2 | LLM | ~1 per article |
| 64 | Ten criteria | G2 | P3 | LLM | as judging |
| 70 | Summary mode | G1 | P3 | LLM | ~0.01 per article |
| 63 | Pairwise judging | G3 | P3 | LLM | 8..10 |
| 92 | Judges per aspect | G2 | P3 | LLM | x aspects |

P1 total: about 4.4 USD of API spend.

Codes: M2 Gemini 4 Argon, M6 Gemini 3.8 Flash.
