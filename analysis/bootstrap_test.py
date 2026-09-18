"""Bootstrap test: can the procedure sustain itself without the real manuscript?

The frozen model is fitted to the finished text, so it is a *description* of the
manuscript, not necessarily a procedure a person could have run. A person starting
from nothing would have to learn the statistics from their own output.

So: seed with a small sample of real text, then iterate --
    fit -> generate -> refit on own output -> generate -> ...
If the statistics stay in the target region the process is self-sustaining
(a human could have bootstrapped it). If they drift or collapse, the model is
parasitic on the finished text.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from tier2_metrics import measure_document, GALLOWS
from voynich_artgen import ArtGenerator
from tune_artgen import split_by_folio, flatten, tier1

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = dict(p_copy=0.06, recency_alpha=0.8, buffer_size=700, cross_onset=True)


def fit(corpus_words, layout_doc):
    g = ArtGenerator(corpus_words)
    g.calibrate()
    g.calibrate_onset(corpus_words)
    g.calibrate_cross_onset(corpus_words)
    g.calibrate_common(corpus_words)
    g.calibrate_layout(layout_doc, gallows_p=0.0)
    real2, _ = measure_document(layout_doc)
    probe = [ln for p in g.document(n_paragraphs=30, seed=3) for ln in p]
    nat = sum(1 for ln in probe if ln and any(ln[0].startswith(x) for x in GALLOWS)) / len(probe)
    g.line_gallows_p = max(0.0, (real2["para/line-initial gallows %"] / 100 - nat) / (1 - nat))
    return g


def run_series(p_invent, rounds=8, seed=800, gen=6000, label=""):
    tr, te = split_by_folio()
    train_words, test_words = flatten(tr), flatten(te)
    real2, _ = measure_document(te)
    corpus = train_words[:seed]
    rows = []
    for r in range(rounds + 1):
        g = fit(corpus, te)
        doc = g.document(n_paragraphs=real2["paras"] // 2, seed=100 + r,
                         p_invent=p_invent, **BASE)
        gw = flatten(doc)
        t1 = tier1(gw, test_words)
        rows.append((r, t1["h2 (char)"][0], t1["TTR"][0], t1["hapax %"][0],
                     t1["top-10 word share %"][0], t1["cross-word MI"][0],
                     t1["h2 (char)"][1], t1["TTR"][1], t1["hapax %"][1],
                     t1["top-10 word share %"][1], t1["cross-word MI"][1]))
        if r < rounds:
            corpus = gw[:gen]
    return rows, label


def main():
    tr, te = split_by_folio()
    train_words = flatten(tr)
    test_words = flatten(te)
    real2, _ = measure_document(te)
    hdr = f"{'p_invent':>9s} {'round':>6s} {'h2':>7s} {'TTR':>7s} {'hapax%':>8s} {'top10%':>8s} {'MI':>7s}"
    print("self-training with a free-invention component\n")
    print(hdr)
    ref = None
    for p_inv in (0.0, 0.05, 0.15, 0.30):
        rows, _ = run_series(p_inv, rounds=8)
        if ref is None:
            ref = rows[0]
            print(f"{'TARGET':>9s} {'-':>6s} {ref[6]:7.3f} {ref[7]:7.3f} {ref[8]:8.2f} "
                  f"{ref[9]:8.2f} {ref[10]:7.3f}")
        for (r, h2, ttr, hap, t10, mi, *_t) in rows:
            if r in (0, 4, 8):
                print(f"{p_inv:9.2f} {r:6d} {h2:7.3f} {ttr:7.3f} {hap:8.2f} {t10:8.2f} {mi:7.3f}")
        print()
    return
    _unused()

    tr, te = split_by_folio()
    train_words = flatten(tr)
    test_words = flatten(te)
    real2, _ = measure_document(te)

    SEED = 800          # words of real text the "scribe" starts from
    GEN = 6000          # words produced per round
    ROUNDS = 10

    corpus = train_words[:SEED]
    print(f"seed corpus: {len(corpus)} real words, then {ROUNDS} rounds of self-training "
          f"({GEN} generated words each)\n")
    keys = ["h2 (char)", "TTR", "hapax %", "mean word len", "sd word len",
            "top-5 finals %", "final-y %", "top-10 word share %", "cross-word MI"]
    print(f"{'round':>6s} {'corpus':>8s} " + " ".join(f"{k.split(' (')[0][:8]:>9s}" for k in keys))
    targets = [tier1([], test_words)[k][1] if False else None for k in keys]

    # target row
    t_ref = None
    for r in range(ROUNDS + 1):
        g = fit(corpus, te)
        doc = g.document(n_paragraphs=real2["paras"] // 2, seed=100 + r, **BASE)
        gw = flatten(doc)
        t1 = tier1(gw, test_words)
        if t_ref is None:
            t_ref = [t1[k][1] for k in keys]
            print(f"{'TARGET':>6s} {'-':>8s} " + " ".join(f"{v:9.3f}" for v in t_ref))
        vals = [t1[k][0] for k in keys]
        print(f"{r:6d} {len(corpus):8d} " + " ".join(f"{v:9.3f}" for v in vals))
        if r < ROUNDS:
            corpus = gw[:GEN]        # refit entirely on the model's own output


if __name__ == "__main__":
    main()
