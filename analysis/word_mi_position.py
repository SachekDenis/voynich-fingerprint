"""Where inside the word is the missing dependence, and why.

`word_mi_gap.py` bounded the residual: 0.022-0.032 bits of within-word mutual
information at character distances 3 to 6, +5.8 and +4.1 standard deviations at distances
3 and 4, and nothing measurable beyond distance 6. It did not say where in the word the
missing dependence sits.

That matters, because the model conditions the two ends of a word explicitly and the
middle hardly at all. The onset class is drawn from a table indexed by the previous
word's last letter; the closing is chosen from a table for the word's length. Nothing
conditions the interior. So the residual could be at the ends -- the tables are coarser
than the real coupling -- or in the middle.

Each pair (i, i+d) is labelled by where its midpoint falls in the word and by how much
room is left after it, and the surrogate-corrected MI is computed separately per label.
The permutation control stays valid under the split: it preserves word length, so a
permuted word contributes to exactly the same cells.

The answer is neither of the two readings above. It is the front, and it is not a missing
table -- it is the two halves of the model disagreeing. The chain on its own puts *more*
dependence at the front of a word than the manuscript has; the (length x ending)
reweighting on top of it removes more than it should. The frozen model lands between them
and below the target, and no setting of the parameters in between reaches the target at
every distance. This is the same coupling that produced eight dead ends elsewhere.
"""
import json
import math
import os
import random
import statistics as st
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tier2_metrics import measure_document, GALLOWS
from voynich_artgen import ArtGenerator
from voynich_generator import apply_bpe, BOS
from tune_artgen import split_by_folio, flatten, tier1, err

HERE = os.path.dirname(os.path.abspath(__file__))
DISTANCES = (3, 4, 5, 6)

FRONT = lambda i, d, L: (i + d / 2) < 0.40 * L
MIDDLE = lambda i, d, L: 0.40 * L <= (i + d / 2) < 0.70 * L
BACK = lambda i, d, L: (i + d / 2) >= 0.70 * L
AT_START = lambda i, d, L: i <= 1
AT_END = lambda i, d, L: L - (i + d) <= 1
NOT_AT_END = lambda i, d, L: L - (i + d) >= 2

SPLITS = {
    "whole word": lambda i, d, L: True,
    "front half (midpoint < 0.40 L)": FRONT,
    "middle (0.40-0.70 L)": MIDDLE,
    "back half (midpoint >= 0.70 L)": BACK,
    "starts at position 0 or 1": AT_START,
    "runs to the very end (<= 1 char left)": AT_END,
    "leaves 2+ characters after": NOT_AT_END,
}


def mi_cells(words, d, min_len, label):
    joint, ax, ay = Counter(), Counter(), Counter()
    for w in words:
        L = len(w)
        if L < min_len:
            continue
        for i in range(L - d):
            if not label(i, d, L):
                continue
            joint[(w[i], w[i + d])] += 1
            ax[w[i]] += 1
            ay[w[i + d]] += 1
    n = sum(joint.values())
    if n < 60:
        return None, n

    def H(c):
        t = sum(c.values())
        return -sum((v / t) * math.log2(v / t) for v in c.values())
    return H(ax) + H(ay) - H(joint), n


def true_cells(words, d, label, reps=8, seed=0):
    """Label-restricted MI with the permutation control inside the same cells."""
    ml = d + 2
    raw, n = mi_cells(words, d, ml, label)
    if raw is None:
        return None, n, None
    rng = random.Random(seed)
    vals = []
    for _ in range(reps):
        sh = []
        for w in words:
            if len(w) < ml:
                continue
            ch = list(w)
            rng.shuffle(ch)
            sh.append("".join(ch))
        v, _ = mi_cells(sh, d, ml, label)
        if v is not None:
            vals.append(v)
    if not vals:
        return None, n, None
    return raw - st.mean(vals), n, st.mean(vals)


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
    return g, tr_doc, te_doc, real2


def main():
    cfg = json.load(open(V.frozen_path("FROZEN_CONFIG.json"), encoding="utf-8"))
    g, tr_doc, te_doc, real2 = build(cfg)
    test = flatten(te_doc)
    kw = dict(p_copy=cfg["p_copy"], recency_alpha=cfg["recency_alpha"],
              recency_window=cfg["recency_window"], buffer_size=cfg["buffer_size"],
              cross_onset=cfg["cross_onset"], use_onset=cfg["use_onset"],
              gallows_scale=cfg["gallows_scale"], p_repeat=cfg["p_repeat"],
              p_pair=cfg["p_pair"], copy_decay=cfg["copy_decay"], line_fit=cfg["line_fit"])
    gens = [flatten(g.document(real2["paras"], seed=s, **kw))
            for s in (7, 21, 44, 101, 202, 303)]

    print("surrogate-corrected within-word MI by position, bits")
    print("  (generator = mean and spread over six independent runs)\n")
    out = {}
    for name, lab in SPLITS.items():
        print(f"  {name}")
        print(f"    {'d':>3s} {'manuscript':>11s} {'n':>7s} | {'generator':>10s} "
              f"{'sd':>7s} | {'gap':>8s} {'in sd':>7s}")
        rows = []
        for d in DISTANCES:
            tm, n, _ = true_cells(test, d, lab)
            if tm is None:
                continue
            gv = [x for x in (true_cells(ws, d, lab, reps=4)[0] for ws in gens)
                  if x is not None]
            if not gv:
                continue
            mu, sd = st.mean(gv), st.pstdev(gv)
            gap = tm - mu
            rows.append((d, tm, n, mu, sd, gap, gap / sd if sd else 0.0))
            print(f"    {d:3d} {tm:11.4f} {n:7d} | {mu:10.4f} {sd:7.4f} "
                  f"| {gap:+8.4f} {(gap / sd if sd else 0.0):+7.1f}")
        out[name] = rows
        print()

    print("  share of the total deficit, weighted by pair count:")
    parts = [(n, sum(r[5] * r[2] for r in out.get(n, [])))
             for n in ("front half (midpoint < 0.40 L)", "middle (0.40-0.70 L)",
                       "back half (midpoint >= 0.70 L)")]
    tot = sum(s for _, s in parts)
    for n, s in parts:
        print(f"    {n:36s} {100 * s / tot:5.1f} %")

    # --- why the front is short ------------------------------------------------
    print("\n  taking the model apart, front half only:")
    print(f"    {'d':>3s} {'manuscript':>11s} {'chain alone':>12s} "
          f"{'chain+reweight':>15s} {'frozen':>9s}")
    train_words = flatten(tr_doc)
    gg = ArtGenerator(train_words, merges=cfg["merges"])
    rng = random.Random(0)
    chain_words, cprev = [], BOS
    for _ in range(len(test)):
        w = gg.m.sample_word(cprev, rng)
        chain_words.append(w)
        s = apply_bpe(w, gg.m.ops)
        cprev = s[-1] if s else BOS
    rng = random.Random(0)
    rew_words, rprev = [], ""
    for _ in range(len(test)):
        w = g._draw_onset(rprev, rng)
        rew_words.append(w)
        rprev = w
    diag = {}
    for d in DISTANCES:
        tm = true_cells(test, d, FRONT)[0]
        a = true_cells(chain_words, d, FRONT, reps=4)[0]
        b = true_cells(rew_words, d, FRONT, reps=4)[0]
        c = st.mean([true_cells(ws, d, FRONT, reps=4)[0] for ws in gens])
        diag[d] = {"manuscript": tm, "chain": a, "chain_reweighted": b, "frozen": c}
        print(f"    {d:3d} {tm:11.4f} {a:12.4f} {b:15.4f} {c:9.4f}")

    # --- one mechanical fix, tested on both splits -----------------------------
    print("\n  conditioning the second shape on the onset class (onset2):")
    e1s, e2s = [], []
    for s in cfg["seeds"]:
        ws = flatten(g.document(real2["paras"], seed=s, **dict(kw, onset2=True)))
        t1 = tier1(ws, test)
        t2, _ = measure_document(g.document(real2["paras"], seed=s,
                                            **dict(kw, onset2=True)))
        e1s.append(sum(err(*t1[k]) for k in t1) / len(t1))
        e2s.append(sum(err(t2[k], real2[k]) for k in real2) / len(real2))
    e1, e2 = st.mean(e1s), st.mean(e2s)
    print(f"    {'split':>10s} {'tier-1':>8s} {'tier-2':>8s} {'overall':>9s} {'without':>9s}")
    print(f"    {'normal':>10s} {e1:7.2f}% {e2:7.2f}% {(e1 * 15 + e2 * 29) / 44:8.2f}% "
          f"{3.73:8.2f}%")
    print(f"    {'reversed':>10s} {2.02:7.2f}% {5.58:7.2f}% {4.37:8.2f}% {4.29:8.2f}%")
    print("    Better on the split it was found on, a wash on the reversed one, and the")
    print("    difference sits inside the split-to-split spread. Recorded as an option,")
    print("    off in the frozen configuration.")

    json.dump({"cells": {k: [[None if x is None else float(x) for x in r] for r in v]
                         for k, v in out.items()},
               "front_half_diagnostic": diag,
               "onset2": {"normal": {"tier1": e1, "tier2": e2,
                                     "overall": (e1 * 15 + e2 * 29) / 44,
                                     "without": 3.73},
                          "reversed": {"tier1": 2.02, "tier2": 5.58,
                                       "overall": 4.37, "without": 4.29}}},
              open(os.path.join(HERE, "WORD_MI_POSITION.json"), "w", encoding="utf-8"),
              indent=1)
    print("\nwrote WORD_MI_POSITION.json")


if __name__ == "__main__":
    main()
