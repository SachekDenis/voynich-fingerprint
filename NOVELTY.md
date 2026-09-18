# What is new here, and what is not

Anyone publishing on the Voynich manuscript should separate the two. Much of what this
repository measures has been measured before, better, by people who got there first.
This file says which is which.

---

## Not new — reproductions

| finding | who established it |
|---|---|
| Conditional character entropy far below any natural language | **Bennett (1976)**, then Landini (2001), Reddy & Knight (2011) |
| h2 ≈ 1.9 for Voynichese against 2.77–6.14 for 316 comparison texts | **Lindemann & Bowern (2020)** — a stricter version of our own 13-corpus test |
| Word-length distribution is unimodal with a peak at 4–5 and no short-word spike | Stolfi; Reddy & Knight (2011) |
| A handful of character bigrams carries a large share of the text | **Lindemann & Bowern (2020)** — they report 29.3 %; we measure 21.8 % |
| Zipf's law holds; vocabulary growth follows Heaps' law | Landini (2001); Ponnaluri (2024) |
| The text is not memoryless — long-range character correlations exist | **Landini (2001)** |
| Morphological slot structure (prefix / stem / suffix) | Reddy & Knight (2011); Stolfi's "crust–mantle–core" |
| Self-citation with copy-and-modify can produce Voynich-like statistics | **Timm & Schinner (2019)** |
| Word-final → word-initial dependence (words ending in `y` precede `qo-` words) | Currier (1976); modelled here as a conditional, not discovered |
| A grille/table device is a plausible production method | Rugg & Taylor (2017); Zandbergen |

Our entropy numbers, the positional entropies, the Zipf slope and the word-length shape
are **confirmations**, reached with a different pipeline. They are useful as an
independent replication, not as a discovery. The corpus comparison here uses 13 corpora;
Lindemann & Bowern's uses 316 and is the stronger result.

---

## New — what we could not find published

### 1. A generator that matches the *whole* fingerprint at once

Timm & Schinner's self-citation generator is the closest prior work: it is a complete,
public, executable procedure, and it was used here as the baseline. An earlier revision
of this file said what it does and does not reproduce by quoting their paper. That is not
a measurement, and it was partly wrong — they match line geometry and several
distributional properties far better than the summary implied. `compare_generators.py`
now runs their executable itself, on text matched to the held-out half, and scores it on
the same vector.

They are given **the best of 20 configurations** of their own switches, not their default,
so the comparison is not against a straw man:

| generator | tier-1 (15 metrics) | structural (27 metrics) |
|---|---|---|
| Timm & Schinner, **best of 20 configs** | 19.9 % | 17.5 % |
| Timm & Schinner, their default | 26.3 % | 28.3 % |
| **this repository's model** | **2.7 %** | **4.6 %** |
| this repository's hand-executable manual (§15) | 7.3 % | 8.4 % |

What they get right, measured: mean line length (3 % off), words per line (2 %),
`len>=10 %` (6 %), adjacent identical words (6 %), ch- onsets (4 %), and all eight
positional character entropies within 4–24 %. The line-fill and gallows machinery in
their generator works.

Where they diverge — and this is the specific claim, not a general one:

| metric | held-out | theirs | error |
|---|---|---|---|
| cross-word MI | 0.068 | 0.008 | **88 %** |
| `qo-` onsets | 15.2 % | 5.5 % | **64 %** |
| words ending in `y` | 40.3 % | 19.1 % | **53 %** |
| words of 8+ characters | 8.3 % | 12.8 % | **54 %** |
| top-10 word share | 12.8 % | 7.5 % | **42 %** |
| line-length sd | 16.05 | 10.01 | **38 %** |
| repeated word-pair | 15.3 % | 10.2 % | 33 % |

So the residual is not "vocabulary richness" in general — with the best configuration
they *over*-produce types (5 218 against 4 526) while under-concentrating the frequency
spectrum. It is that their output is too **even**: too flat a spectrum, too uniform a line,
too few `qo-` words and `-y` endings, and no measurable word-final → word-initial
dependence at all.

The model here matches **44 metrics simultaneously at a 3.7 % mean error** (4.3 % on the
reversed split), on a held-out split: entropy, positional entropy, vocabulary richness, hapax share, the full
word-frequency spectrum, length distribution, ending distribution, onset distribution,
cross-word MI, line fill, paragraph shape, gallows placement, Zipf slope, repetition
structure. Code: `analysis/voynich_artgen.py`, `analysis/freeze_and_verify.py`,
`analysis/compare_generators.py`.

### 2. The metrics are coupled — eight documented dead ends

This is the part that took the longest and is, we think, the most useful to anyone
building a similar model. The parameters are not independent, and the obvious ways to
fix a metric break another:

| attempt | result |
|---|---|
| direct control of word length (fill to a target length) | length distribution TV = 0.015, but **endings destroyed**: words in `y` fall from 40 % to 23 % |
| control the *number of syllables* instead | H(word) 10.265 against 10.274 — nearly exact — and endings destroyed again (top-5 finals 91 % → 55 %) |
| append an ending drawn from the real ending distribution | endings exact, **vocabulary explodes**: TTR 0.28 → 0.43 |
| penalise recent words ("recency penalty") | fixes repeated pairs, **ruins the frequency spectrum**: top-10 share 11.8 % → 5.5 % |
| reuse a stock of frequent words | lowers diversity without concentrating the spectrum: top-10 stays at 10.1 % against a target of 12.8 % |
| resample the onset class inside the rejection loop | the acceptance weight biases the onset distribution — a systematic bug that flattens `qo-` and MI |
| copy from nearby text (`copy_decay`), word-pair memory up to 0.45 | moves the repetition rate, leaves long-range MI untouched, costs the text statistics |
| a frequency-weighted paragraph-local pool | raises within-paragraph repetition toward the target **and across paragraphs too**, because every paragraph got the same list. Costs tier-1 2.8 % → 12.6 %. What fixed it was changing the pool from a fixed list to a per-passage one — see §7 |

What works is entering at the level where the coupling arises: **the identity of the
word is never touched, and only conditional distributions are reweighted** — length,
ending, onset class.

### 3. Two structural properties of the manuscript, measured

Both are directly measurable in the transcription and both were missing from the model
before being measured:

- **Words shorten toward the right margin.** Mean word length by decile of position in
  the line: 5.39 → 5.12 → 5.31 → 5.24 → 5.32 → 5.21 → 5.26 → 5.17 → 4.95 → **4.33**.
  First word of a line 5.54, last 4.82. A scribe fitting the word to the remaining space.
- **The last line of a paragraph is about half the length of the others.** Median 46
  characters for mid-paragraph lines, **23** for paragraph-final ones. Treating them as
  one population makes a model squeeze words into deliberately short lines.

### 4. The labels beside the drawings imitate names without being names

If the manuscript is a herbal, the short texts next to the pictures are names, and names
are longer than ordinary words. Measured against a rarity-matched control drawn from the
manuscript's own body text:

| | body text | labels | matched control (hapax words) |
|---|---|---|---|
| TTR | 0.223 | 0.704 | 1.000 |
| hapax share | 15.7 % | 59.6 % | 100 % |
| mean word length | 5.17 | **5.20** | **7.10** (z = −38) |
| h2 | 1.866 | 2.346 | 2.446 |

The labels carry the surface signature of a name list — high type/token ratio, high
hapax share — and none of the formal properties: their word length is exactly the body
average, while genuinely rare words of the same text are 38 standard deviations longer.
48.2 % of label word-types also occur in the body, against 17 % expected by chance. The
code is `analysis/label_analysis.py`.

### 5. The procedure is not self-sustaining without invention

A model fitted to the finished manuscript is a *description*, not necessarily a
*procedure*. To test whether a person could have produced the text by iterating on their
own output, the model was refit on its own generations:

| free invention per word | after 8 rounds |
|---|---|
| 0 % | **collapses**: TTR 0.138 → 0.086, hapax 7.4 % → 4.1 %, top-10 share 22.6 % → 27.2 % |
| 15 % | **self-sustains**: h2 1.766 → 1.873 (target 1.842), top-10 → 15.9 % (target 12.8 %) |
| 30 % | overshoots: TTR 0.476, hapax 37.2 % |

Pure mechanical copying contracts. The manuscript's vocabulary richness requires a
source of novelty that does not decay — in a human, invention. Code:
`analysis/bootstrap_test.py`.

### 6. A controlled cipher attack

Most refutations of the substitution hypothesis report a failure. This one reports a
**control that succeeds**: the same hill-climbing solver recovers **100 % of words**
(6000/6000) from a random substitution of Latin, and then fails on Voynichese
(score per character −11.11, against a Latin ceiling of −8.57 and a random-mapping floor
of −13.81). That separates "the attack does not work" from "the hypothesis is false".

### 7. The passage is the unit of work — word repetition resets at the paragraph

Not previously quantified, and the sharpest single statement of how the book was made:
the text repeats words at two and three-quarter times chance *inside* a passage and at
chance across the break, and the break is invisible to every memoryless measure.

**The profile.** The rate at which a word repeats an earlier one, as a function of
distance in words:

| lag | 1 | 2 | 3 | 4 | 5 | 6 | 12 | 20 |
|---|---|---|---|---|---|---|---|---|
| **manuscript** | 0.87 | 0.93 | 0.94 | 0.95 | 0.75 | 0.91 | 0.73 | 0.73 |
| this generator | 1.01 | 0.31 | 0.21 | 0.25 | 0.21 | 0.28 | 0.24 | 0.28 |
| Latin | 0.17 | 0.75 | 1.41 | 1.78 | 1.60 | 1.71 | 1.80 | 1.31 |

Against the Simpson index Σf² = 0.326 %, which is the rate independent sampling from the
text's own word distribution would give, the manuscript runs at **2.6 ×** and Latin at
1.4 × (rising with distance, as function words do). The generator sits below even the
baseline.

**It is not flat. It drops at the paragraph, and only there.**

Repeat rate at lags 2–6 pooled, for word pairs that stay inside a unit against pairs that
cross its boundary:

| boundary | inside | across | ratio |
|---|---|---|---|
| line | 0.934 % | 0.774 % | 1.2 × |
| **paragraph** | **0.907 %** | **0.374 %** | **2.4 ×** |
| folio | 0.875 % | 0.195 % | 4.5 × |

Memoryless baseline: 0.326 %. Crossing a line barely matters — the vocabulary continues,
as typography should. Crossing a **paragraph** cuts the rate by more than half, from 2.8 ×
chance to 1.15 × chance. Crossing a **folio** drops it below chance. The profile looked
flat only because paragraphs average 44 words, so lags up to 120 are mostly within them.

The paragraph break is the sharp boundary; the page turn is sharper still, which is the
same effect one scale up — but a folio boundary is also where a quire or a gathering
changes, so the two are not separated here.

**What carries it.** Shuffling the words inside each paragraph keeps the passage's word
multiset and destroys its order; that alone accounts for two thirds of the excess. The
remainder is genuine sequential structure, and it is flat from lag 1 to lag 80 — which is
not what grammar looks like.

| component | size | share |
|---|---|---|
| the passage has its own vocabulary (topical) | +0.373 pp | **67 %** |
| order inside the passage (sequential) | +0.182 pp | **33 %** |

The excess is carried by **common** words, not rare ones. Words occurring exactly twice in
the whole manuscript have a median separation of 7022 words, and only 0.5 % of such pairs
sit within ten words — *less* than Latin (2.8 %) and less than the generator (3.6 %).
Rare forms disperse; the working set is the frequent ones.

**Read as a made object**, this is the signature of a unit of work. A person sits down to
write a passage — one plant, one recipe, one part of the body — holds a bounded set of
forms while doing it, and starts the next passage with a new one. A language does not do
this: topical clustering does not snap to a typographic paragraph mark. The sequential
third, flat over eighty words, is not grammar either (grammar is short-range); it is what
copying from a nearby model, or habitual phrasing, looks like.

An earlier revision of this file said the across-paragraph rate fell *below* chance. With
the paragraph segmentation corrected (see `LIMITATIONS.md` §3d) it does not: it falls from
2.8 × chance to 1.15 ×, and it is the **folio** boundary that goes below chance, to 0.60 ×.
The drop is still sharp and still at the paragraph, but the "reverses sign" claim was a
consequence of the segmentation error and is withdrawn.

**The target, exactly.** Against its own frequency spectrum, the across-paragraph rate is
**statistically indistinguishable from independent sampling**: 57 hits against 49.7
expected, z = +1.0. The within-paragraph rate is 1387 against 498.5 expected, z = +39.8.
So the property is not that the text repeats more than its spectrum allows — it is that
the repetition is scoped *precisely* to the passage and vanishes at the boundary, while
the boundary itself is invisible to the memoryless baseline.

**Reproducing it.** An earlier revision of this file said the selectivity could not be
reproduced. That was wrong, and the failure had a specific cause: the paragraph pool was
the same list for every paragraph (the N most frequent words), so it raised the rate
inside a passage *and* between any two passages. Two fixes work.

*Draw the word from the words already written in this paragraph*, and clear that list at
the break. Between two passages the two lists are independent, so the rate falls back to
chance by construction.

| configuration | within | w/base | across | a/base | 44-metric error |
|---|---|---|---|---|---|
| **manuscript** | 0.907 % | **2.78 ×** | 0.374 % | **1.15 ×** | — |
| frozen configuration, no mechanism | 0.267 % | 0.88 × | 0.283 % | 0.94 × | 3.7 % |
| sampled pool, 0.80 × 110 | 0.875 % | 2.77 × | 0.321 % | 1.02 × | 7.6 % |
| passage self-pool, 0.08 | 0.700 % | 2.35 × | 0.296 % | 0.99 × | 5.2 % |
| **the manual of §15, its own parameters** | **0.719 %** | **2.54 ×** | **0.273 %** | **0.96 ×** | **7.8 %** |

The last line is the demonstration. The manual carries a passage-scoped pool because a
hand naturally does, and its re-use rate was chosen on a selection split for the overall
44-metric error in §15 — *not* for this profile, which had not been measured at that
point. It reproduces the shape anyway.

**What it cost, and why.** It first looked like a four-point price on the headline. Almost
all of that was one metric: drawing from the passage pool could return the word
immediately preceding, which pushed *adjacent identical words* from 21 % to 70 % error.
The target profile is measured at lags 2 to 6, so a lag-1 repeat was pure cost with no
gain. Excluding the near neighbour from the draw cut the price on the selection split
from about 2.5 points to **0.5**, and made the profile match better rather than worse.

| | within | ratio | across | ratio | 44-metric error |
|---|---|---|---|---|---|
| frozen configuration | 0.260 % | 0.85 × | 0.304 % | 0.99 × | 3.96 / 4.30 % |
| **manuscript** | **0.907 %** | **2.78 ×** | **0.374 %** | **1.15 ×** | — |
| with the passage pool | 0.859 % | **2.85 ×** | 0.274 % | 0.91 × | 4.50 / 6.09 % |

(normal / reversed split.) The within-paragraph ratio now lands on the target on *both*
splits, so the mechanism is not fitting the split it was seen on. The price is 0.5 points
on the selection split and 1.8 on the reversed one, and the reversed split is the honest
one here — which is why the frozen configuration still leaves the mechanism off. That is
now a documented choice at a measured price, not a gap.

The analogous mechanism for the front-of-word dependence is in §10 and does not fare as
well: it reaches the target only by wrecking the length tails.

### 8. The long-range correlation gap does not exist — an estimator artefact

An earlier revision of this repository reported that the generator under-produces
character mutual information at offsets 6–12 (0.140 against the manuscript's 0.181) and
called it the clearest open problem in the model. **That was wrong.**

Mutual information estimated on a small sample is biased upward, and the bias grows with
the size of the joint table. On words of at least nine characters there are only ~1300
character pairs at a given offset, against a 22 × 22 table: the Miller–Madox correction
is **0.168 bits**, essentially the whole of the reported effect.

| within-word MI, offset 8 | pairs | raw | correction | corrected |
|---|---|---|---|---|
| manuscript | 1315 | 0.181 | 0.168 | **0.0133** |
| generator | 1723 | 0.140 | 0.128 | **0.0117** |
| Latin | 5381 | 0.210 | 0.059 | **0.151** |

Corrected, the two differ by 0.0016 bits. There is no long-range character structure in
the manuscript beyond what the generator already produces — and both are an order of
magnitude below Latin.

What is real is a **short-offset** gap, where the sample is large enough that the
correction is negligible (≈0.01 bits on 23 000 pairs):

| within-word MI, offset 4 | corrected | ratio |
|---|---|---|
| manuscript | 0.2497 | |
| generator | 0.2147 | 86 % |
| Latin | 0.1427 | 57 % |

### 9. The generator already implements the slot grammar

The manuscript's words decompose into three slots with very unequal weights — Stolfi's
crust / mantle / core:

| slot | types | entropy |
|---|---|---|
| onset | 154 | 6.59 bits |
| **core** | 711 | **2.06 bits** |
| ending | 145 | 6.38 bits |

Thirty cores cover 92.6 % of all words. The interior of a Voynich word is nearly a
constant; almost all the information sits at the two edges.

A slot grammar was proposed as the fix for §8. It is not needed: the bigram chain
already lands in the same structure, and the remaining differences are inside a few per
cent.

| | H(onset) | **H(core)** | H(ending) | top-30 cores |
|---|---|---|---|---|
| manuscript | 6.55 | **2.10** | 6.36 | 92.4 % |
| generator | 6.61 | **2.03** | 6.36 | 92.3 % |

The crust-to-ending coupling is reproduced too: MI(onset class ; final character) is
0.1026 against 0.0943 (92 %), and P(final `y` | onset class) tracks the manuscript
(`ch`: 51 % vs 49 %, `qo`: 47 % vs 50 %, `sh`: 58 % vs 56 %).

Every character-level dependency measured here is reproduced at **86–100 %**. The residual
is a uniform few per cent rather than a missing component.

### 10. What is actually missing

Two things, and neither is hidden.

**The within-word dependence is short, and it is short at the front.** Measured with a
surrogate control rather than an analytic bias correction — see `LIMITATIONS.md` §3
— the manuscript keeps a real dependence out to about six characters and the generator
is short of it by 0.022–0.032 bits over distances three to six. Beyond six **neither
corpus has any measurable dependence at all**.

`word_mi_position.py` then labels each character pair by where it sits in the word, and
the deficit turns out to be almost entirely at the beginning: **86 %** of it is in the
front half, the middle is under one standard deviation at every distance, and at the back
the generator has *more* than the manuscript. The sharpest single cell is pairs starting
at position 0 or 1, at +7.4 standard deviations.

**It is not a missing table, and it is not closable here.** Four attempts were made:

| attempt | result |
|---|---|
| a within-word repetition mechanism | no effect |
| conditioning the second shape on the onset class | helps the split it was found on, a wash on the reversed one |
| `p_raw` — accept a fraction of words unchecked | reaches the target only by wrecking the length tails |
| `endfix` — accept on length alone, then swap the ending | **much worse**: front-half MI 0.154 → 0.079, 44-metric error 3.96 % → 11.97 % |

The last failure is the informative one. The idea was to decouple the two halves of the
reweighting, since the front is what the acceptance damages. It fails because the ending
is not an appendage — it is constrained by what precedes it, so editing it independently
destroys the dependence it was meant to preserve.

A word-level mixture of checked and unchecked words *does* reach the target, at 25 %
unchecked and a small length cost. The interpolation exists; the model's single joint
accept/reject cannot express it. This is a limit of the architecture rather than a missing
measurement, and it is the one item in this repository that is not closed.

### 11. The text runs out of context after two characters

Every entropy figure in this repository until now was a bigram figure. The question that
separates a language from a table is not the bigram entropy but the **slope**: how much
does a third, a fourth, a fifth character of context buy? A language keeps buying,
because morphology and grammar constrain what comes next. A table of syllables stops
buying the moment the syllable is identified.

Cross-entropy with Witten-Bell smoothing, trained on half of each corpus and tested on
the other half, so alphabets of different size are comparable and no bias correction is
needed:

| corpus | h1 | h2 | h3 | h4 | h5 | gain 2→3 | gain 3→4 |
|---|---|---|---|---|---|---|---|
| **manuscript** | 3.87 | **2.34** | **2.14** | 2.17 | 2.31 | **+0.20** | −0.03 |
| this generator | 3.85 | **2.33** | **2.14** | 2.20 | 2.38 | **+0.19** | −0.06 |
| Latin | 3.98 | 3.48 | 3.03 | 2.68 | 2.59 | +0.45 | +0.35 |
| Italian | 4.03 | 3.49 | 3.21 | 3.05 | 3.12 | +0.28 | +0.16 |
| German | 4.21 | 3.62 | 3.32 | 3.17 | 3.24 | +0.30 | +0.15 |
| Old Church Slavonic | 5.23 | 4.72 | 4.54 | 4.66 | 4.84 | +0.18 | −0.12 |

The manuscript stops learning at two characters of context. The third buys 0.20 bits;
the fourth buys nothing. Latin buys 0.45 and then 0.35 more. Orders 4 and 5 are
unreliable for every corpus here (smoothing is not sufficient at that sparsity), which is
why the conclusion rests on the 2→3 step, where the counts are ample.

**The generator reproduces the whole curve**, at every order, to within 0.01–0.03 bits,
and was never fitted to it. `order_profile.py`.

### 12. The text supports two scribes, not five

The division of the manuscript into hands is disputed: Currier proposed two, Fagin Davis
proposed five, and a critique argues her diagnostic features occur on nearly every page.
The text itself can be asked.

Each hand was compared with **random samples of the same size drawn from its own
section**, so neither sample size nor section content can explain a difference:

| section | hand | tokens | h2 | z against its own section |
|---|---|---|---|---|
| herbal | 1 | 6935 | 1.819 | **−22.9** |
| herbal | 2 | 2201 | 1.854 | −5.2 |
| herbal | 3 | 773 | 1.858 | −1.5 |
| herbal | 5 | 889 | 1.887 | −0.9 |
| pharmaceutical | 2 | 1805 | 1.768 | **−9.6** |
| pharmaceutical | 1 | 3252 | 1.908 | −2.8 |

Hands 1 and 2 are statistically distinct from the bulk of their own section, by margins
that cannot be sampling: −22.9σ and −9.6σ. Hands 3 and 5 are **indistinguishable** from
random samples of their section on entropy, type-token ratio and hapax share, every
absolute z below 1.6.

So the text statistics support **two** groups, and do not support the other three. That is
consistent with both sides of the dispute: with Currier, that there are two; with the
critics of the five-scribe hypothesis, that the extra hands are not separable on textual
grounds. It says nothing against palaeographic evidence, which is a different kind of
evidence and was not examined here.

### 13. The sections are statistically different, and the model is section-specific

Every split used so far was by leaf parity, so training and test always contained the same
mixture of sections. Fitting to one section and testing on another answers a different
question: is one procedure enough for the whole book?

| train | test | tier-1 error | tier-2 error |
|---|---|---|---|
| herbal | herbal | 4.1 % | 4.5 % |
| biological | biological | 3.2 % | 5.2 % |
| pharmaceutical | pharmaceutical | 5.2 % | 8.5 % |
| recipes | recipes | 2.6 % | 5.9 % |
| pharmaceutical | → recipes | 10.3 % | 20.4 % |
| **herbal** | **→ recipes** | **11.1 %** | **26.2 %** |
| biological | → recipes | 13.5 % | 24.1 % |
| recipes | → herbal | 16.8 % | 20.3 % |
| **herbal** | **→ biological** | **24.0 %** | **48.1 %** |
| biological | → herbal | 27.3 % | 34.4 % |
| herbal | → pharmaceutical | **4.4 %** | **11.3 %** |

Within a section the model reproduces 44 metrics at 3–6 %. Across sections the error is
three to six times that. Two of the eleven pairs are the exception and are informative:
**herbal → pharmaceutical is as good as within-section** (4.4 %), and those are exactly the
two sections that make up Currier's language A. Section identity and dialect are entangled,
but neither alone explains the spread — biological and recipes are both Currier B and still
transfer at 13.5 %, twice the within-section error.

And the headline does not survive being taken apart. `book_model.py` measures three
designs on the same held-out leaves:

| design | per-section error | pooled |
|---|---|---|
| **A** one pooled model, the whole held-out half at once | — | **3.7 %** |
| **B** the same pooled model, each held-out section alone | 10.6–26.2 % | 14.4 % |
| **C** one parameter set per section, half a section each way | 5.7–14.2 % | 7.5 % |

A and B are the same model. The distance between 3.7 % and 14.4 % is not a fitting
failure: pooling the sections produces statistics that no individual section has, and
what the model reproduces is the mixture. So the honest form of the headline is: *a
language-free procedure reproduces the aggregate statistics of the manuscript to 3.7 %;
applied to any single section it is off by 10–26 %, and with per-section parameters by
5.7–14.2 %.* Per-section parameters halve the per-section error, and their limit is text
rather than method — pharmaceutical has 1 494 training words under that design and lands
at 14.2 %, recipes has 4 982 and lands at 6.1 %.

**Which table makes them different?** `section_gap_localise.py` replaces one component
of the source model with the target's, one at a time, and measures how much of the
transfer error each replacement removes:

| component replaced | mean share of the transfer error removed |
|---|---|
| the (length × final shape) joint | **22 %** |
| the onset marginal and cross-word table | 19 % |
| the pair memory and stock of frequent words | 19 % |
| line width and paragraph shape | 14 % |

No component dominates, and no pair falls below about 60 % of its original error even
with one table fully replaced. The sections differ in all of their tables at once, which
is why per-section parameters are the only thing that works and why they are expensive:
there is no single mechanism to fix.

A fourth design is worse than either: a shared text model with per-section page geometry
alone, at 11.9 %. Geometry and the length conditioning are coupled — the length target is
measured on non-line-final words — so changing the column width without re-deriving the
lengths moves the realised length distribution instead of improving it.

### 14. What the sections actually differ by

The transfer failure says the sections differ; it does not say how. Measured axis by axis
(`section_structure.py`), against a within-section resampling baseline:

| axis | between sections | same section, resampled | ratio |
|---|---|---|---|
| letter frequencies | 0.0189 | 0.0008 | **25×** |
| word onsets | 0.0823 | 0.0063 | **13×** |
| first two letters | 0.1352 | 0.0299 | 4.5× |
| word length | 0.0133 | 0.0036 | 3.7× |
| last two letters | 0.0894 | 0.0314 | 2.8× |

Three findings, one of which refutes a natural guess.

**The sections draw on the same vocabulary and weight it differently.** The top twenty word
types of every section are all in the shared stock, 60–83 % of every section's running text
comes from words that appear in three or more sections, and the most frequent word of the
herbal (`daiin`, `chol`, `chor`) and of the recipes (`aiin`, `chedy`, `qokeey`) are the same
kinds of words in a different order. So the difference is not a different repertoire. It is
a different frequency profile over one repertoire — which is what a habit is, and what a
hand can change between sections without learning anything new.

**Part of it is paper, not language.** Mean characters per line, by section:
astronomical 27.0, zodiac 30.6, herbal 34.9, biological 42.9, pharmaceutical 44.2,
cosmological 45.6, recipes 52.5. That is a factor of 1.9, and it tracks how much of the
page the drawing occupies — the herbal pages are half plant, the recipes pages are full
text. Any line- or paragraph-based metric read across sections is partly reading page
geometry.

`section_transfer.py` now measures how much, by telling the generator the target
section's line width and paragraph shape — a physical parameter a writer plainly copies
from the page in front of him — and repeating the transfer:

| train → test | as-is | layout from target |
|---|---|---|
| herbal → recipes | 11.1 % / 26.2 % | 11.1 % / **18.9 %** |
| recipes → herbal | 16.8 % / 20.3 % | 13.1 % / **11.0 %** |
| herbal → biological | 24.0 % / 48.1 % | 18.4 % / **32.3 %** |
| biological → herbal | 27.3 % / 34.4 % | 18.6 % / **20.1 %** |
| pharmaceutical → recipes | 10.3 % / 20.4 % | 8.5 % / **14.3 %** |

(tier-1 / tier-2.) Page geometry accounts for about **a third of the tier-2 gap and a
fifth of the tier-1 gap**. So the sections genuinely differ in their text as well, and
that residual is not explained here.

**The obvious explanation of Currier A/B is wrong.** Currier's two languages use different
gallows characters — `t`/`k` in A, `p`/`f` in B — so the natural guess is that the whole
difference is a pen-stroke substitution. Rewriting the herbal with `t→p`, `k→f` makes the
onset distribution *less* like the recipes, not more (JS divergence 0.121 → 0.160), and the
same for biological and pharmaceutical. The A/B contrast is real but it is not a glyph swap.

`section_structure.py`.

## Assessment of claims encountered along the way

Two groups of claims were examined and are written up in
[`docs/claims-assessment.md`](docs/claims-assessment.md): a repository proposing a
camera-obscura encoding with an Old Church Slavonic reading, and the 2026 news wave
reporting that an AI had deciphered the manuscript. Both are refuted by their own
material and by the data.

### 15. The manual: a hand-executable procedure that reaches 7.8 %

Everything above is a computer result. The generator reaches 3.7 % by rejection sampling on
a joint (length × ending) distribution and by a 151-row transition table — neither is
available to a person with a quill. `scribe_method.py` asks the opposite question: what is
the smallest procedure a *hand* can execute, and how close does it get?

The scribe carries eight tables, all of them short: 60 syllable shapes; 14 standard word
openings; a 21-row link table (after writing this *letter*, the shape that usually follows);
a length table; 14 stock endings chosen by the word's length; a cross-word carry-over table;
a list of habitual word pairs; and page rules.

The procedure for one word is: look at the last letter written, write an opening, decide the
length and the ending, fill the middle until the word is that size. Nothing is a statistic
and nothing is ever thrown away and re-rolled.

| | tier-1 | tier-2 | overall, 44 metrics |
|---|---|---|---|
| computer generator (rejection sampling) | 2.7 % | 4.3 % | **3.7 %** |
| **the manual, by hand** | **7.3 %** | **8.0 %** | **7.8 %** |

Hyper-parameters (60 shapes, stock-pair rate, re-use rate, gallows rate) were chosen on a
selection half *inside* the training leaves and then reported on the untouched held-out
half, so no number is fitted to the text it is scored against.

Four findings from building it:

**The ending must be carried as letters, not as shapes.** A 60-shape table cannot spell the
true last shape of most words, so drawing the ending from the shape table loses the
manuscript's endings — `-y` above all, which closes 40 % of its words. The scribe's output
had `-y` on 15 % of words until the endings were learned as character suffixes instead;
then 44.6 % against a target of 40.3 %.

**The hand's substitute for rejection sampling is deciding the length first.** A chain that
rolls a die after every shape and stops on a rule gets a geometric length distribution:
mean 4.2 against 5.2, sd 2.6 against 1.9, and both tails far too heavy. Choosing the word's
size before writing it, and filling to that size, fixes the distribution outright
(sd 1.88 against 1.86, length TV distance 0.063) and costs nothing in plausibility — a
person does know how long the word is about to be.

**Repeats and vocabulary come from one mechanism, and the hand version of it is a swap.**
The manuscript combines a highly repetitive text (`repeated word-pair 15.3 %`) with a rich
vocabulary (4 526 types in 16 436 tokens). A table-driven writer gets one or the other. Both
fall out of writing a word again with *one shape changed for the one that usually follows
it*, which is what a hand does with a formula it has just used. Restricting the change to a
swap rather than an insertion or a deletion matters more than any other single parameter: an
insertion or a deletion also creates repeats, but it doubles the number of one- and
two-letter words, because the hand that is supposed to be filling a word to a decided length
keeps making it shorter instead.

**What the manual does not reach is vocabulary richness.** The residual 7.8 % is dominated
by three measures of the same thing: hapax share of tokens (14.7 % against 19.7 %), TTR
(0.230 against 0.275) and hapax share of types (63.7 % against 71.6 %). The manuscript's
vocabulary is more productive than 60 shapes and one mutation operator produce. Whether that
is a sixth mechanism, or simply a larger table, is not settled here.

`scribe_method.py`, `scribe_design.py`; the tables as printed are in
`SCRIBE_MANUAL.txt` and a sample of the output is in `scribe_sample.txt`.

One property it reproduces without having been asked to. Its passage pool — the forms
still in mind, cleared at the paragraph break — was chosen on a selection split for the
overall 44-metric error. Measured afterwards against the manuscript's repetition profile
(`repetition_fix.py`, §7), it lands at 2.54 × chance inside a passage against a target of
2.78 ×, and 0.96 × across the break against 1.15 ×. The shape came out of the hand's
natural bookkeeping rather than out of fitting.
