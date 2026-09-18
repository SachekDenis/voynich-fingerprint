"""The paragraph-reset repetition: what the target is, and what reproduces it.

This was the one measured property the model knowingly missed. It is now reproduced,
and the mechanism turns out to be the one a hand would use.

THE TARGET. Repeat rate at lags 2-6 pooled, for word pairs inside a paragraph against
pairs that cross a paragraph break, measured on the manuscript:

    inside a paragraph   0.907 %   2.78 x the memoryless baseline   z = +39.8
    across a boundary    0.374 %   1.15 x the baseline              z = +1.0
    baseline (sum f^2)   0.326 %

The second line is the important one. Against its own frequency spectrum, the
across-paragraph rate is **indistinguishable from independent sampling** (one standard
deviation), while the within-paragraph rate is forty standard deviations above it. So
the property is not that the text repeats more; it is that the repetition is scoped
exactly to the passage.

THE MECHANISM. Draw the word from the words already written *in this paragraph*, and
clear that list at the paragraph break. Inside a passage a word already used is more
likely to come up again; between two passages the two lists are independent, so the
rate falls back to chance. No parameter of that description is fitted to the target --
the mechanism either has the shape or it does not.

WHY THE EARLIER ATTEMPT FAILED. The first pool gave every paragraph the same working
set (the N most frequent words). That raises repetition inside a passage *and* between
any two passages, because both paragraphs draw from the same list. Sampling the pool
from the frequency distribution instead (pool_mode="sample") fixes the shape and also
works -- see the sweep -- but it costs more on the rest of the vector, because a word
drawn from a fixed pool loses the length and ending conditioning.

WHAT IT COST, AND WHY. It first looked like a four-point price. Almost all of that was
one metric: the pool drew the word immediately preceding, which pushed "adjacent
identical words" from 21 % to 70 % error. The target profile is measured at lags 2 to 6,
so a lag-1 repeat was pure cost for no gain. Excluding the near neighbour from the draw
cut the price on the selection split from about 2.5 points to 0.5 and made the profile
match *better*, not worse.

           within  ratio   across  ratio    44-metric error
frozen      0.260 %  0.85x   0.304 %  0.99x   3.96 % / 4.30 %  (normal / reversed)
manuscript  0.907 %  2.78x   0.374 %  1.15x
with pool   0.859 %  2.85x   0.274 %  0.91x   4.50 % / 6.09 %

The within-paragraph ratio now lands on the target on *both* splits, so the mechanism is
not fitting the split it was seen on. The price is 0.5 points on the selection split and
1.8 on the reversed one, which is why the frozen configuration still leaves it off: the
honest headline is the reversed one, and it is not free there.

A second price is documented in `word_mi_position.py`: p_raw, the analogous mechanism for
the front-of-word dependence, reaches the target only by wrecking the length tails.
"""
import json
import os
import random
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tier2_metrics import measure_document, GALLOWS
from voynich_artgen import ArtGenerator
from tune_artgen import split_by_folio, flatten, tier1, err
from repetition_origin import split_with_context
from scribe_method import Manual, make_scribe, scribe_document, split_with_folios

HERE = os.path.dirname(os.path.abspath(__file__))
LAGS = (2, 3, 4, 5, 6)


def profile_words(words, unit):
    """(inside %, across %, memoryless baseline %) over the given lags."""
    N = len(words)
    a_n = a_h = b_n = b_h = 0
    for lag in LAGS:
        for i in range(N - lag):
            if unit[i] != unit[i + lag]:
                b_n += 1
                b_h += words[i] == words[i + lag]
            else:
                a_n += 1
                a_h += words[i] == words[i + lag]
    c = Counter(words)
    base = 100 * sum((v / N) ** 2 for v in c.values())
    return 100 * a_h / a_n, 100 * b_h / b_n, base


def profile_doc(doc):
    words, unit = [], []
    for pi, p in enumerate(doc):
        for ln in p:
            for w in ln:
                words.append(w)
                unit.append(pi)
    return profile_words(words, unit)


def build(cfg):
    tr_doc, te_doc = split_by_folio()
    train_words = flatten(tr_doc)
    g = ArtGenerator(train_words, merges=cfg["merges"])
    g.calibrate()
    g.calibrate_onset(train_words)
    g.calibrate_cross_onset(train_words)
    g.calibrate_common(train_words)
    g.calibrate_pairs(train_words)
    g.calibrate_lengths(tr_doc)
    g.fit_penalty = cfg["fit_penalty"]
    g.calibrate_proposal()
    g.calibrate_layout(tr_doc, gallows_p=0.0)
    g.gallows_scale = cfg["gallows_scale"]
    real2, _ = measure_document(te_doc)
    probe = [ln for p in g.document(40, seed=3) for ln in p]
    nat = sum(1 for ln in probe if ln and any(ln[0].startswith(x) for x in GALLOWS)) / len(probe)
    g.line_gallows_p = max(0.0, (real2["para/line-initial gallows %"] / 100 - nat) / (1 - nat))
    return g, te_doc, real2


def generate(g, real2, cfg, **over):
    kw = dict(p_copy=cfg["p_copy"], recency_alpha=cfg["recency_alpha"],
              recency_window=cfg["recency_window"], buffer_size=cfg["buffer_size"],
              cross_onset=cfg["cross_onset"], use_onset=cfg["use_onset"],
              gallows_scale=cfg["gallows_scale"], p_repeat=cfg["p_repeat"],
              p_pair=cfg["p_pair"], copy_decay=cfg["copy_decay"],
              line_fit=cfg["line_fit"])
    kw.update(over)
    return g.document(real2["paras"], seed=cfg["seeds"][0], **kw)


def cost(doc, te_doc, te_words, real2):
    gw = flatten(doc)
    t1 = tier1(gw, te_words)
    t2, _ = measure_document(doc)
    e1 = sum(err(*t1[k]) for k in t1) / len(t1)
    e2 = sum(err(t2[k], real2[k]) for k in real2) / len(real2)
    return e1, e2, (e1 * 15 + e2 * 29) / 44


def main():
    cfg = json.load(open(os.path.join(HERE, "FROZEN_CONFIG.json"), encoding="utf-8"))
    cfg = dict(cfg, p_selfpool=0.0, p_selfmut=0.0, p_pool=0.0, pool_size=0, pool_mode="top")
    tr_doc, te_doc = split_by_folio()
    te_words = flatten(te_doc)
    real2, _ = measure_document(te_doc)

    mw, mp, mf, ml = split_with_context()
    t_in, t_out, t_base = profile_words(mw, mp)
    print("manuscript (lags 2-6 pooled):")
    print(f"  inside {t_in:.3f}%  ({t_in/t_base:.2f}x)   across {t_out:.3f}%  "
          f"({t_out/t_base:.2f}x)   baseline {t_base:.3f}%\n")

    print(f"  {'configuration':26s} {'within':>7s} {'w/base':>7s} {'across':>7s} "
          f"{'a/base':>7s} | {'tier-1':>7s} {'tier-2':>7s} {'overall':>8s}")
    print("  " + "-" * 84)

    def row(label, doc):
        i, o, b = profile_doc(doc)
        e1, e2, ov = cost(doc, te_doc, te_words, real2)
        print(f"  {label:26s} {i:6.3f}% {i/b:6.2f}x {o:6.3f}% {o/b:6.2f}x | "
              f"{e1:6.1f}% {e2:6.1f}% {ov:7.2f}%")
        return dict(within=i, across=o, baseline=b, within_ratio=i / b,
                    across_ratio=o / b, tier1_pct=e1, tier2_pct=e2, overall_pct=ov)

    g, _, _ = build(cfg)
    out = {"manuscript": dict(within=t_in, across=t_out, baseline=t_base,
                              within_ratio=t_in / t_base, across_ratio=t_out / t_base)}
    out["frozen"] = row("frozen (no mechanism)", generate(g, real2, cfg))
    out["selfpool_0.08"] = row("passage self-pool 0.08",
                               generate(g, real2, cfg, p_selfpool=0.08, p_selfmut=0.25))
    out["selfpool_0.10"] = row("passage self-pool 0.10",
                               generate(g, real2, cfg, p_selfpool=0.10, p_selfmut=0.25))
    out["sampled_pool"] = row("sampled pool 0.65 x 72",
                              generate(g, real2, cfg, p_pool=0.65, pool_size=72,
                                       pool_mode="sample"))
    out["sampled_pool_wide"] = row("sampled pool 0.80 x 110",
                                   generate(g, real2, cfg, p_pool=0.80, pool_size=110,
                                            pool_mode="sample"))

    # the hand-executable manual, whose passage pool was chosen for the whole 44-metric
    # error and not for this profile at all
    res = json.load(open(os.path.join(HERE, "SCRIBE_RESULT.json"), encoding="utf-8"))
    par, fol = split_with_folios()
    even = [(p, f) for p, f in zip(par, fol)
            if int(re.match(r"f?(\d+)", f).group(1)) % 2 == 0]
    tr = [w for p, _ in even for ln in p for w in ln]
    man = Manual(tr, n_forms=res["n_forms"])
    lines = [ln for p in te_doc for ln in p]
    widths = [sum(len(w) for w in ln) for ln in lines]
    for pr in (0.0, 0.12, 0.25):
        write = make_scribe(man, p_pair=res["p_pair"], p_reuse=pr)
        doc = scribe_document(write, len(lines), widths, [len(p) for p in te_doc],
                              random.Random(11), gallows_p=res["gallows_p"])
        out[f"manual_{pr}"] = row(f"the manual, re-use {pr:.2f}", doc)

    print(f"\n  {'manuscript':26s} {t_in:6.3f}% {t_in/t_base:6.2f}x {t_out:6.3f}% "
          f"{t_out/t_base:6.2f}x")
    json.dump(out, open(os.path.join(HERE, "REPETITION_FIX.json"), "w",
                        encoding="utf-8"), indent=1)
    print("\nwrote REPETITION_FIX.json")


if __name__ == "__main__":
    main()
