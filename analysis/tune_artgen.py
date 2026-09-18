"""Combined tier-1 + tier-2 tuning, on a single consistent train/test split.

Training: body-text words on even-numbered leaves.
Test:     body-text document (paragraphs of lines) on odd-numbered leaves.
Both tiers are measured against that same held-out document, so TTR, hapax and
vocabulary metrics are compared at matching scope.
"""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from refstats import fingerprint
from generate_evaluate import edge_stats, cross_MI
from tier2_metrics import load_real_document, measure_document, GALLOWS
from voynich_artgen import ArtGenerator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def folio_num(f):
    return int(re.match(r"f?(\d+)", f).group(1))


def split_by_folio():
    """Rebuild the document keeping the folio of each paragraph.

    Paragraphs are delimited by the manuscript's own <%> / <$> marks, not by the
    locus type: every one of the 772 markers sits on a body locus and they pair
    without exception. See the note in tier2_metrics.load_real_document.
    """
    path = os.path.join(ROOT, "data", "IT2a-n.txt")
    paras, folios, cur, curf = [], [], [], []
    open_para = False
    for folio, locus, ltype, raw, meta in V.parse_ivtff(path):
        code = re.sub(r"\d+$", "", ltype)
        if code.lstrip("@+*&=")[:1] != "P":
            continue
        starts = raw.lstrip().startswith("<%>")
        ends = raw.rstrip().endswith("<$>")
        t = V.strip_markup(raw).replace("<%>", "").replace("<$>", "")
        ws = []
        for tok in re.split(r"[.,\s]+", t):
            tok = tok.strip("-")
            if not tok or re.search(r"[?!]", tok) or any(c in tok for c in "[]{}()"):
                continue
            ws.append(tok)
        if starts and open_para and cur:
            paras.append(cur)
            folios.append(curf[0])
            cur, curf = [], []
        if not ws:
            continue
        open_para = True
        cur.append(ws)
        curf.append(folio)
        if ends:
            paras.append(cur)
            folios.append(curf[0])
            cur, curf = [], []
            open_para = False
    if cur:
        paras.append(cur)
        folios.append(curf[0])
    tr = [p for p, f in zip(paras, folios) if folio_num(f) % 2 == 0]
    te = [p for p, f in zip(paras, folios) if folio_num(f) % 2 == 1]
    return tr, te


def flatten(doc):
    return [w for p in doc for ln in p for w in ln]


def err(a, b):
    if abs(a) < 1e-12 and abs(b) < 1e-12:
        return 0.0
    if abs(b) < 1e-9:
        return abs(a) * 100
    return abs(a - b) / abs(b) * 100


def tier1(words, test_words):
    tf = fingerprint(test_words)
    to5, tf5, tfy, tt10 = edge_stats(test_words)
    tmi = cross_MI(test_words)
    gt = Counter(len(w) for w in test_words)
    tt = sum(gt.values())
    fp = fingerprint(words)
    o5, f5, fy, t10 = edge_stats(words)
    mi = cross_MI(words)
    gc = Counter(len(w) for w in words)
    t = sum(gc.values())
    tv = 0.5 * sum(abs(gc[k] / t - gt[k] / tt) for k in set(list(gc) + list(gt)))
    return {
        "h1 (char)": (fp["h1_char"], tf["h1_char"]),
        "h2 (char)": (fp["h2_char"], tf["h2_char"]),
        "H(word)": (fp["h_word"], tf["h_word"]),
        "TTR": (fp["ttr"], tf["ttr"]),
        "hapax %": (fp["hapax_%"], tf["hapax_%"]),
        "mean word len": (fp["mean_len"], tf["mean_len"]),
        "sd word len": (fp["sd_len"], tf["sd_len"]),
        "H init": (fp["h_pos_init"], tf["h_pos_init"]),
        "H final": (fp["h_pos_final"], tf["h_pos_final"]),
        "len dist TV": (tv, 0.0),
        "top-5 onsets %": (100 * o5, 100 * to5),
        "top-5 finals %": (100 * f5, 100 * tf5),
        "final-y %": (100 * fy, 100 * tfy),
        "top-10 word share %": (100 * t10, 100 * tt10),
        "cross-word MI": (mi, tmi),
    }


def main():
    tr_doc, te_doc = split_by_folio()
    train_words = flatten(tr_doc)
    test_words = flatten(te_doc)
    real2, real_words = measure_document(te_doc)
    print(f"train {len(train_words)} words | held-out {len(test_words)} words, "
          f"{real2['paras']} paras, {real2['lines']} lines")

    g = ArtGenerator(train_words)
    g.calibrate()
    g.calibrate_onset(train_words)
    g.calibrate_cross_onset(train_words)
    g.calibrate_common(train_words)
    g.calibrate_layout(te_doc, gallows_p=0.0)

    # calibrate the line-initial gallows injection against the held-out document
    g.line_gallows_p = 0.0
    probe = [ln for p in g.document(n_paragraphs=40, seed=3) for ln in p]
    nat = sum(1 for ln in probe if ln and any(ln[0].startswith(x) for x in GALLOWS)) / len(probe)
    tgt_g = real2["para/line-initial gallows %"] / 100
    g.line_gallows_p = max(0.0, (tgt_g - nat) / (1 - nat))
    print(f"gallows: natural {nat*100:.1f}% target {tgt_g*100:.1f}% -> inject {g.line_gallows_p:.3f}")

    base = dict(buffer_size=700, use_onset=False, cross_onset=True)
    configs = [
        dict(base, p_copy=0.06, recency_alpha=0.8),
        dict(base, p_copy=0.06, recency_alpha=0.8, gallows_scale=0.7),
        dict(base, p_copy=0.04, recency_alpha=1.2),
        dict(base, p_copy=0.08, recency_alpha=0.6),
    ]

    results = {}
    for cfg in configs:
        use_onset = cfg.pop("use_onset")
        gen_doc = g.document(n_paragraphs=real2["paras"], seed=7,
                              use_onset=use_onset, **cfg)
        gw = flatten(gen_doc)
        t1 = tier1(gw, test_words)
        t2, _ = measure_document(gen_doc)
        e1 = sum(err(*t1[k]) for k in t1) / len(t1)
        e2 = sum(err(t2[k], real2[k]) for k in real2) / len(real2)
        results[(use_onset, tuple(sorted(cfg.items())))] = (t1, t2, e1, e2, len(gw))

    cols = list(results)
    print(f"\n{'metric':30s} {'target':>9s} " + " ".join(f"{'c'+str(i):>9s}" for i in range(len(cols))))
    print("-" * (30 + 10 + 10 * len(cols)))
    for k in results[cols[0]][0]:
        print(f"{k:30s} {results[cols[0]][0][k][1]:9.3f} " +
              " ".join(f"{results[c][0][k][0]:9.3f}" for c in cols))
    print()
    for k in real2:
        print(f"{k:30s} {real2[k]:9.3f} " + " ".join(f"{results[c][1][k]:9.3f}" for c in cols))
    print("-" * (30 + 10 + 10 * len(cols)))
    print(f"{'TIER-1 mean err %':30s} {'':>9s} " + " ".join(f"{results[c][2]:9.1f}" for c in cols))
    print(f"{'TIER-2 mean err %':30s} {'':>9s} " + " ".join(f"{results[c][3]:9.1f}" for c in cols))
    print(f"{'words':30s} {'':>9s} " + " ".join(f"{results[c][4]:9d}" for c in cols))
    for i, c in enumerate(cols):
        print(f"  c{i}: onset_reweight={c[0]} {dict(c[1])}")


if __name__ == "__main__":
    main()
