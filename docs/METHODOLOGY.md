# Methodology

A leaderboard tells you who is strongest. This tells you who is enough, and
what enough costs. The method finds, for your own documents, the cheapest
translation setup that holds each of three quality tiers, and shows where it
fails.

## 1. Definitions

- Document: one source text, split into segments with stable ids
  (`S2-p3` = section 2, paragraph 3).
- Translator: any model or service that turns a document into the target
  language. Shown to judges only as a blind code (M1, M2, ...).
- Judge: a model that scores translations. Shown only as a blind code
  (J1, J2, ...). Judges never learn which model wrote which translation.
- Verdict: one judge's scores for all translations of one document.
- Criterion: one of six scored properties (section 3).
- Tier: a promise about what the reader gets (section 6).
- Guarantee: the tier a translator holds on its worst document.

## 2. Pipeline

1. Convert. Each PDF or DOCX becomes a list of segments; images become
   placeholders.
2. Translate. Every translator translates every document as a whole, so it
   can keep terminology consistent.
3. Check. Deterministic scripts compare each translation with the source:
   missing or extra segments, changed numbers, untranslated fragments,
   glossary terms. A translation that fails a hard gate scores 0 on that
   document.
4. Calibrate. Each judge first scores a translation with planted errors
   (section 4). A judge that misses too many is excluded.
5. Judge. Each judge reads the source and all translations of a document at
   once and scores every translation on the six criteria, ranks them and
   quotes concrete errors.
6. Report. Averages per criterion, ranking, judge agreement, self-judging,
   tiers, price.

## 3. Criteria

Each scored 0 to 10. Anchors: 10 flawless, 8 minor issues, 5 noticeable
errors but meaning intact, 2 serious distortions, 0 failed.

| Criterion | What it checks |
|---|---|
| meaning | every statement keeps its meaning, including negation, modality, who did what |
| completeness | nothing omitted, nothing added |
| data | numbers, dates, names, links match the source exactly |
| naturalness | reads like a native text, no calque |
| flow | coherent, good rhythm, one terminology across the document |
| clean | no untranslated fragments, no meta text, placeholders kept |

The total out of 60 is an orientation, not a verdict: the six criteria have
equal weight, which is a simplification. Decisions use the criteria
themselves (section 6).

## 4. Judges

- Calibration: before judging, every judge gets one translation with five
  planted errors: a flipped negation, a changed number, a dropped sentence,
  a swapped modal verb, a changed quantifier. It must catch at least three.
- Diversity: judges come from different vendors; vendor diversity matters
  more than the strength of one judge.
- Self-judging: when a judge's own model is also a translator, its verdicts
  on that translation are reported separately and compared with the other
  judges.
- Position bias: an optional second pass presents translations in reversed
  order.

## 5. Price

Actual cost per call is taken from the provider, not estimated. Prices are
compared per 1000 source words and at list price; promotional prices are
not used for decisions because they end.

## 6. Tiers and the guarantee

| Tier | Promise to the reader | Thresholds (0 to 10) |
|---|---|---|
| Rough | grasp what the document says | completeness 8+, meaning 7+ |
| Optimized | accurate and citable, plain wording | meaning 9+, completeness 9+, no number mismatches, naturalness 7+ |
| Comfortable | long work with the text is pleasant | Optimized plus naturalness 9+, flow 9+, one terminology |
| Best | maximum quality, price secondary | highest measured |

A translator holds a tier only if every document meets the thresholds: the
guarantee is the worst document, not the average. For each tier the winner
is the cheapest setup that holds it. A setup may be a single model or a
pipeline (for example a translator plus a cheap editor), measured as one
unit.

## 7. Limits

- Judges are models. Calibration shows they read the text, not that they
  agree with a human expert.
- A small document set and one run give an order, not a spread. More
  documents give a firmer guarantee.
- Adding a translator means every judge scores all translations of a
  document again; adding a judge does not.
- Results hold for the documents, language pair and prompts used. Run it on
  your own documents; that is the point of the method.
