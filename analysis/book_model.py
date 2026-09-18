"""The headline is a statement about the book in aggregate, not about its parts.

This is the measurement that closes the section question, and it turns out to sharpen the
caveat rather than remove it. Three designs, same 44 metrics, same held-out leaves:

  A  one pooled model, scored over the whole held-out half                3.7 %
  B  one pooled model, applied unchanged to each held-out section    10.6 - 26.2 %
  C  one parameter set per section, each on half its own leaves       5.7 - 14.2 %

A and B are the same model. The difference between 3.7 % and 10-26 % is not a fitting
problem: it is that pooling the sections produces statistics that no individual section
has. The model reproduces the mixture, and the mixture is what the parity split measures.

C halves the per-section error, which is what "the model needs per-section parameters"
means in numbers. Its limit is text: the pharmaceutical section has 1494 training words
under that design and lands at 14.2 %, while the recipes section with 4982 lands at 6.1 %.

A fourth design was tried and is worse than either: a shared text model with per-section
page geometry alone, at 11.9 %. Geometry and the length conditioning are coupled -- the
length target is measured on non-line-final words, so changing the column width without
re-deriving the lengths moves the realised length distribution instead of improving it.
That is the same coupling that runs through the rest of this repository.
"""
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from tier2_metrics import measure_document, GALLOWS
from voynich_artgen import ArtGenerator
from tune_artgen import split_by_folio, flatten, tier1, err
from section_transfer import build, finish, generate_matched

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SECTIONS = ["herbal", "biological", "pharmaceutical", "recipes", "cosmological"]
MIN_HALF = 600


def section_split():
    """Per-section documents, split by leaf parity inside each section."""
    out = defaultdict(dict)
    for folio, locus, ltype, raw, meta in V.parse_ivtff(
            os.path.join(ROOT, "data", "IT2a-n.txt")):
        code = re.sub(r"\d+$", "", ltype)
        if code.lstrip("@+*&=")[:1] != "P":
            continue
        sec = V.section_of(folio)
        starts = raw.lstrip().startswith("<%>")
        ends = raw.rstrip().endswith("<$>")
        t = V.strip_markup(raw).replace("<%>", "").replace("<$>", "")
        ws = [x.strip("-") for x in re.split(r"[.,\s]+", t)]
        ws = [x for x in ws if x and not re.search(r"[?!]", x)
              and not any(c in x for c in "[]{}()")]
        st = out[sec]
        if starts and st.get("cur"):
            st["paras"].append((st["cur"], st["folio"]))
            st["cur"] = []
        if not ws:
            continue
        if "cur" not in st:
            st["cur"], st["folio"], st["paras"] = [], folio, []
        st["cur"].append(ws)
        if ends:
            st["paras"].append((st["cur"], folio))
            st["cur"] = []
    docs = {}
    for sec, st in out.items():
        if st.get("cur"):
            st["paras"].append((st["cur"], st["folio"]))
        ps = [p for p, _ in st["paras"]]
        fs = [f for _, f in st["paras"]]
        even = [p for p, f in zip(ps, fs) if int(re.match(r"f?(\d+)", f).group(1)) % 2 == 0]
        odd = [p for p, f in zip(ps, fs) if int(re.match(r"f?(\d+)", f).group(1)) % 2 == 1]
        docs[sec] = (even, odd)
    return docs


def score(g, cfg, te, seed=7):
    ew = flatten(te)
    real2, _ = measure_document(te)
    doc = generate_matched(g, cfg, seed, len(ew))
    gw = flatten(doc)
    t1 = tier1(gw, ew)
    t2, _ = measure_document(doc)
    e1 = sum(err(*t1[k]) for k in t1) / len(t1)
    e2 = sum(err(t2[k], real2[k]) for k in real2) / len(real2)
    return e1, e2, (e1 * 15 + e2 * 29) / 44, len(ew)


def main():
    cfg = json.load(open(os.path.join(HERE, "FROZEN_CONFIG.json"), encoding="utf-8"))
    tr_doc, te_doc = split_by_folio()
    docs = section_split()
    out = {}

    print("A. one pooled model, the whole held-out half at once")
    pooled = build(flatten(tr_doc))
    finish(pooled, tr_doc, te_doc, cfg)
    e1, e2, ov, n = score(pooled, cfg, te_doc)
    print(f"   tier-1 {e1:.1f} %   tier-2 {e2:.1f} %   overall {ov:.2f} %   ({n} words)\n")
    out["A_pooled_whole_book"] = {"tier1_pct": e1, "tier2_pct": e2, "overall_pct": ov,
                                  "words": n}

    print("B. the same pooled model, applied unchanged to each held-out section")
    print(f"   {'section':15s} {'held out':>9s} {'tier-1':>8s} {'tier-2':>8s} {'overall':>9s}")
    print("   " + "-" * 54)
    rows_b, wb = [], 0
    for sec in SECTIONS:
        if sec not in docs:
            continue
        _, te = docs[sec]
        if len(flatten(te)) < MIN_HALF:
            continue
        a, b, o, n = score(pooled, cfg, te)
        rows_b.append((sec, a, b, o, n))
        wb += n
        print(f"   {sec:15s} {n:9d} {a:7.1f}% {b:7.1f}% {o:8.2f}%")
    print("   " + "-" * 54)
    pb = sum(o * n for _, _, _, o, n in rows_b) / wb
    print(f"   {'pooled by text':15s} {'':>9s} {'':>8s} {'':>8s} {pb:8.2f}%\n")
    out["B_pooled_model_per_section"] = {
        "per_section": {s: {"tier1_pct": a, "tier2_pct": b, "overall_pct": o,
                            "words": n} for s, a, b, o, n in rows_b},
        "pooled_pct": pb}

    print("C. one parameter set per section, each on half its own leaves")
    print(f"   {'section':15s} {'train w':>8s} {'held out':>9s} {'tier-1':>8s} "
          f"{'tier-2':>8s} {'overall':>9s}")
    print("   " + "-" * 66)
    rows_c, wc = [], 0
    for sec in SECTIONS:
        if sec not in docs:
            continue
        tr, te = docs[sec]
        tw, ew = flatten(tr), flatten(te)
        if len(ew) < MIN_HALF or len(tw) < MIN_HALF:
            print(f"   {sec:15s} {len(tw):8d} {len(ew):9d}   -- too little text")
            continue
        g = build(list(tw))
        finish(g, tr, te, cfg)
        a, b, o, n = score(g, cfg, te)
        rows_c.append((sec, a, b, o, n, len(tw)))
        wc += n
        print(f"   {sec:15s} {len(tw):8d} {n:9d} {a:7.1f}% {b:7.1f}% {o:8.2f}%")
    print("   " + "-" * 66)
    pc = sum(o * n for _, _, _, o, n, _ in rows_c) / wc
    print(f"   {'pooled by text':15s} {'':>8s} {'':>9s} {'':>8s} {'':>8s} {pc:8.2f}%\n")
    out["C_per_section_parameters"] = {
        "per_section": {s: {"tier1_pct": a, "tier2_pct": b, "overall_pct": o,
                            "train_words": t, "held_out_words": n}
                        for s, a, b, o, n, t in rows_c},
        "pooled_pct": pc}

    out["note"] = ("A and B use the same model; the gap between them is the section "
                   "difference, not a fitting failure.")
    json.dump(out, open(os.path.join(HERE, "BOOK_MODEL.json"), "w", encoding="utf-8"),
              indent=1)
    print("wrote BOOK_MODEL.json")


if __name__ == "__main__":
    main()
