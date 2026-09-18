"""Is the generator executable by a human hand, not a processor?

Three questions, each measured:
  1. EFFORT      -- how many operations per accepted word?
  2. WORKING SET -- how much already-written text must be visible?
  3. SUBSTITUTION-- which components can be dropped and replaced by a human habit?
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from tier2_metrics import measure_document, GALLOWS
from voynich_artgen import ArtGenerator
from tune_artgen import split_by_folio, flatten, tier1, err
from voynich_generator import apply_bpe

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = dict(p_copy=0.06, recency_alpha=0.8, recency_window=120, buffer_size=700,
            cross_onset=True, use_onset=False, gallows_scale=1.0)


def build():
    tr, te = split_by_folio()
    train_words, test_words = flatten(tr), flatten(te)
    g = ArtGenerator(train_words)
    g.calibrate()
    g.calibrate_onset(train_words)
    g.calibrate_cross_onset(train_words)
    g.calibrate_common(train_words)
    g.calibrate_layout(te, gallows_p=0.0)
    real2, _ = measure_document(te)
    probe = [ln for p in g.document(n_paragraphs=40, seed=3) for ln in p]
    nat = sum(1 for ln in probe if ln and any(ln[0].startswith(x) for x in GALLOWS)) / len(probe)
    g.line_gallows_p = max(0.0, (real2["para/line-initial gallows %"] / 100 - nat) / (1 - nat))
    return g, test_words, real2


# --------------------------------------------------------------------------
# 1. Effort accounting
# --------------------------------------------------------------------------

def effort():
    g, test_words, real2 = build()
    for p_copy in (0.06, 0.30):
        g.trials = 0
        doc = g.document(n_paragraphs=6, seed=7,
                         p_copy=p_copy, recency_alpha=BASE["recency_alpha"],
                         buffer_size=BASE["buffer_size"], cross_onset=True)
        words = flatten(doc)
        fresh = sum(1 for _ in []) if False else None
        print(f"== 1. EFFORT (p_copy={p_copy}) ==")
        print(f"  words produced               : {len(words)}")
        print(f"  candidate words evaluated    : {g.trials}")
        print(f"  candidates per kept word     : {g.trials/max(1,len(words)):.2f}")
        lens = [len(apply_bpe(w, g.m.ops)) for w in words]
        print(f"  syllables per word (mean)    : {sum(lens)/len(lens):.2f}")
        print(f"  words from copy+edit         : {100*p_copy:.0f}%")
        print()


# --------------------------------------------------------------------------
# 2. Working set: how much prior text must be visible?
# --------------------------------------------------------------------------

def buffer_sweep():
    g, test_words, real2 = build()
    print("\n== 2. WORKING SET (how far back the copy source can reach) ==")
    print(f"  {'buffer':>8s} {'~lines':>7s} {'tier-1 %':>9s} {'tier-2 %':>9s} {'top-10 %':>9s} {'reps %':>7s}")
    for bs in (25, 50, 100, 200, 400, 700, 1500):
        doc = g.document(n_paragraphs=real2["paras"], seed=7,
                         p_copy=BASE["p_copy"], recency_alpha=BASE["recency_alpha"],
                         buffer_size=bs, cross_onset=True)
        gw = flatten(doc)
        t1 = tier1(gw, test_words)
        t2, _ = measure_document(doc)[0:2]
        e1 = sum(err(*t1[k]) for k in t1) / len(t1)
        e2 = sum(err(t2[k], real2[k]) for k in real2) / len(real2)
        top10 = t1["top-10 word share %"][0]
        reps = t2["repeated word-pair %"]
        print(f"  {bs:8d} {bs/8.1:7.0f} {e1:9.1f} {e2:9.1f} {top10:9.2f} {reps:7.1f}")
    print(f"  held-out target: top-10 {t1['top-10 word share %'][1]:.2f}%  "
          f"repeated pairs {real2['repeated word-pair %']:.1f}%")


# --------------------------------------------------------------------------
# 3. Ablation: what does each component buy?
# --------------------------------------------------------------------------

def ablation():
    g, test_words, real2 = build()
    print("\n== 3. ABLATION (component removed -> what breaks) ==")
    variants = {
        "full model": dict(),
        "no cross-onset (onset by unit chain)": dict(cross_onset=False, use_onset=False),
        "no length/final reweighting": dict(no_reweight=True),
        "no self-citation": dict(p_copy=0.0),
        "no gallows at line start": dict(no_gallows=True),
        "no line fill (uniform line length)": dict(no_lines=True),
        "no recency penalty": dict(recency_alpha=0.0),
    }
    base_ref = None
    for name, mod in variants.items():
        kw = dict(BASE)
        if mod.get("no_gallows"):
            g.line_gallows_p = 0.0
        else:
            g.line_gallows_p = 0.115
        if mod.get("no_lines"):
            g.line_char_choices = [int(sum(g.line_char_choices) / len(g.line_char_choices))] * 50
        kw.update({k: v for k, v in mod.items() if k in BASE})
        if mod.get("no_reweight"):
            saved = (g.tgt_len, g.tgt_fin)
            # ratio target/proposal becomes exactly 1 -> the first candidate is always taken
            g.tgt_len, g.tgt_fin = g.prop_len, g.prop_fin
        doc = g.document(n_paragraphs=real2["paras"], seed=7,
                         p_copy=kw["p_copy"], recency_alpha=kw["recency_alpha"],
                         buffer_size=kw["buffer_size"],
                         cross_onset=kw["cross_onset"], use_onset=kw["use_onset"])
        if mod.get("no_reweight"):
            g.tgt_len, g.tgt_fin = saved
        gw = flatten(doc)
        t1 = tier1(gw, test_words)
        t2, _ = measure_document(doc)[0:2]
        e1 = sum(err(*t1[k]) for k in t1) / len(t1)
        e2 = sum(err(t2[k], real2[k]) for k in real2) / len(real2)
        if mod.get("no_lines"):
            g.calibrate_layout(split_by_folio()[1], gallows_p=g.line_gallows_p)
        print(f"  {name:38s} tier-1 {e1:6.1f}%  tier-2 {e2:6.1f}%  "
              f"h2 {t1['h2 (char)'][0]:.3f}  MI {t1['cross-word MI'][0]:.3f}  "
              f"final-y {t1['final-y %'][0]:.1f}")


if __name__ == "__main__":
    effort()
    buffer_sweep()
    ablation()
