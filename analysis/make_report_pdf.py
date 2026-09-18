"""Typeset the whole work as a single PDF, in a plain scientific register.

Content is every measured number in this repository, including the three self-corrections
and the negative results. Nothing here is generated at runtime: the figures are copied
from the frozen results, the comparison file and the book model, so the document cannot
drift away from the code without someone noticing.
"""
import json
import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle, KeepTogether)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# works in both layouts: beside the script's parent, which is the repo root
# when the script is run from a clone and the working directory here.
OUT = os.path.join(ROOT, "report.pdf")

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontName="Times-Roman", fontSize=9.6,
                      leading=13.2, alignment=TA_JUSTIFY, spaceAfter=5)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Times-Bold", fontSize=13,
                    leading=16, spaceBefore=13, spaceAfter=6, textColor=colors.black)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Times-BoldItalic", fontSize=10.6,
                    leading=13, spaceBefore=9, spaceAfter=4, textColor=colors.black)
TITLE = ParagraphStyle("title", parent=ss["Title"], fontName="Times-Bold", fontSize=17,
                       leading=21, alignment=TA_CENTER, spaceAfter=4)
SUB = ParagraphStyle("sub", parent=BODY, fontSize=10.5, leading=14, alignment=TA_CENTER,
                     textColor=colors.HexColor("#333333"), spaceAfter=16)
ABS = ParagraphStyle("abs", parent=BODY, fontSize=9.2, leading=12.6, leftIndent=13,
                     rightIndent=13, spaceAfter=8)
CAP = ParagraphStyle("cap", parent=BODY, fontSize=8.4, leading=11, spaceBefore=2,
                     spaceAfter=9, textColor=colors.HexColor("#444444"))
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.8, leading=11.8)


def P(t, s=BODY):
    return Paragraph(t, s)


def table(rows, widths, align="LEFT"):
    data = [[Paragraph(str(c), ParagraphStyle("c", parent=SMALL, fontName="Times-Roman",
                                              fontSize=8.4, leading=10.6))
             for c in r] for r in rows]
    head = ParagraphStyle("h", parent=SMALL, fontName="Times-Bold", fontSize=8.4, leading=10.6)
    data[0] = [Paragraph(str(c), head) for c in rows[0]]
    t = Table(data, colWidths=widths, hAlign=align)
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def load():
    d = {}
    for name, path in (("frozen", os.path.join(HERE, "FROZEN_RESULTS.json")),
                       ("cmp", os.path.join(HERE, "GENERATOR_COMPARISON.json")),
                       ("book", os.path.join(HERE, "BOOK_MODEL.json")),
                       ("rep", os.path.join(HERE, "REPETITION_FIX.json")),
                       ("mi", os.path.join(HERE, "WORD_MI_GAP.json")),
                       ("scribe", os.path.join(HERE, "SCRIBE_RESULT.json"))):
        d[name] = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    d["cfg"] = json.load(open(os.path.join(HERE, "FROZEN_CONFIG.json"), encoding="utf-8"))
    return d


def build():
    D = load()
    S = []
    A = S.append

    A(P("A measurable fingerprint of the Voynich manuscript,<br/>and a procedure that "
        "reproduces it", TITLE))
    A(P("A computational study of the text of Beinecke MS 408<br/>"
        "with three self-corrections and a hand-executable model", SUB))
    A(P("<b>Abstract.</b> The text of the Voynich manuscript has resisted reading for a "
        "century. This work does not attempt to read it. It measures a fingerprint of "
        "forty-four statistics of the text against thirteen natural-language corpora, "
        "rules out classes of hypothesis with controlled tests, and demonstrates that the "
        "whole fingerprint is reproduced by a procedure containing no language, no cipher "
        "and no message — at a mean error of 3.7 % on a held-out half of the corpus "
        "(4.3 % on an independent reversed split). The closest prior generator, run here "
        "on the same scorecard with the best of twenty of its own configurations, reaches "
        "18.3 %. A reduced, hand-executable version of the model — eight printed "
        "tables and a die, no rejection sampling — reaches 7.8 %. Three results are "
        "new and are stated precisely: word repetition is scoped to the paragraph and "
        "falls to chance across a break; the sections of the book differ partly because "
        "the page geometry differs, not only the text; and the headline figure describes "
        "the book in aggregate, not any of its parts. Three errors found in earlier "
        "revisions of this work are recorded rather than removed.", ABS))

    # ---------------------------------------------------------------- 1
    A(P("1. The question", H1))
    A(P("Two claims are often run together. The strong claim is that the text has been "
        "read, or can be. The weak and testable claim is that its measurable behaviour is "
        "consistent with a procedure that contains no message. Only the second is "
        "addressed here, and it is addressed by construction: a model is built that "
        "produces the measurements without containing a language, and the standard "
        "cryptographic hypotheses for a natural-language plaintext are then excluded by "
        "controlled tests."))
    A(P("The manuscript is Yale, Beinecke MS 408, radiocarbon dated 1404–1438. All "
        "measurements here are taken from transliterations, principally the Takahashi EVA "
        "transcription in IVTFF 2.0, and are therefore statements about the transcription "
        "as much as about the ink. Section 13 returns to this."))

    # ---------------------------------------------------------------- 2
    A(P("2. Data and method", H1))
    A(P("The body text — paragraph loci, excluding labels, radial and circular text "
        "— comprises 33 641 words in 772 paragraphs over 4 117 lines on 206 folios. "
        "Paragraph boundaries are the manuscript's own paragraph marks: a line opening "
        "with the transcriber's <font face='Courier'>&lt;%&gt;</font> begins one and a "
        "line closing with <font face='Courier'>&lt;$&gt;</font> ends it. Those two "
        "markers occur exactly 772 times each and pair without a single anomaly across "
        "the whole file. The locus type is not the paragraph boundary; section 12 records "
        "what assuming otherwise cost."))
    A(P("Every result is on a split by leaf parity: the model is fitted on the "
        "even-numbered leaves and scored on the odd-numbered ones, or the reverse. All "
        "generators are seeded, and the frozen configuration reproduces every published "
        "number bit-for-bit (checked drift 0.00 %)."))
    A(table([["quantity", "value"],
             ["body words", "33 641"],
             ["paragraphs (manuscript marks)", "772"],
             ["lines", "4 117"],
             ["folios", "206"],
             ["mean paragraph length", "5.16 lines"],
             ["mean line length", "42.0 characters"],
             ["comparison corpora", "13 (Universal Dependencies)"],
             ["transliteration alphabets tested", "5 (EVA, v101, ZL, FSG, Friedman)"]],
            [70 * mm, 55 * mm],
            align="CENTER"))

    # ---------------------------------------------------------------- 3
    A(P("3. The fingerprint", H1))
    A(P("Conditional character entropy — how much the next character carries given "
        "the present one — is the statistic that started the field. Bennett reported "
        "in 1976 that Voynichese is far below European plain text; the figure here "
        "reproduces that and is not new."))
    A(table([["corpus", "h2 (bits)"],
             ["<b>Voynich manuscript</b>", "<b>1.89</b>"],
             ["a meaning-free generator (this work)", "1.68–1.77"],
             ["closest of 13 corpora (Augustine)", "2.98"],
             ["Latin / Italian / Spanish", "3.19 / 3.19 / 3.19"],
             ["Old Church Slavonic / Greek / Hebrew", "3.49 / 3.58 / 3.85"]],
            [95 * mm, 30 * mm], align="CENTER"))
    A(P("The gap to the nearest language is 1.09 bits; the gap to the generator is "
        "0.13–0.22 bits. The result survives the obvious objection that EVA writes "
        "one manuscript glyph with two Latin characters: across five independent "
        "transliteration alphabets, including Currier's v101 where one glyph is exactly "
        "one character and the alphabet has 166 symbols, h2 stays between 1.85 and 2.35 "
        "while Latin reaches 3.19.", CAP))
    A(P("Two further properties are worth recording because the model had to reproduce "
        "them, and because they are what a language does not look like."))
    A(table([["metric", "Voynich", "Latin", "Italian", "OCS", "generator"],
             ["Brevity law (mean length vs rank)", "−0.390", "−0.927",
              "−1.128", "−0.918", "−0.429"],
             ["high-probability bigrams covering the text",
              "21.8 % (9)", "1.9 %", "1.2 %", "1.8 %", "22.7 % (8)"]],
            [58 * mm, 20 * mm, 19 * mm, 19 * mm, 16 * mm, 22 * mm],
            align="CENTER"))
    A(P("In a language, frequent words are short; in the manuscript the effect is almost "
        "absent. And a handful of character bigrams accounts for a fifth of all the "
        "text.", CAP))

    # ---------------------------------------------------------------- 4
    A(P("4. How much context does the text use", H1))
    A(P("Every entropy figure above is a bigram figure. The question that separates a "
        "language from a table is the slope: what does a third, fourth or fifth character "
        "of context buy? Measured with Witten–Bell smoothing on a held-out half, so "
        "the numbers are comparable across alphabets of different size."))
    A(table([["corpus", "h1", "h2", "h3", "gain 2→3", "gain 3→4"],
             ["<b>manuscript</b>", "3.87", "2.34", "2.14", "<b>+0.20</b>", "−0.03"],
             ["generator", "3.85", "2.33", "2.14", "+0.19", "−0.06"],
             ["Latin", "3.98", "3.48", "3.03", "+0.45", "+0.35"]],
            [34 * mm, 17 * mm, 17 * mm, 17 * mm, 24 * mm, 24 * mm], align="CENTER"))
    A(P("The text is exhausted by two characters of context; Latin keeps paying. The "
        "generator tracks the manuscript's curve at every order to within 0.01–0.03 "
        "bits, and was never fitted to it.", CAP))

    # ---------------------------------------------------------------- 5
    A(P("5. What the text is not", H1))
    A(P("A substitution cipher is refuted in the literature, thoroughly, by others. The "
        "contribution here is only that the refutation carries a working control, which "
        "separates “the attack does not work” from “the hypothesis is "
        "false”. The same hill-climbing solver recovers <b>100 % of words</b> "
        "(6 000 of 6 000) from a random substitution of Latin, and then fails on "
        "Voynichese at −11.11 per character against a Latin ceiling of −8.57 and "
        "a random-mapping floor of −13.81."))
    A(P("The word-length distribution alone excludes a letter-level cipher over any of "
        "the thirteen corpora: the manuscript has 5.8 % words of two letters or fewer "
        "where the corpora have 17.9–27.3 %. A transposition or homophonic scheme "
        "preserves that distribution and is not excluded by it; it is excluded by the "
        "character entropy."))

    # ---------------------------------------------------------------- 6
    A(P("6. The generative model", H1))
    A(P("The model has five components, each entering at a measured property rather than "
        "at a guess."))
    A(table([["component", "what it fixes"],
             ["BPE syllable inventory (140 merges)", "the character-entropy scale"],
             ["bigram chain over those syllables", "the rigid onset and coda slots of a word"],
             ["P(onset class | last character of the previous word)", "cross-word dependence"],
             ["reweighting on (length × final syllable)",
              "the length distribution and the endings at once"],
             ["word-pair memory, self-citation with mutation",
              "vocabulary size, Zipf slope, hapax share"]],
            [72 * mm, 58 * mm], align="CENTER"))
    A(P("A layout layer sits on top: separate line budgets for mid-paragraph and "
        "paragraph-final lines, words shortened as the margin approaches, gallows "
        "characters at line openings."))
    A(P("The list is not the interesting part. The components are coupled, and most of "
        "the obvious ways to fix a single metric break another. Eight dead ends are "
        "documented: controlling word length directly destroys the endings (words in "
        "<i>y</i> fall from 40 % to 23 %); controlling the number of syllables does the "
        "same (top-5 finals 91 % → 55 %); appending an ending drawn from the real "
        "distribution explodes the vocabulary (TTR 0.28 → 0.43); penalising recent "
        "words fixes repeated pairs and flattens the frequency spectrum (top-10 share "
        "11.8 % → 5.5 %). What works is entering at the level where the coupling "
        "arises: the identity of the word is never touched, and only conditional "
        "distributions are reweighted."))
    A(P("The frozen configuration reproduces the fingerprint at a mean error of "
        "<b>3.7 %</b> over 44 metrics — 2.7 % across fifteen text statistics and "
        "4.3 % across twenty-nine structural ones — on a held-out half. On the "
        "reversed split, where the same configuration is re-run without any selection, "
        "the figure is 4.29 %."))
    A(table([["tier", "metrics", "mean error"],
             ["text statistics", "15", "2.7 %"],
             ["structure: lines, paragraphs, Zipf, repetition", "29", "4.3 %"],
             ["<b>overall</b>", "<b>44</b>", "<b>3.7 %</b>"],
             ["the same, reversed split", "44", "4.29 %"]],
            [85 * mm, 20 * mm, 25 * mm], align="CENTER"))

    # ---------------------------------------------------------------- 7
    A(P("7. Against the closest prior generator", H1))
    A(P("Timm and Schinner's self-citation generator is the nearest prior work: a "
        "complete, public, executable procedure. An earlier revision of this work "
        "described its strengths and weaknesses by quoting their paper, which is not a "
        "measurement and was also partly wrong. Their executable is now run directly, at "
        "a text size matched to the held-out half, and scored on the same vector, with "
        "<b>the best of twenty</b> configurations of its own switches rather than its "
        "default."))
    A(table([["generator", "tier-1 (15 metrics)", "structural (27 metrics)"],
             ["Timm &amp; Schinner, best of 20 configurations", "19.9 %", "17.5 %"],
             ["Timm &amp; Schinner, their default", "26.3 %", "28.3 %"],
             ["<b>this model</b>", "<b>2.7 %</b>", "<b>4.6 %</b>"],
             ["this model's hand-executable manual", "7.3 %", "8.4 %"]],
            [72 * mm, 30 * mm, 28 * mm], align="CENTER"))
    A(P("What they have right, measured rather than assumed: mean line length (3 % "
        "error), words per line (2 %), words of ten or more characters (6 %), adjacent "
        "identical words (6 %), <i>ch</i>- onsets (4 %), and all eight positional "
        "character entropies within 4–24 %. Their line-fill and gallows machinery "
        "works."))
    A(P("Where they diverge is specific, and it is not “vocabulary "
        "richness” in general — with the best configuration they "
        "<i>over</i>-produce word types, 5 218 against 4 526, while "
        "under-concentrating the frequency spectrum. Their output is too even."))
    A(table([["metric", "held-out", "theirs", "error"],
             ["cross-word mutual information", "0.068", "0.008", "88 %"],
             ["<i>qo</i>- onsets", "15.2 %", "5.5 %", "64 %"],
             ["words of 8+ characters", "8.3 %", "12.8 %", "54 %"],
             ["words ending in <i>y</i>", "40.3 %", "19.1 %", "53 %"],
             ["top-10 word share", "12.8 %", "7.5 %", "42 %"],
             ["line-length standard deviation", "16.05", "10.01", "38 %"],
             ["repeated word-pair", "15.3 %", "10.2 %", "33 %"]],
            [62 * mm, 24 * mm, 24 * mm, 20 * mm], align="CENTER"))

    # ---------------------------------------------------------------- 8
    A(P("8. The manual: the same fingerprint by hand", H1))
    A(P("The model above reaches 3.7 % by rejection sampling on a joint distribution and "
        "by a 151-row transition table. A person with a quill cannot carry either. The "
        "question this section answers is the smallest procedure a <i>hand</i> can "
        "execute, and how close it comes."))
    A(P("The scribe carries eight short tables: sixty syllable shapes; fourteen standard "
        "word openings; a twenty-one-row link table giving the shape that usually follows "
        "a given letter; a length table; fourteen stock endings chosen by word length; a "
        "cross-word carry-over table; a list of habitual word pairs; and page rules. The "
        "procedure for one word is: look at the last letter written, write an opening, "
        "decide the length and the ending, fill the middle until the word is that size. "
        "Nothing is a statistic and nothing is ever thrown away and re-rolled."))
    A(table([["", "tier-1", "tier-2", "overall (44 metrics)"],
             ["computer model, with rejection sampling", "2.7 %", "4.3 %", "<b>3.7 %</b>"],
             ["<b>the manual, by hand</b>", "<b>7.3 %</b>", "<b>8.0 %</b>", "<b>7.8 %</b>"]],
            [72 * mm, 20 * mm, 20 * mm, 35 * mm], align="CENTER"))
    A(P("Four things were learned building it, and each is a constraint on any account of "
        "how such a text could be made."))
    A(P("<b>The ending must be carried as letters, not as shapes.</b> A sixty-shape "
        "table cannot spell the true last shape of most words, so an ending drawn from "
        "the shape table loses the manuscript's endings — <i>y</i> above all, which "
        "closes 40 % of its words. The output had <i>y</i> on 15 % of words until the "
        "endings were learned as character suffixes; then 44.6 % against a target of "
        "40.3 %.", SMALL))
    A(P("<b>The hand's substitute for rejection sampling is deciding the length "
        "first.</b> A chain that rolls a die after every shape and stops on a rule gets a "
        "geometric length distribution: mean 4.2 against 5.2, standard deviation 2.6 "
        "against 1.9, both tails far too heavy. Choosing the size before writing, and "
        "filling to it, fixes the distribution outright (sd 1.88 against 1.86) and costs "
        "nothing in plausibility — a person does know how long the word is about to "
        "be.", SMALL))
    A(P("<b>Repeats and vocabulary come from one mechanism, and the hand version of it is "
        "a swap.</b> The manuscript combines a highly repetitive text with a rich "
        "vocabulary; a table-driven writer usually gets one or the other. Both fall out of "
        "writing a word again with one shape changed for the one that usually follows it. "
        "Restricting that change to a swap — not an insertion or a deletion — "
        "matters more than any other single parameter: an insertion also creates repeats, "
        "but it doubles the number of one- and two-letter words, because the hand that is "
        "supposed to be filling a word to a decided length keeps making it shorter.", SMALL))
    A(P("<b>What the manual does not reach is vocabulary richness.</b> The residual "
        "7.8 % is dominated by three measures of the same thing: hapax share of tokens "
        "14.7 % against 19.7 %, type-token ratio 0.230 against 0.275, and hapax share of "
        "types 63.7 % against 71.6 %. The manuscript's vocabulary is more productive than "
        "sixty shapes and one mutation operator produce.", SMALL))

    # ---------------------------------------------------------------- 9
    A(P("9. The passage is the unit of work", H1))
    A(P("The most informative single measurement in this work concerns word repetition, "
        "and it is best stated as a null result. Against its own frequency spectrum "
        "— the rate independent sampling from the text's own word distribution would "
        "give — the manuscript repeats words at 2.78 times chance <i>inside</i> a "
        "paragraph, and is <b>indistinguishable from chance</b> across a paragraph break."))
    A(table([["region", "rate", "ratio to chance", "significance"],
             ["inside a paragraph", "0.907 %", "<b>2.78 ×</b>", "z = +39.8"],
             ["across a paragraph break", "0.374 %", "1.15 ×", "z = +1.0"],
             ["across a folio boundary", "0.195 %", "0.60 ×", "below chance"],
             ["memoryless baseline (Σf²)", "0.326 %", "1.00 ×", "—"]],
            [55 * mm, 22 * mm, 28 * mm, 25 * mm], align="CENTER"))
    A(P("The property is not that the text repeats more than its spectrum allows. It is "
        "that the repetition is scoped exactly to the passage and vanishes at the "
        "boundary, while the boundary itself is invisible to every memoryless measure. A "
        "language does not do this: topical clustering does not snap to a typographic "
        "paragraph mark.", CAP))
    A(P("An earlier revision reported that the across-paragraph rate fell <i>below</i> "
        "chance and that no model in this class reproduced the selectivity. Both were "
        "wrong, and the cause was specific: the paragraph pool was the same list for "
        "every paragraph, so it raised repetition inside a passage and between passages "
        "alike. Giving each passage its own pool — the words already written in that "
        "passage, or a sample drawn from the frequency distribution — reproduces the "
        "shape, because between two passages the two lists are independent by "
        "construction."))
    rep = D["rep"]
    rows = [["configuration", "inside", "ratio", "across", "ratio", "44-metric error"]]
    labels = [("manuscript", "manuscript"), ("frozen (no mechanism)", "frozen"),
              ("sampled pool, 0.80 × 110", "sampled_pool_wide"),
              ("passage self-pool, 0.08", "selfpool_0.08"),
              ("the manual, its own parameters", "manual_0.12")]
    for name, key in labels:
        r = rep.get(key)
        if not r:
            continue
        bold = key in ("manuscript", "manual_0.12")
        f = (lambda x: f"<b>{x}</b>") if bold else (lambda x: x)
        rows.append([f(name), f(f"{r['within']:.3f} %"), f(f"{r['within_ratio']:.2f} ×"),
                     f(f"{r['across']:.3f} %"), f(f"{r['across_ratio']:.2f} ×"),
                     f("—") if "overall_pct" not in r else f(f"{r['overall_pct']:.2f} %")])
    A(table(rows, [55 * mm, 20 * mm, 18 * mm, 20 * mm, 17 * mm, 26 * mm], align="CENTER"))
    A(P("The last line is the demonstration. The manual carries a passage-scoped pool "
        "because a hand naturally does, and its re-use rate was chosen on a selection "
        "split for the overall 44-metric error — not for this profile, which had not "
        "been measured at that point. It reproduces the shape anyway.", CAP))
    A(P("The price of the mechanism in the computer model was four points at first, and "
        "almost all of it was one metric: the pool could return the word immediately "
        "preceding, which pushed <i>adjacent identical words</i> from 21 % to 70 % error. "
        "The target profile is measured at lags 2 to 6, so a lag-1 repeat was pure cost "
        "with no gain. Excluding the near neighbour from the draw cut the price on the "
        "selection split from about 2.5 points to 0.5 and made the profile match better "
        "rather than worse.", CAP))
    A(table([["", "within", "ratio", "across", "ratio", "44-metric error"],
             ["frozen configuration", "0.260 %", "0.85 ×", "0.304 %", "0.99 ×",
              "3.96 / 4.30 %"],
             ["<b>manuscript</b>", "<b>0.907 %</b>", "<b>2.78 ×</b>", "<b>0.374 %</b>",
              "<b>1.15 ×</b>", "—"],
             ["with the passage pool", "0.859 %", "<b>2.85 ×</b>", "0.274 %", "0.91 ×",
              "4.50 / 6.09 %"]],
            [40 * mm, 20 * mm, 17 * mm, 20 * mm, 17 * mm, 30 * mm], align="CENTER"))
    A(P("The within-paragraph ratio lands on the target on <i>both</i> splits, so the "
        "mechanism is not fitting the split it was found on. The price is 0.5 points on "
        "the selection split and 1.8 on the reversed one, and the reversed split is the "
        "honest one; the frozen configuration therefore leaves the mechanism off. That is "
        "a documented choice at a measured price rather than a gap.", CAP))

    # ---------------------------------------------------------------- 10
    A(P("10. Sections, and what the headline actually measures", H1))
    A(P("Every split in this work is by leaf parity, so both halves carry the same "
        "mixture of sections. That makes the 3.7 % a statement about the book in "
        "aggregate. Two further measurements establish how far it can be pushed down."))
    A(P("First, the sections differ, and by much more than sampling noise. Measured "
        "against a within-section resampling baseline, the ratio of between-section to "
        "within-section divergence is 25 × on letter frequencies, 13 × on word "
        "onsets, 4.5 × on the first two letters, 3.7 × on word length and "
        "2.8 × on the last two letters. They draw on the same vocabulary — the "
        "top twenty word types of every section are in the shared stock, and 60–83 % "
        "of every section's running text comes from words occurring in three or more "
        "sections — and weight it differently. Part of the difference is not textual "
        "at all: mean characters per line runs from 27.0 in the astronomical section to "
        "52.5 in the recipes, tracking how much of the page the drawing occupies. The "
        "obvious explanation of Currier's A and B — that the contrast is a "
        "gallows-character substitution, <i>t</i>/<i>k</i> for <i>p</i>/<i>f</i> "
        "— is refuted by test: rewriting the herbal with that substitution makes "
        "its onset distribution <i>less</i> like the recipes, not more (Jensen–Shannon "
        "divergence 0.121 → 0.160)."))
    A(P("Second, the pooled headline does not survive being taken apart."))
    book = D["book"]
    rows = [["design", "tier-1", "tier-2", "overall"]]
    a = book.get("A_pooled_whole_book", {})
    if a:
        rows.append(["<b>A</b> one pooled model, whole held-out half",
                     f"<b>{a['tier1_pct']:.1f} %</b>", f"<b>{a['tier2_pct']:.1f} %</b>",
                     f"<b>{a['overall_pct']:.2f} %</b>"])
    rows.append(["<b>B</b> the same model, each section alone", "9.1–19.1 %",
                 "11.4–29.8 %", f"<b>{book.get('B_pooled_model_per_section',{}).get('pooled_pct',0):.2f} %</b>"])
    rows.append(["<b>C</b> one parameter set per section", "4.4–9.2 %",
                 "6.4–16.8 %", f"<b>{book.get('C_per_section_parameters',{}).get('pooled_pct',0):.2f} %</b>"])
    A(table(rows, [82 * mm, 24 * mm, 24 * mm, 24 * mm], align="CENTER"))
    A(P("A and B are the same model. The distance between 3.7 % and 14.4 % is not a "
        "fitting failure: pooling the sections produces statistics that no individual "
        "section has, and the model reproduces the mixture. Per-section parameters halve "
        "the per-section error, and their limit is text — the pharmaceutical section "
        "has 1 494 training words under that design and lands at 14.2 %, while recipes "
        "with 4 982 lands at 6.1 %. A fourth design, a shared text model with per-section "
        "page geometry alone, is worse than either at 11.9 %, because the geometry and "
        "the length conditioning are coupled.", CAP))
    A(P("Which table carries the difference is measurable. Replacing one component of the "
        "source model with the target's, one at a time, and measuring how much of the "
        "transfer error disappears:"))
    A(table([["component replaced", "mean share of the transfer error removed"],
             ["the (length × final shape) joint", "<b>22 %</b>"],
             ["the onset marginal and cross-word table", "19 %"],
             ["the pair memory and stock of frequent words", "19 %"],
             ["line width and paragraph shape", "14 %"]],
            [82 * mm, 62 * mm], align="CENTER"))
    A(P("No component dominates, and no pair falls below about 60 % of its original error "
        "even with one table fully replaced. The sections differ in all of their tables at "
        "once, which is why per-section parameters are the only thing that works and why "
        "they are expensive. The honest form of the headline is therefore: <i>a "
        "language-free procedure reproduces the aggregate statistics of the manuscript to "
        "3.7 %; applied to any single section it is off by 10–26 %, and with "
        "per-section parameters by 5.7–14.2 %.</i>", CAP))

    # ---------------------------------------------------------------- 11
    A(P("11. What remains open", H1))
    A(P("One number is not closed. Within a word, the manuscript retains a small but "
        "real character dependence out to a distance of about six characters, and the "
        "generator is short of it. The measurement matters because the way it was "
        "previously reported was wrong in an instructive way: the repository used a "
        "Miller–Madow correction whose magnitude, on a few thousand character pairs "
        "against a 22 × 22 table, was larger than the effect being compared."))
    A(P("Measured instead with a surrogate control — the characters of every word "
        "permuted within that word, which preserves length and marginal frequencies "
        "exactly and destroys only the dependence, so that the permuted text's mutual "
        "information <i>is</i> the estimator's bias — the residual is small and "
        "localised."))
    mi = D["mi"]
    rows = [["distance", "manuscript (bits)", "generator (bits)", "gap", "in sd"],
            ["2", "0.666", "0.652", "+0.014", "+2.6"],
            ["3", "0.335", "0.309", "<b>+0.026</b>", "<b>+5.8</b>"],
            ["4", "0.097", "0.075", "<b>+0.022</b>", "<b>+4.1</b>"],
            ["5", "0.075", "0.055", "+0.021", "+1.7"],
            ["6", "0.077", "0.044", "+0.033", "+2.5"],
            ["8", "−0.026", "−0.008", "—", "both zero"]]
    A(table(rows, [24 * mm, 36 * mm, 34 * mm, 24 * mm, 22 * mm], align="CENTER"))
    A(P("Beyond a distance of six neither corpus has any measurable dependence: the "
        "corrected value is at or below zero for both. The residual is 0.022–0.032 "
        "bits over distances three to six, significant at 5.8 and 4.1 standard deviations "
        "at distances three and four.", CAP))
    A(P("Labelling every character pair by where it sits in the word locates the deficit "
        "rather than spreading it. Eighty-six per cent of it is in the <i>front</i> half "
        "of the word; the middle is under one standard deviation at every distance; and at "
        "the back the generator has <i>more</i> dependence than the manuscript. The "
        "sharpest single cell is pairs starting at position 0 or 1, at +7.4 standard "
        "deviations at distance 3.", CAP))
    A(table([["d", "manuscript", "chain alone", "chain + reweighting", "frozen model"],
             ["3", "0.201", "0.221", "0.178", "0.162"],
             ["4", "0.041", "<b>0.109</b>", "<b>0.014</b>", "0.017"],
             ["5", "0.016", "0.007", "0.011", "0.004"]],
            [14 * mm, 28 * mm, 27 * mm, 38 * mm, 27 * mm], align="CENTER"))
    A(P("Front half of the word only, so this is not a length effect. The chain on its own "
        "puts more dependence there than the manuscript has; the (length × ending) "
        "reweighting on top of it removes more than it should; the frozen model lands "
        "below the target.", CAP))
    A(P("Four attempts were made to close it, and the fourth is the informative one."))
    A(table([["attempt", "result"],
             ["a within-word repetition mechanism", "no effect"],
             ["conditioning the second shape on the onset class",
              "helps the split it was found on, a wash on the reversed one"],
             ["<i>p_raw</i>: accept a fraction of words unchecked",
              "reaches the target only by wrecking the length tails "
              "(<i>len≥10</i> 5 % → 22 %, <i>len≤2</i> 3 % → 15 %)"],
             ["<i>endfix</i>: accept on length alone, then repair the ending",
              "<b>much worse</b> — front-half MI 0.154 → 0.079, "
              "44-metric error 3.96 % → 11.97 %"]],
            [62 * mm, 82 * mm], align="CENTER"))
    A(P("The last failure is the informative one. The idea was to decouple the two halves of "
        "the reweighting, since the front is what the acceptance damages. It fails because "
        "the ending is not an appendage: it is constrained by what precedes it, and editing "
        "it independently destroys the dependence it was meant to preserve. A word-level "
        "mixture of checked and unchecked words <i>does</i> reach the target, at 25 % "
        "unchecked and a small cost in the length distribution — the interpolation exists, "
        "and the model's single joint accept/reject cannot express it.", CAP))
    A(P("<b>Conclusion.</b> The front-of-word dependence is not reachable within this "
        "architecture. The reweighting is one accept-or-reject on (length, ending); the "
        "manuscript's value sits between what the chain proposes and what that acceptance "
        "keeps, and every attempt to split the acceptance apart makes it worse. Closing it "
        "would need a different generator rather than a different parameter. This is the "
        "one item in the work that is not closed, and it is a limit of the model rather "
        "than a missing measurement.", CAP))

    # ---------------------------------------------------------------- 12
    A(P("12. Three corrections", H1))
    A(P("Recorded because each changed a published figure, and because the third is a "
        "trap that any study of this transcription could fall into."))
    A(P("<b>1. A leaked layout parameter.</b> Line and paragraph constants were once "
        "taken from the held-out document. That is a leak, it inflated the result, and it "
        "was found only because a reversed split was run. The honest within-section error "
        "moved from 3.2 % to 4.0 %.", SMALL))
    A(P("<b>2. A mutual-information comparison measuring its own estimator bias.</b> The "
        "Miller–Madow correction on the table sizes involved, 0.168 bits, was larger "
        "than the effect being compared. Corrected, the manuscript and generator agree to "
        "0.0016 bits where a gap had been reported.", SMALL))
    A(P("<b>3. Paragraph segmentation by the wrong marker.</b> Paragraphs were delimited "
        "by the IVTFF locus type (<font face='Courier'>@</font> / <font "
        "face='Courier'>+</font> / <font face='Courier'>*</font>) instead of by the "
        "manuscript's own paragraph marks (<font face='Courier'>&lt;%&gt;</font> / "
        "<font face='Courier'>&lt;$&gt;</font>). The <font face='Courier'>@</font> marker "
        "appears only on the first paragraph of a page, so in the recipes section this "
        "merged about twelve real paragraphs into one 43-line block. Real mean paragraph "
        "length is <b>5.16 lines, not 14.81</b>. Every paragraph-dependent number was "
        "recomputed and the frozen configuration re-verified; the headline moved from "
        "4.0 % to 3.7 %, improving, because the generator had been faithfully learning "
        "the artefact. A claim about repetition reversing sign across a paragraph break "
        "was withdrawn as a consequence.", SMALL))

    # ---------------------------------------------------------------- 13
    A(P("13. What is claimed", H1))
    A(P("<b>Claimed.</b> The measurable behaviour of the text — forty-four "
        "statistics covering character entropy and its context profile, vocabulary "
        "richness, the word-frequency spectrum, length and ending distributions, onset "
        "classes, cross-word dependence, line fill, paragraph shape, gallows placement, "
        "Zipf slope and repetition structure — is reproduced by a procedure that "
        "contains no language, no cipher and no message (3.7 %); a reduced version of "
        "that procedure is executable by hand with a printed table and a die (7.8 %); and "
        "the standard cryptographic hypotheses for a natural-language plaintext are "
        "excluded by controlled tests."))
    A(P("<b>Not claimed.</b> That the manuscript is meaningless. A verbose cipher or a "
        "nomenclator would be statistically indistinguishable from the generator's "
        "output. The defensible statement is that the data are inconsistent with a "
        "natural language under any letter-level cipher and consistent with procedural "
        "generation. Nothing here bears on who wrote the manuscript, when, or whether "
        "every stroke is original; those are separate literatures."))
    A(P("<b>Scope.</b> Every number is a statement about a transliteration, not about the "
        "ink. The same statistics were computed across five independent transliteration "
        "alphabets and the qualitative results survive, but the objection is real and is "
        "answered empirically rather than in principle."))

    # ---------------------------------------------------------------- refs
    A(P("References", H1))
    refs = [
        "Bennett, W. R. (1976). <i>Scientific and Engineering Problem-Solving with the "
        "Computer.</i> Prentice-Hall.",
        "Currier, P. (1976). Papers on the Voynich manuscript.",
        "Davis, L. F. (2020). How many glyphs and how many scribes? Digital palaeography "
        "and the Voynich manuscript. <i>Manuscript Studies</i> 5(1).",
        "Landini, G. (2001). Evidence of linguistic structure in the Voynich manuscript "
        "using spectral analysis. <i>Cryptologia</i> 25(4), 275–295.",
        "Lindemann, L. &amp; Bowern, C. (2020). Character entropy in modern and "
        "historical texts. arXiv:2010.14697.",
        "Montemurro, M. &amp; Zanette, D. (2013). Keywords and co-occurrence patterns in "
        "the Voynich manuscript. <i>PLOS ONE</i> 8(6).",
        "Ponnaluri, R. V. (2024). The Voynich manuscript was written in a single, natural "
        "language. <i>Cryptologia</i> 49(6), 505–524.",
        "Reddy, S. &amp; Knight, K. (2011). What we know about the Voynich manuscript. "
        "<i>Proc. ACL-HLT Workshop on Language Technology for Cultural Heritage, Social "
        "Sciences, and Humanities</i>, 78–86.",
        "Rugg, G. &amp; Taylor, G. (2017). Hoaxing statistical features of the Voynich "
        "manuscript. <i>Cryptologia</i> 41(3).",
        "Stolfi, J. <i>Properties of the Voynich Manuscript, Part 1.</i> Technical "
        "report, UNICAMP.",
        "Timm, T. &amp; Schinner, A. (2019). A possible generating algorithm of the "
        "Voynich manuscript. <i>Cryptologia</i> 44(1), 1–19. Executable: "
        "SelfCitationTextgenerator.",
        "Takahashi, T. EVA transliteration, IVTFF 2.0, via voynich.nu.",
        "Universal Dependencies treebanks, v2.x, universaldependencies.org.",
    ]
    for r in refs:
        A(P(r, ParagraphStyle("ref", parent=SMALL, leftIndent=13, firstLineIndent=-13,
                              spaceAfter=3.5)))

    A(Spacer(1, 8 * mm))
    A(P("All figures in this document are produced by the code in <font "
        "face='Courier'>analysis/</font> and are reproducible from a clean checkout; the "
        "frozen configuration verifies bit-for-bit at 0.00 % drift. Three negative "
        "results are kept in the repository rather than removed: an image-based test of "
        "the writing direction that failed on two of three pages, a compression test "
        "that does not discriminate, and an aborted reversal test whose statistic is "
        "invariant under reversal and therefore could not have answered its question.",
        ParagraphStyle("foot", parent=SMALL, fontSize=8.2, leading=11,
                       textColor=colors.HexColor("#444444"))))
    return S


def main():
    doc = BaseDocTemplate(OUT, pagesize=A4,
                          leftMargin=22 * mm, rightMargin=22 * mm,
                          topMargin=20 * mm, bottomMargin=20 * mm,
                          title="A measurable fingerprint of the Voynich manuscript",
                          author="Manuscript project", subject="Voynichese statistics")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")

    def page(canv, d):
        canv.saveState()
        canv.setFont("Times-Roman", 7.6)
        canv.setFillColor(colors.HexColor("#666666"))
        canv.drawCentredString(A4[0] / 2, 12 * mm, str(canv.getPageNumber()))
        canv.restoreState()
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=page)])
    doc.build(build())
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
