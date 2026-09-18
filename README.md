# A measurable fingerprint of the Voynich manuscript — and a generator that reproduces it

The Voynich manuscript (Yale, Beinecke MS 408) has resisted decipherment for a century.
This repository does not claim to read it. It does three narrower things, all
reproducible from public data:

1. **Measures a fingerprint** of the text: 15 text statistics plus 29 structural ones,
   taken from the transcription and from thirteen natural-language corpora, on a
   train/test split of the manuscript's own leaves.
2. **Rules out classes of hypothesis** with controlled experiments — a substitution
   attack that is validated on a cipher it must break, and a model that reproduces the
   fingerprint without containing any language at all.
3. **Demonstrates the positive alternative**: a five-component generative model whose
   output matches the whole fingerprint at a **3.7 % mean error over 44 metrics**, on a
   split it was not fitted to — and a **hand-executable procedure**, eight short tables
   and a die, no rejection sampling, that reaches **7.8 %**.

---

## Headline numbers

### Conditional character entropy (h2)

How much information the next character carries given the current one. Lower means more
predictable.

| corpus | h2 |
|---|---|
| **Voynich manuscript** | **1.893** |
| a meaning-free generator (this repo) | 1.678 – 1.770 |
| closest of 13 natural-language corpora (Augustine) | 2.979 |
| Latin / Italian / Spanish | 3.188 / 3.190 / 3.189 |
| Old Church Slavonic / Greek / Hebrew | 3.493 / 3.578 / 3.846 |

The gap between the manuscript and the nearest language is **1.09 bits**; the gap
between the manuscript and the generator is **0.13–0.22 bits**.

The result survives the obvious objection that EVA writes one manuscript glyph with two
Latin characters. Across five independent transliteration alphabets — including v101
(Currier), where one glyph is exactly one character and the alphabet has 166 symbols —
h2 stays between 1.85 and 2.35, while Latin reaches 3.19.

### Two anomalies the literature reports, reproduced

| metric | Voynich | Latin | Italian | OCS | generator |
|---|---|---|---|---|---|
| **Brevity law** (mean length vs rank) | **−0.390** | −0.927 | −1.128 | −0.918 | **−0.429** |
| **high-probability bigrams** covering the text | **21.8 %** (9 bigrams) | 1.9 % | 1.2 % | 1.8 % | **22.7 %** (8) |

In a language, frequent words are short — that is what the Brevity law is. In the
manuscript the effect is almost absent. And a handful of character bigrams accounts for
a fifth of all the text.

### The generator

A five-component model reproduces the whole fingerprint:

| | metrics | mean error |
|---|---|---|
| text statistics | 15 | **2.7 %** |
| structure (lines, paragraphs, Zipf, repetition) | 29 | **4.3 %** |
| **overall** | **44** | **3.7 %** |

On an independent reversed split the same configuration gives 4.29 %. The parameter set
was tuned on one split, so the agreement of the two splits is the evidence that it is
not overfitted — see [`NOVELTY.md`](NOVELTY.md) and the warning in
[`LIMITATIONS.md`](LIMITATIONS.md).

**The headline describes the book in aggregate, not its parts.** Every split here is by
leaf parity, so both halves carry the same mixture of sections. `book_model.py` measures
what that costs: the same pooled model applied to a single held-out section is off by
**10.6–26.2 %**, and one parameter set per section, each trained on half that section,
gives **5.7–14.2 %** (pooled 7.5 %). Pooling the sections produces statistics that no
individual section has. The sections differ by far more than sampling noise, and part of
the difference is not textual at all — mean characters per line runs from 27.0 to 52.5
by section, following how much of the page the drawing takes.

### Against the closest prior generator

The comparison with Timm & Schinner used to be a quotation from their paper. It is now a
measurement: `compare_generators.py` runs their executable itself, at matched text size,
and gives it the **best of 20** configurations of its own switches.

| generator | tier-1 (15 metrics) | structural (27 metrics) |
|---|---|---|
| Timm & Schinner, best of 20 configs | 19.9 % | 17.5 % |
| Timm & Schinner, their default | 26.3 % | 28.3 % |
| **this model** | **2.7 %** | **4.6 %** |
| this model's hand-executable manual | 7.3 % | 8.4 % |

They match mean line length and line-initial gallows placement well. What they do not
have is concentration: 88 % off on cross-word mutual information, 64 % on `qo-` onsets,
53 % on words ending in `y`, 42 % on the top-10 word share.

### The manual — the same fingerprint by hand

The generator needs rejection sampling on a joint distribution and a 151-row table. A
person with a quill cannot carry that. `scribe_method.py` builds the smallest procedure
a *hand* can execute — 60 syllable shapes, 14 openings, a 21-row link table, a length
table, 14 endings, a carry-over table, stock word pairs, page rules — and reaches
**7.3 % / 8.0 %, 7.8 % overall**, with hyper-parameters chosen on a selection half
inside the training leaves and reported on the untouched held-out half. The tables as
they would be printed are in `SCRIBE_MANUAL.txt` and a sample of what the procedure
writes is in `scribe_sample.txt`. [`NOVELTY.md`](NOVELTY.md) §15 says what the manual
establishes and what it does not.

---

## What the model is made of

| component | what it buys |
|---|---|
| 1. a BPE syllable inventory (140 merges) | the character-entropy scale |
| 2. a bigram chain over those syllables | the rigid onset/coda slots of words |
| 3. `P(onset class │ last character of the previous word)` | cross-word dependence |
| 4. reweighting on (word length × final syllable) | the length distribution and the endings at once |
| 5. word-pair memory + self-citation with mutation | vocabulary size, Zipf slope, hapax share |

Plus a layout layer: separate line budgets for mid-paragraph and paragraph-final lines,
words shortened toward the margin, gallows characters at line starts.

The interesting part is not the list but the couplings between them — most of the
obvious mechanisms make things worse. Eight dead ends are documented in
[`NOVELTY.md`](NOVELTY.md).

---

## Running it

```bash
pip install -r requirements.txt

# transcriptions go in ./data (not redistributed here -- see data/README.md)
python analysis/refstats.py            # fingerprint against 13 corpora
python analysis/alphabet_robustness.py # the same statistic across 5 alphabets
python analysis/tier2_metrics.py       # structural metrics of the real text
python analysis/metrics_lit.py         # Heaps, Brevity, bigram concentration, long-range MI
python analysis/label_analysis.py      # do the labels behave like names?
python analysis/substitution_attack.py # cipher attack with a working control
python analysis/freeze_and_verify.py   # rebuild the generator; --verify checks drift
python analysis/human_feasibility.py   # could a person execute this procedure?
python analysis/bootstrap_test.py      # is the procedure self-sustaining?
python analysis/order_profile.py       # cross-entropy by context order, held-out
python analysis/repetition_origin.py   # where the word-repetition excess sits
python analysis/section_transfer.py    # does one set of parameters cover every section?
python analysis/section_structure.py   # what the sections actually differ by
python analysis/scribe_design.py       # how small the manual can be
python analysis/scribe_method.py       # the manual, and how close a hand gets
python analysis/compare_generators.py  # this model vs Timm & Schinner's, measured
python analysis/repetition_fix.py      # the passage-scoped repetition profile
python analysis/word_mi_gap.py         # within-word dependence, surrogate-controlled
python analysis/word_mi_position.py    # where in the word the residual sits
python analysis/book_model.py          # pooled vs per-section: what the headline measures
python analysis/section_gap_localise.py # which table makes the sections different
python analysis/make_report_pdf.py     # typeset report.pdf
```

`freeze_and_verify.py --verify` reproduces every number bit-for-bit (drift 0.00 %);
all generators are seeded, so results are deterministic.

**[`report.pdf`](report.pdf)** is the whole work typeset as a single document — abstract,
methods, results, the three corrections, and the negative results kept alongside the
positive ones.

---

## What is claimed, and what is not

**Claimed:** the text's measurable behaviour is reproducible by a procedure that
contains no language, no cipher and no message — and the standard cryptographic
hypotheses for a natural-language plaintext are excluded by controlled tests.

**Not claimed:** that the manuscript is definitely meaningless. A verbose cipher or a
nomenclator would be statistically indistinguishable from the generator's output. The
honest statement is that the data are consistent with procedural generation and
inconsistent with a natural language under any letter-level cipher.

See [`LIMITATIONS.md`](LIMITATIONS.md) for the full list of what these tests cannot
decide. It records three corrections made during the work: a leaked layout parameter, a
mutual-information comparison that was measuring its own estimator bias, and a paragraph
segmentation taken from the wrong transcription marker — which had made the model learn an
artefact of the file rather than a property of the manuscript.

**[`NOVELTY.md`](NOVELTY.md)** separates what is new here from what reproduces
published results. Most of the headline entropy figures are not new; the field has known
them for years.

---

## Data and prior work

Transcriptions from [voynich.nu](https://www.voynich.nu/data/) (Takahashi EVA, Currier
v101, Zandbergen–Landini, FSG, Friedman). Reference corpora from
[Universal Dependencies](https://universaldependencies.org/). The generator used as a
baseline is Torsten Timm's
[SelfCitationTextgenerator](https://github.com/TorstenTimm/SelfCitationTextgenerator).

Prior work this leans on: Bennett (1976) on low character entropy; Landini (2001) on
Zipf and long-range structure; Reddy & Knight (2011) on word length and morphology;
Lindemann & Bowern (2020) on entropy against 316 languages and on bigram concentration;
Timm & Schinner (2019, 2024) on self-citation; Stolfi on word-length distributions;
Ponnaluri (2024) on Heaps and Brevity laws. Full list in
[`docs/references.md`](docs/references.md).

## Licence

Code: MIT. Text: CC BY 4.0.
