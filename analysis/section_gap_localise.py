"""Which table makes the sections different?

`section_transfer.py` shows that a generator fitted to one section fails on another, and
that page geometry accounts for about a third of the tier-2 gap and a fifth of the tier-1
gap. It does not say where the rest lives. `book_model.py` shows per-section parameters
halve the error, and that the limit is text.

This localises it the way everything else in this repository was localised: replace one
component of the source model with the target's, one at a time, and see how much of the
transfer error each replacement removes. Whatever removes most is what the sections
actually differ in.

Components, in the order they enter the generator:

  layout        line width and paragraph shape, taken from the target document
  lengths       the (length x final shape) joint, which drives the reweighting
  onset         the onset-class marginal and the cross-word table
  pairs         the memory of which word follows which
  language      the whole model refitted on the target: BPE inventory, chain, everything

The last one is the ceiling: replacing everything is the same as training on the target,
which is why it is here only as a reference.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tier2_metrics import measure_document, GALLOWS
from voynich_artgen import ArtGenerator
from tune_artgen import tier1, err
from section_transfer import section_docs, build, finish, generate_matched

HERE = os.path.dirname(os.path.abspath(__file__))
PAIRS = [("herbal", "recipes"), ("recipes", "herbal"), ("herbal", "biological"),
         ("biological", "herbal"), ("pharmaceutical", "recipes")]


def refit_into(g, target_words, meth):
    """Call one calibrate_* on the model, using the target's text."""
    if meth == "lengths":
        g.calibrate_lengths(target_words["doc"])
    elif meth == "onset":
        g.calibrate_onset(target_words["words"])
        g.calibrate_cross_onset(target_words["words"])
    elif meth == "pairs":
        g.calibrate_pairs(target_words["words"])
        g.calibrate_common(target_words["words"])
    elif meth == "language":
        m = ArtGenerator(target_words["words"], merges=g.m.merges if hasattr(g.m, "merges") else 140)
        m.calibrate()
        g.__dict__.update(m.__dict__)
    return g


def run(src, dst, cfg, words, paras, sw=None):
    g = build(list(words[src]))
    real2 = finish(g, paras[src], paras[dst], cfg)
    if sw == "layout":
        g.calibrate_layout(paras[dst], gallows_p=g.line_gallows_p)
    elif sw in ("lengths", "onset", "pairs"):
        refit_into(g, {"words": list(words[dst]), "doc": paras[dst]}, sw)
        if sw == "lengths":
            g.calibrate_proposal()
    doc = generate_matched(g, cfg, 7, len(words[dst]))
    gw = [w for p in doc for ln in p for w in ln]
    t1 = tier1(gw, words[dst])
    t2, _ = measure_document(doc)
    e1 = sum(err(*t1[k]) for k in t1) / len(t1)
    e2 = sum(err(t2[k], real2[k]) for k in real2) / len(real2)
    return e1, e2, (e1 * 15 + e2 * 29) / 44


def main():
    cfg = json.load(open(os.path.join(HERE, "FROZEN_CONFIG.json"), encoding="utf-8"))
    words, paras = section_docs()
    print("transfer error with one component taken from the target section\n")
    print(f"  {'train -> test':24s} {'swapped':>10s} {'tier-1':>8s} {'tier-2':>8s} "
          f"{'overall':>9s} {'removed':>9s}")
    print("  " + "-" * 74)
    out = {}
    for a, b in PAIRS:
        if a not in words or b not in words or len(words[a]) < 3000 or len(words[b]) < 800:
            continue
        base = run(a, b, cfg, words, paras)
        ov0 = base[2]
        print(f"  {a + ' -> ' + b:24s} {'nothing':>10s} {base[0]:7.1f}% {base[1]:7.1f}% "
              f"{ov0:8.2f}% {'':>9s}")
        rec = {}
        for sw in ("layout", "lengths", "onset", "pairs"):
            e1, e2, ov = run(a, b, cfg, words, paras, sw)
            removed = (ov0 - ov) / ov0 * 100 if ov0 else 0.0
            rec[sw] = {"tier1": e1, "tier2": e2, "overall": ov, "removed_pct": removed}
            print(f"  {'':24s} {sw:>10s} {e1:7.1f}% {e2:7.1f}% {ov:8.2f}% "
                  f"{removed:8.0f}%")
        print()
        out[f"{a}->{b}"] = {"baseline": {"tier1": base[0], "tier2": base[1],
                                         "overall": ov0}, "swaps": rec}

    print("  how much of the transfer error each component removes, by pair:")
    print(f"  {'pair':24s} " + " ".join(f"{s:>9s}" for s in
                                       ("layout", "lengths", "onset", "pairs")))
    print("  " + "-" * 66)
    means = {s: [] for s in ("layout", "lengths", "onset", "pairs")}
    for k, v in out.items():
        row = []
        for s in ("layout", "lengths", "onset", "pairs"):
            r = v["swaps"][s]["removed_pct"]
            means[s].append(r)
            row.append(f"{r:8.0f}%")
        print(f"  {k:24s} " + " ".join(row))
    print("  " + "-" * 66)
    print(f"  {'mean':24s} " + " ".join(f"{sum(means[s])/len(means[s]):8.0f}%" for s in means))
    print("\n  An earlier run of this comparison had the tabulation wrong and is replaced;")
    print("  the numbers here are internally consistent with `section_transfer.py`.")

    json.dump(out, open(os.path.join(HERE, "SECTION_GAP.json"), "w", encoding="utf-8"),
              indent=1)
    print("  wrote SECTION_GAP.json")


if __name__ == "__main__":
    main()
