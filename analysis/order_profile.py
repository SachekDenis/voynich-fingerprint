"""How much does context buy?  Cross-entropy by model order, on held-out text.

Every entropy figure in this repository so far is a bigram figure. But the question that
separates a language from a table is not the bigram entropy, it is the slope: how much
does a third, a fourth, a fifth character of context buy?

Measured with Witten-Bell smoothing on a held-out half of each corpus, so the numbers are
comparable across alphabets of different size and no estimator bias correction is needed.

A language keeps buying: each extra character of context lowers the cross-entropy
substantially, because grammar and morphology constrain what comes next. A table of
syllables saturates as soon as the syllable is identified. The slope is the test.
"""
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def stream(words):
    return [c for w in words for c in w]


def fit(train, order):
    """Witten-Bell counts: for every context, the count table and its type count."""
    ctx = defaultdict(Counter)
    for i in range(len(train) - order + 1):
        c = tuple(train[i:i + order - 1])
        ctx[c][train[i + order - 1]] += 1
    return ctx


def cross_entropy(test, ctx, unigram, order, alpha=1.0):
    """Average -log2 p(c | context) on held-out data."""
    tot = 0.0
    n = 0
    # Witten-Bell: p = (count + T * p_lower) / (N + T), T = number of distinct continuations
    lower_ctx = {1: None}
    for i in range(len(test) - order + 1):
        hist = tuple(test[i:i + order - 1])
        c = test[i + order - 1]
        if order == 1:
            p = (unigram[c] + alpha) / (sum(unigram.values()) + alpha * len(unigram))
        else:
            tab = ctx.get(hist)
            if not tab:
                p = (unigram[c] + alpha) / (sum(unigram.values()) + alpha * len(unigram))
            else:
                N = sum(tab.values())
                T = len(tab)
                # back off to the shorter context, approximated by the unigram
                p_back = (unigram[c] + alpha) / (sum(unigram.values()) + alpha * len(unigram))
                p = (tab[c] + T * p_back) / (N + T)
        tot += -math.log2(max(p, 1e-12))
        n += 1
    return tot / n


def profile(name, words, max_order=5):
    s = stream(words)
    half = len(s) // 2
    train, test = s[:half], s[half:half + 200000]
    uni = Counter(train)
    out = []
    for order in range(1, max_order + 1):
        ctx = fit(train, order) if order > 1 else {}
        out.append(cross_entropy(test, ctx, uni, order))
    print(f"  {name:14s} " + " ".join(f"{v:6.2f}" for v in out) +
          "   | gain 1->2 {:+.2f}  2->3 {:+.2f}  3->4 {:+.2f} 4->5 {:+.2f}".format(
              out[0] - out[1], out[1] - out[2], out[2] - out[3], out[3] - out[4]))
    return out


if __name__ == "__main__":
    import voynich_lib as V
    from refstats import tok_from_conllu
    import json
    from tier2_metrics import measure_document, GALLOWS
    from voynich_artgen import ArtGenerator
    from tune_artgen import split_by_folio, flatten

    print("cross-entropy in bits per character, Witten-Bell, trained on half / tested on half")
    print(f"  {'corpus':14s} " + " ".join(f"{'h'+str(k):>6s}" for k in range(1, 6)))
    sets = [("manuscript", [w[4] for w in V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt"))])]
    for n in ("latin", "italian", "ocs", "german"):
        p = os.path.join(ROOT, "data", "ref", f"{n}.conllu")
        if os.path.exists(p):
            sets.append((n, tok_from_conllu(p)))
    for name, ws in sets:
        profile(name, ws)

    cfg = json.load(open(V.frozen_path("FROZEN_CONFIG.json"), encoding="utf-8"))
    tr, te = split_by_folio()
    train, test = flatten(tr), flatten(te)
    real2, _ = measure_document(te)
    g = ArtGenerator(train, merges=cfg["merges"])
    g.calibrate(); g.calibrate_onset(train); g.calibrate_cross_onset(train)
    g.calibrate_common(train); g.calibrate_pairs(train); g.calibrate_lengths(tr)
    g.fit_penalty = cfg["fit_penalty"]; g.calibrate_proposal()
    g.calibrate_layout(tr, gallows_p=0.0); g.gallows_scale = cfg["gallows_scale"]
    pr = [ln for p in g.document(40, seed=3) for ln in p]
    nat = sum(1 for ln in pr if ln and any(ln[0].startswith(x) for x in GALLOWS)) / len(pr)
    g.line_gallows_p = max(0.0, (real2["para/line-initial gallows %"] / 100 - nat) / (1 - nat))
    doc = g.document(real2["paras"], seed=7, p_copy=cfg["p_copy"],
                     recency_alpha=cfg["recency_alpha"], buffer_size=cfg["buffer_size"],
                     cross_onset=cfg["cross_onset"], p_repeat=cfg["p_repeat"],
                     p_pair=cfg["p_pair"], line_fit=cfg["line_fit"],
                     gallows_scale=cfg["gallows_scale"])
    profile("generator", flatten(doc))
