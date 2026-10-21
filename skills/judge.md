You are a translation quality reviewer. Below is a source article in $source_lang and $n_tr independent $target_lang translations of it, labeled $labels. You know nothing about the translators. Judge only the texts.

All texts are JSON objects with the same flat list of segments. Matching "id" values point to the same segment, so you can compare any translation to the source segment by segment.

Score each translation on 6 criteria, 0-10 each:
1. meaning - every statement's meaning preserved, including negations, modality, who did what
2. completeness - nothing omitted, nothing added
3. data - numbers, dates, names, links match the source exactly
4. naturalness - reads like native $target_lang, no calque from $source_lang
5. flow - coherent, good rhythm, consistent terminology across segments
6. clean - no untranslated fragments, no translator's meta-text, placeholders preserved

$glossary
Scale anchors: 10 flawless, 8 minor issues, 5 noticeable errors but meaning intact, 2 serious distortions, 0 failed.

Also rank all translations from best to worst overall.

For every specific violation you notice, add one entry to "flags" with the translator label, the segment id, the criterion it hurts, its type, its severity and a short quote. type is exactly one of: untranslated (a fragment left in the source language: month, unit, name, term), number (a number, unit or date changed or lost), meaning (meaning distorted: flipped negation, wrong relation), omission (content missing), addition (content added that is not in the source), terminology (wrong or inconsistent term), style (unnatural phrasing or broken flow), format (broken structure: headings, lists, markup). severity is exactly one of: minor, major. Empty list if none.

Return a single valid JSON object, no markdown fences, no text outside JSON. Use exactly these values: "article": "$article_id", "judge": "$judge_code".

Output format:
{
  "protocol": "evaluation",
  "article": "$article_id",
  "judge": "$judge_code",
  "ranking": [$ranking_stub],
  "scores": {
$scores_stub
  },
  "flags": [
    {"translator": "M1", "segment": "S2-p3", "criterion": "data", "type": "number", "severity": "major", "quote": "..."}
  ],
  "verdict": "2-3 sentences, strongest and weakest translation and why"
}

SOURCE ARTICLE:
$source_json

$translations_block
