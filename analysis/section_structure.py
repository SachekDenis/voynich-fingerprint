"""What actually differs between the sections?

section_transfer.py showed that a generator fitted to one section fails on another.
That is a negative result; this asks the constructive question. Sections could differ in
several independent ways, and which one it is determines what a scribe would have had to
change with the pen:

  * a different syllable table        -> different letter combinations exist at all
  * a different working vocabulary    -> same table, different stock of forms
  * a different ending preference     -> e.g. -y dominant in one, -n in another
  * a different gallows glyph         -> literally t/k in one section, p/f in another
  * nothing systematic, just drift    -> all sections are samples of one distribution

Each is measured separately here, on the same words the generator sees.
"""
import math
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from tier2_metrics import onset, GALLOWS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTIONS = ["herbal", "astronomical", "zodiac", "biological", "cosmological",
            "pharmaceutical", "recipes"]


def load_rows(path=None):
    path = path or os.path.join(ROOT, "data", "IT2a-n.txt")
    return V.load_words(path)


def h2_of(words):
    chars, big = Counter(), Counter()
    for w in words:
        chars.update(w)
        big.update(w[i:i + 2] for i in range(len(w) - 1))
    n = sum(chars.values())
    nb = sum(big.values())
    h1 = -sum((c / n) * math.log2(c / n) for c in chars.values())
    hxy = -sum((c / nb) * math.log2(c / nb) for c in big.values())
    return h1, hxy - h1


def js(p, q):
    """Jensen-Shannon divergence in bits; 0 = identical."""
    keys = set(p) | set(q)
    out = 0.0
    for k in keys:
        a, b = p.get(k, 0.0), q.get(k, 0.0)
        m = (a + b) / 2
        if a:
            out += 0.5 * a * math.log2(a / m)
        if b:
            out += 0.5 * b * math.log2(b / m)
    return out


def dist(counter):
    t = sum(counter.values())
    return {k: v / t for k, v in counter.items()} if t else {}


# --------------------------------------------------------------------------
# 1. per-section profile
# --------------------------------------------------------------------------

def profile(rows):
    by = defaultdict(list)
    for f, sec, cur, hand, w in rows:
        by[sec].append(w)
    print("per-section profile")
    print(f"  {'section':15s} {'tokens':>7s} {'types':>6s} {'h1':>5s} {'h2':>5s} "
          f"{'len':>5s} {'sd':>5s} {'t/k%':>6s} {'p/f%':>6s} {'qo%':>6s} {'ch%':>6s} "
          f"{'-y%':>6s} {'-dy%':>6s}")
    print("  " + "-" * 92)
    prof = {}
    for sec in SECTIONS:
        ws = by.get(sec)
        if not ws:
            continue
        h1, h2 = h2_of(ws)
        L = [len(w) for w in ws]
        mean = sum(L) / len(L)
        sd = math.sqrt(sum((x - mean) ** 2 for x in L) / len(L))
        tk = sum(1 for w in ws if w[0] in "tk") / len(ws)
        pf = sum(1 for w in ws if w[0] in "pf") / len(ws)
        qo = sum(1 for w in ws if w.startswith("qo")) / len(ws)
        ch = sum(1 for w in ws if w.startswith(("ch", "sh"))) / len(ws)
        y = sum(1 for w in ws if w.endswith("y")) / len(ws)
        dy = sum(1 for w in ws if w.endswith("dy")) / len(ws)
        prof[sec] = dict(tokens=len(ws), types=len(set(ws)), h1=h1, h2=h2,
                         mean=mean, sd=sd, tk=tk, pf=pf, qo=qo, ch=ch, y=y, dy=dy,
                         words=ws)
        print(f"  {sec:15s} {len(ws):7d} {len(set(ws)):6d} {h1:5.2f} {h2:5.2f} "
              f"{mean:5.2f} {sd:5.2f} {100*tk:5.1f}% {100*pf:5.1f}% {100*qo:5.1f}% "
              f"{100*ch:5.1f}% {100*y:5.1f}% {100*dy:5.1f}%")
    return prof


# --------------------------------------------------------------------------
# 2. how far apart are the distributions, and on which axis?
# --------------------------------------------------------------------------

def axes(prof):
    """JS divergence between every pair of sections, per axis."""
    print("\ndistance between sections, by axis (Jensen-Shannon, bits)")
    axes_def = {
        "onset": lambda ws: dist(Counter(onset(w) for w in ws)),
        "last2": lambda ws: dist(Counter(w[-2:] for w in ws)),
        "first2": lambda ws: dist(Counter(w[:2] for w in ws)),
        "length": lambda ws: dist(Counter(len(w) for w in ws)),
        "chars": lambda ws: dist(Counter(c for w in ws for c in w)),
    }
    names = [s for s in SECTIONS if s in prof]
    base = {}
    for name, fn in axes_def.items():
        d = {s: fn(prof[s]["words"]) for s in names}
        vals = []
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                vals.append(js(d[a], d[b]))
        # baseline: two random halves of the SAME section differ by sampling noise
        rng_split = []
        import random
        r = random.Random(0)
        for s in names:
            ws = list(prof[s]["words"])
            r.shuffle(ws)
            h = len(ws) // 2
            rng_split.append(js(fn(ws[:h]), fn(ws[h:])))
        base[name] = (sum(vals) / len(vals), sum(rng_split) / len(rng_split))
        print(f"  {name:8s} mean between-section {base[name][0]:.4f}   "
              f"within-section noise {base[name][1]:.4f}   "
              f"ratio {base[name][0]/max(base[name][1],1e-9):5.1f}x")
    return base


def matrix(prof, axis="last2"):
    """Full pairwise table for one axis, plus the within/noise reference."""
    names = [s for s in SECTIONS if s in prof]
    fn = {"onset": lambda ws: dist(Counter(onset(w) for w in ws)),
          "last2": lambda ws: dist(Counter(w[-2:] for w in ws)),
          "length": lambda ws: dist(Counter(len(w) for w in ws))}[axis]
    print(f"\npairwise JS on {axis}")
    print("  " + " " * 15 + " ".join(f"{n[:6]:>7s}" for n in names))
    for a in names:
        row = []
        for b in names:
            row.append(js(fn(prof[a]["words"]), fn(prof[b]["words"])))
        print(f"  {a:15s}" + " ".join(f"{v:7.3f}" for v in row))


# --------------------------------------------------------------------------
# 3. is it Currier A vs B (a dialect), or the subject matter?
# --------------------------------------------------------------------------

def dialect(rows, prof):
    print("\nis the split Currier A / B (dialect) or the section (subject)?")
    by_cur = defaultdict(list)
    for f, sec, cur, hand, w in rows:
        by_cur[cur].append(w)
    if len(by_cur) >= 2:
        A, B = by_cur.get("A", []), by_cur.get("B", [])
        print(f"  Currier A: {len(A):6d} words   Currier B: {len(B):6d} words")
        for lbl, ws in (("A", A), ("B", B)):
            h1, h2 = h2_of(ws)
            mn = sum(len(w) for w in ws) / len(ws)
            print(f"    {lbl}: h2 {h2:5.2f}  mean len {mn:5.2f}  "
                  f"t/k {100*sum(1 for w in ws if w[0] in 'tk')/len(ws):5.1f}%  "
                  f"p/f {100*sum(1 for w in ws if w[0] in 'pf')/len(ws):5.1f}%  "
                  f"-y {100*sum(1 for w in ws if w.endswith('y'))/len(ws):5.1f}%")
    # section composition of each Currier language
    comp = defaultdict(Counter)
    for f, sec, cur, hand, w in rows:
        comp[cur][sec] += 1
    for cur in sorted(comp):
        tot = sum(comp[cur].values())
        top = ", ".join(f"{s} {100*c/tot:.0f}%" for s, c in comp[cur].most_common(4))
        print(f"    {cur} is made of: {top}")


def gallows_swap_test(prof):
    """Currier's A/B difference is partly a glyph swap: t/k in A, p/f in B.

    If the sections' main difference is that swap, then rewriting one section with the
    other's gallows should move it a long way toward the other section -- a change a
    scribe makes by simply choosing a different pen stroke.
    """
    print("\ngallows-swap test: is the herbal->recipes gap a pen-stroke substitution?")
    pairs = [("herbal", "recipes"), ("herbal", "biological"),
             ("herbal", "pharmaceutical"), ("pharmaceutical", "recipes")]
    for a, b in pairs:
        if a not in prof or b not in prof:
            continue
        wa, wb = prof[a]["words"], prof[b]["words"]
        da = dist(Counter(w[-2:] for w in wa))
        db = dist(Counter(w[-2:] for w in wb))
        fa = dist(Counter(w[:2] for w in wa))
        fb = dist(Counter(w[:2] for w in wb))
        before = js(fa, fb)
        for mapping in ([(("t", "p")), (("k", "f"))],
                        [(("t", "p")), (("k", "f")), (("ch", "sh"))],
                        [(("t", "p")), (("k", "f")), (("qo", "qo"))]):
            sw = []
            for w in wa:
                for x, y in mapping:
                    if w.startswith(x):
                        w = y + w[len(x):]
                        break
                sw.append(w)
            fa2 = dist(Counter(w[:2] for w in sw))
            d2 = dist(Counter(w[-2:] for w in sw))
            print(f"  {a:15s} -> {b:14s}  onset JS {before:.4f} -> {js(fa2, fb):.4f}"
                  f"   (mapping {[x+'->'+y for x,y in mapping]})")
            break
        # also: does swapping gallows change the tail profile at all?
        la = dist(Counter(len(w) for w in wa))
        lb = dist(Counter(len(w) for w in wb))
        print(f"  {'':15s}    last2 JS {js(da, db):.4f}   length JS {js(la, lb):.4f}")


# --------------------------------------------------------------------------
# 4. shared core vs section-specific periphery
# --------------------------------------------------------------------------

def core_periphery(prof, rows):
    print("\nshared stock vs section-specific vocabulary")
    names = [s for s in SECTIONS if s in prof]
    sets = {s: set(prof[s]["words"]) for s in names}
    print(f"  {'section':15s} {'types':>6s} {'in >=3 sections':>16s} {'token mass':>11s} "
          f"{'top-20 shared':>14s}")
    print("  " + "-" * 70)
    shared3 = set()
    for w in set().union(*sets.values()):
        if sum(1 for s in names if w in sets[s]) >= 3:
            shared3.add(w)
    for s in names:
        ws = prof[s]["words"]
        c = Counter(ws)
        types = len(c)
        common3 = sum(1 for w in c if w in shared3)
        mass = sum(n for w, n in c.items() if w in shared3) / len(ws)
        top20 = [w for w, _ in c.most_common(20)]
        sh = sum(1 for w in top20 if w in shared3)
        print(f"  {s:15s} {types:6d} {100*common3/types:15.1f}% {100*mass:10.1f}% "
              f"{sh:12d}/20")
    # are the top words the same words, or different words in the same slots?
    print("\n  the most frequent word of each section, and its rank in the others:")
    for s in names:
        top = [w for w, _ in Counter(prof[s]["words"]).most_common(5)]
        print(f"    {s:15s} {', '.join(top)}")


# --------------------------------------------------------------------------
# 5. where does the transfer error actually come from?
# --------------------------------------------------------------------------

def decomposition():
    """Full per-metric error for a cross-section transfer, worst first."""
    from tier2_metrics import measure_document
    from tune_artgen import tier1, err, split_by_folio, flatten
    from voynich_artgen import ArtGenerator
    import json
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from section_transfer import section_words, build, finish

    cfg = json.load(open(V.frozen_path("FROZEN_CONFIG.json"), encoding="utf-8"))
    words, paras = section_words()
    for src, dst in (("herbal", "recipes"), ("herbal", "herbal")):
        g = build(list(words[src]))
        real2 = finish(g, paras[src], paras[dst], cfg)
        doc = g.document(real2["paras"], seed=7, p_copy=cfg["p_copy"],
                         recency_alpha=cfg["recency_alpha"],
                         buffer_size=cfg["buffer_size"],
                         cross_onset=cfg["cross_onset"], p_repeat=cfg["p_repeat"],
                         p_pair=cfg["p_pair"], line_fit=cfg["line_fit"],
                         gallows_scale=cfg["gallows_scale"])
        t2, _ = measure_document(doc)
        rows = sorted(((err(t2[k], real2[k]), k, t2[k], real2[k]) for k in real2),
                      reverse=True)
        print(f"\n{src} -> {dst}: worst tier-2 metrics")
        print(f"  {'metric':32s} {'gen':>10s} {'real':>10s} {'err%':>8s}")
        print("  " + "-" * 64)
        for e, k, a, b in rows[:12]:
            print(f"  {k:32s} {a:10.3f} {b:10.3f} {e:8.1f}")
        mean = sum(r[0] for r in rows) / len(rows)
        print(f"  {'MEAN over 29 metrics':32s} {'':>10s} {'':>10s} {mean:8.1f}")


if __name__ == "__main__":
    rows = load_rows()
    prof = profile(rows)
    axes(prof)
    matrix(prof, "last2")
    matrix(prof, "onset")
    dialect(rows, prof)
    gallows_swap_test(prof)
    core_periphery(prof, rows)
    decomposition()
