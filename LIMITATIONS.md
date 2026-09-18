# Limitations — what these tests cannot decide

Written to be read before the results. Several of these are the difference between a
defensible claim and an overclaim.

---

## 1. "Reproducible by a language-free procedure" is not "meaningless"

A verbose cipher, a nomenclator, or a table-and-grille encoding would produce text
whose statistics reflect the *encoding*, not the language. Such a text is statistically
indistinguishable from the generator's output. The generator is a demonstration that a
message-free procedure suffices to explain the measurements; it is not a proof that no
message is present.

The defensible claim is narrower and is the one made here: the data are **inconsistent
with a natural language under any letter-level cipher** (substitution, homophonic,
transposition-within-words) and **consistent with procedural generation**.

## 2. The parameter set was selected on one split

The headline figure is a mean over 44 metrics on a held-out half of the corpus. But the
configuration was chosen by looking at that same half. The honest number is the one from
the reversed split, where the same configuration is re-run without selection:
**4.29 %**, against 3.73 % on the selection split. Report both, as the README does.

An earlier revision of this work took the layout constants — line lengths, paragraph
lengths — from the held-out document. That is a leak, it inflated the result, and it was
found only because a reversed split was run. Assume similar leaks elsewhere until they
are looked for.

## 3. The generator does not reproduce everything

| metric | Voynich | generator | gap |
|---|---|---|---|
| within-word MI, offset 3 (surrogate-corrected) | 0.335 | 0.309 | +0.026 bits, **+5.8 sd** |
| within-word MI, offset 4 (surrogate-corrected) | 0.097 | 0.075 | +0.022 bits, **+4.1 sd** |
| within-word MI, offset 5 | 0.075 | 0.055 | +0.021 bits, +1.7 sd |
| within-word MI, offset 6 | 0.077 | 0.044 | +0.033 bits, +2.5 sd |
| within-word MI, offset 8 and beyond | ≈ 0 | ≈ 0 | none in either |
| MI(onset class; final character) | 0.103 | 0.094 | 8 % |
| H(core) of the word's middle slot | 2.10 | 2.03 | 3 % |
| hapax share | 19.7 % | 18.3 % | 7 % |
| word repetition, lags 2–6 | 0.907 % | 0.267 % | **3.4 × low** (see §6b — mechanism implemented, off by choice) |

The mutual-information rows were recomputed. The earlier version used a Miller–Madow
correction whose magnitude, on a few thousand character pairs against a 22 × 22 table,
was larger than the effect being compared. The replacement is a **surrogate control**:
the characters of every word are permuted within that word, which preserves the word
length and the marginal frequencies exactly and destroys only the dependence, so the
permuted text's MI *is* the estimator's bias. No formula is assumed.

What that shows is narrower than "8–14 %, uniform across decompositions": the
manuscript's within-word dependence dies out by a distance of about six characters, and
beyond that **neither corpus has any measurable dependence at all**. The residual is
0.022–0.032 bits over distances 3 to 6 — real, at +5.8 and +4.1 sd against the
generator's seed-to-seed spread, and small. A within-word repetition mechanism was built
to test the obvious explanation and does not close it. Code: `word_mi_gap.py`.

**Where it sits.** `word_mi_position.py` labels every character pair by its position in
the word and repeats the measurement per label. The deficit is not spread out, and it is
not where the obvious reading puts it:

| cell | share of the deficit | largest gap |
|---|---|---|
| front half (midpoint < 0.40 L) | **86 %** | +0.039 bits at d=3, **+3.7 sd** |
| middle (0.40-0.70 L) | 19 % | +0.005 bits, under 1 sd at every distance |
| back half (midpoint >= 0.70 L) | **−6 %** | the generator has *more* than the manuscript |

The single sharpest cell is pairs starting at position 0 or 1: +0.041 bits at d=3, **+7.4
sd**. So the missing dependence is at the **front** of the word — between the opening
characters and what follows them.

**Why, and why it is not simply a missing table.** Taking the model apart at the front
half:

| d | manuscript | chain alone | chain + reweighting | frozen |
|---|---|---|---|---|
| 3 | 0.201 | 0.221 | 0.178 | 0.162 |
| 4 | 0.041 | **0.109** | **0.014** | 0.017 |
| 5 | 0.016 | 0.007 | 0.011 | 0.004 |

The chain on its own puts *more* dependence at the front of a word than the manuscript
has; the (length x ending) reweighting on top of it removes more than it should; the
frozen model lands below the target. Two components that each model something real
disagree by more than the residual they are supposed to explain. This is the same
coupling that produced the eight dead ends, and it is described rather than solved.

**Four attempts to close it, and what they establish.** This is now a statement about the
model's architecture rather than an unfinished measurement.

| attempt | result |
|---|---|
| a within-word repetition mechanism | does not move it |
| conditioning the second shape on the onset class | better on the split it was found on, a wash on the reversed one |
| `p_raw`: accept a fraction of words with no length or ending check | reaches the target only by wrecking the length tails (`len>=10` 5 % → 22 %, `len<=2` 3 % → 15 %) |
| `endfix`: accept on length alone, then repair the ending by swapping the last shape | **much worse** — front-half MI falls from 0.154 to 0.079 and the 44-metric error goes 3.96 % → 11.97 % |

The last one is the informative failure. The idea was to decouple the two halves of the
reweighting, since the front is what the acceptance damages. It fails because the ending
is not an appendage: it is constrained by what precedes it, and editing it independently
destroys the dependence it was meant to preserve. A word-level mixture of checked and
unchecked words *does* reach the target at 25 % unchecked with a small cost, so the
interpolation exists — but the model's single joint accept/reject cannot express it.

**Conclusion.** The front-of-word dependence is not reachable within this architecture.
The reweighting is one accept/reject on (length, ending); the manuscript's value sits
between what the chain proposes and what that acceptance keeps, and every attempt to split
the acceptance apart makes it worse. Closing it would need a different generator, not a
different parameter.

One further mechanical attempt is recorded as an option: conditioning the *second*
shape on the onset class rather than only on the last letter of the first. It is strictly
more information and it improves the split it was tested on (3.73 % → 3.49 %) and the
front half at d=3 — but it is a wash on the reversed split (4.29 % → 4.37 %), and the
difference sits inside the split-to-split spread. By this repository's own rule that the
reversed split arbitrates, it stays off.

**A caution about MI on small samples.** The metric reported here previously as "far MI
(d = 6–12)" showed the generator at 0.011 against 0.017. Almost all of that difference
was estimator bias: on ~1300 pairs against a 22 × 22 table the Miller–Madow correction is
0.168 bits, larger than the effect itself. Corrected, the two agree to 0.0016 bits. Any
mutual-information figure computed on a few thousand pairs needs the correction stated,
and this repository did not state it in its first revision.

The remaining gap is a bounded 0.022–0.032 bits at character distances 3 to 6 inside a
word, and nothing beyond. The word-repetition figure is the one metric the frozen form
knowingly leaves off, now that it is reachable — see §6b.

## 3b. The model is section-specific, and the headline describes a mixture

`section_transfer.py` fits the generator to one section and tests it on another. The error
goes from 2.6–5.2 % (same section) to 10–27 % (different section).

The 3.7 % headline is not a within-section figure, and it is not a whole-book figure
either: it is measured over a held-out half carrying the same **mixture** of sections as
the half the model was fitted on. An earlier revision of this file called it
"within-section", which is wrong in the other direction. `book_model.py` settles it with
three designs on the same 44 metrics and the same held-out leaves:

| design | per-section error | pooled |
|---|---|---|
| **A** one pooled model, the whole held-out half at once | — | **3.9 %** |
| **B** the same pooled model, each section on its own | 10.6–26.2 % | 14.4 % |
| **C** one parameter set per section, half a section each | 5.7–14.2 % | 7.5 % |

A and B are the same model. (A reads 3.9 % here and 3.7 % in the headline: same model on
the same split, but the script reports one seed while the headline averages three.) The
distance between 3.9 % and 14.4 % is not a fitting failure — pooling the sections produces
statistics that no individual section has, and what the model reproduces is the mixture.
**The headline is a statement about the book in aggregate and cannot be pushed down to its
parts.** Per-section parameters halve the per-section error, and their limit is text:
pharmaceutical has 1 494 training words under that design and lands at 14.2 %, recipes has
4 982 and lands at 6.1 %.

Which table carries it is measurable. `section_gap_localise.py` replaces one component of
the source model with the target's at a time: the (length x final shape) joint removes
**22 %** of the transfer error on average, the onset tables 19 %, the pair memory 19 %,
and the page geometry 14 %. No component dominates and no pair falls below 60 % of its
original error even with one table fully replaced. The sections differ in all of their
tables at once, which is why there is no single mechanism to fix.

Part of the difference is not textual at all — mean characters per line runs from 27.0
(astronomical) to 52.5 (recipes), tracking how much of the page the drawing occupies — but
a shared text model with per-section geometry alone is *worse* than either (11.9 %),
because geometry and the length conditioning are coupled. See `section_structure.py`,
`section_transfer.py`, `NOVELTY.md` §13–14.

## 3c. The manual establishes executability, not authorship

`scribe_method.py` reaches 7.8 % on the held-out half with eight short tables and no
rejection sampling, which shows that a procedure of this size is *sufficient* to produce
the measurements. It does not show that anyone used it, and it is not a reconstruction of
what a historical scribe did.

Its residual error is concentrated in three measures of vocabulary richness (hapax share of
tokens 14.7 % against 19.7 %, TTR 0.230 against 0.275, hapax share of types 63.7 % against
71.6 %). The manuscript's vocabulary is more productive than 60 shapes and one mutation
operator produce. Whether that needs a sixth mechanism or simply a larger table is not
settled.

The eight tables were also *derived from the manuscript's own statistics*. A person could
execute the procedure, but could not have derived it. This is the same gap as §6: the
demonstration is of executability given the tables, not of how the tables would arise.

## 3d. Three corrections made during this work

Recorded because each one changed a published number.

1. **A leaked layout parameter.** Line and paragraph constants were once taken from the
   held-out document. Fixed; the honest error moved from 3.2 % to 4.0 %.
2. **A mutual-information comparison measuring its own estimator bias.** The Miller–Madow
   correction on the table sizes involved (0.168 bits) was larger than the effect being
   compared. Corrected; the manuscript/generator difference in far-MI largely disappeared.
3. **Paragraph segmentation by the wrong marker.** Paragraphs were delimited by the locus
   type (`@` / `+` / `*`) instead of by the manuscript's own paragraph marks (`<%>` /
   `<$>`). `@` marks only the first paragraph of a page, so in the recipes section this
   merged about twelve real paragraphs into one 43-line block. The markers occur exactly
   772 times each and pair without exception, which is why they are the right ones. The
   effect was not small: real mean paragraph length is **5.16 lines, not 14.81**. Every
   paragraph-dependent number was recomputed, the frozen configuration re-verified, and
   the headline moved from 4.0 % to 3.7 % — it improved, because the generator had been
   faithfully learning the artefact.

## 4. The corpus comparison is smaller than the published one

Thirteen corpora here; Lindemann & Bowern used 316 languages and their result is
strictly stronger. The value of the smaller comparison is that it is reproducible from
a clean checkout in minutes, and that it covers Old Church Slavonic and Croatian — the
languages named by the specific claims being tested.

## 5. Everything is measured on a transcription, not on the ink

Every number here comes from EVA and four other transliterations. If a transliteration
systematically merges or splits glyphs, the statistics move. This objection is real, and
the answer here is empirical rather than principled: the same statistic was computed
across five alphabets, including v101, where one manuscript glyph is exactly one
character and the alphabet has 166 symbols. Low entropy survives at 2.35 against 3.19
for Latin under the same encoding.

It is still a transcription-level result. The manuscript's own glyph inventory has been
analysed independently by others (Currier's alphabet, Davis's digital paleography).

## 6. The human-feasibility argument is an argument, not a measurement

`human_feasibility.py` measures how many candidates the model evaluates per accepted
word (1.33), how much prior text it needs to see (25 words suffice — the result is flat
from a 25-word to a 1500-word window), and which components are load-bearing on
ablation. From that it argues that a person could execute the procedure with the last
few lines in view.

That is a plausibility argument about a historical actor who cannot be consulted. It
does not show that anyone did this, and it cannot distinguish a deliberate procedure
from a computational model that happens to fit.

## 6b. The repetition profile is reproduced, at a measured price

The manuscript repeats words at **2.78 ×** the rate its own frequency spectrum permits
inside a paragraph, and at **1.15 ×** — statistically indistinguishable from
independent sampling, z = +1.0, 57 hits against 49.7 expected — across a paragraph break.
The within-paragraph figure is 1387 hits against 498.5 expected, z = +39.8.

Two earlier statements in this file were wrong and are withdrawn. The selectivity *can* be
reproduced, and the price is not four points. The mechanism — give each passage its own
pool, cleared at the break — first drew from that pool uniformly, including the word
immediately preceding. That inflates *adjacent identical words* from 21 % to 70 % error,
and since the target is measured at lags 2 to 6 a lag-1 repeat buys nothing. Excluding the
near neighbour cut the price on the selection split from about 2.5 points to 0.5.

| | within | ratio | across | ratio | 44-metric error |
|---|---|---|---|---|---|
| frozen configuration | 0.260 % | 0.85 × | 0.304 % | 0.99 × | 3.96 / 4.30 % |
| **manuscript** | **0.907 %** | **2.78 ×** | **0.374 %** | **1.15 ×** | — |
| with the passage pool | 0.859 % | **2.85 ×** | 0.274 % | 0.91 × | 4.50 / 6.09 % |

The within-paragraph ratio matches on both splits, so the mechanism is not fitting the
split it was found on. The price is 0.5 points on the selection split and 1.8 on the
reversed one; by this repository's rule that the reversed split arbitrates, the frozen
configuration leaves it off. That is a choice at a measured price rather than a gap.
`repetition_fix.py`.

## 7. The self-sustaining test has an artefact

`bootstrap_test.py` refits on the model's own output for eight rounds. It finds that
without free invention the vocabulary contracts monotonically. But the corpus passed to
each refit is truncated to 6000 words, so long-range effects of the full history are
discarded. The test was repeated with an accumulating corpus capped at 40000 words and
the collapse persisted, but the artefact is not fully excluded.

Cross-word MI decays under refitting in every variant tested, including the ones that
sustain everything else. That decay is unexplained.

## 8. The label result is about distributions, not about intent

`label_analysis.py` shows that the labels next to the drawings carry the surface
profile of a name list while lacking the length signature of names. It does not show
that anyone intended to mislead. "Constructed to invite name-matching" and "by-product
of the same generator that happens to look like names" are not distinguishable from
these statistics.

## 9. Nothing here bears on the physical manuscript

The dating (radiocarbon 1404–1438), the inks (McCrone 2009), the number of scribes
(Currier's two, Davis's five, and the dispute between them) are separate literatures and
are not addressed by any code in this repository. The text statistics are silent on
who wrote it, when, or whether every stroke is original.

## 10. Where the numbers come from

The full metric definitions are in the code, but two conventions matter when comparing
with published figures:

- **h2 is computed on EVA.** It drops to 1.85–2.35 depending on the alphabet; quoting a
  single figure without naming the alphabet is not meaningful. The README quotes EVA.
- **Two splits of the corpus appear in the code**: all loci, and body text only
  (paragraph loci, excluding labels and circular text). They give h2 = 1.893 and 1.842
  respectively. The structural metrics require the body-only split, because line and
  paragraph geometry only exists there.
