"""Tier-2 metrics: structural properties beyond the basic fingerprint.

Covers line fill, paragraph shape, gallows placement, Zipf slope, positional
character distributions, onset classes, repetition and the length tail.
Everything works on a "document" = list of paragraphs, each a list of lines,
each a list of words, so the real text and the generator are measured identically.
"""
import math
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLOWS = ("cth", "ckh", "cph", "cfh", "t", "k", "p", "f")
ONSET_GLYPHS = ("cth", "ckh", "cph", "cfh", "ch", "sh", "qo")


def onset(w):
    for g in ONSET_GLYPHS:
        if w.startswith(g):
            return g
    return w[0] if w else ""


def load_real_document(path=None, body_only=True):
    """Parse the transcription into paragraphs of lines of words.

    Paragraphs are delimited by the manuscript's own paragraph marks: a line opening
    with <%> starts one, a line closing with <$> ends it. Those two markers occur
    exactly 772 times each and pair without a single anomaly, so the segmentation is
    the transcriber's, not a guess.

    The locus type (@ / + / *) is NOT the paragraph boundary. @ marks only the first
    paragraph of a page and * a mid-page start; using them merges whole pages of
    running text into one 'paragraph' -- in the recipes section that turns ~12 real
    paragraphs into one 43-line block, which is not a property of the manuscript.

    body_only keeps only running-text loci, dropping labels, radial and circular
    text, which have a different line geometry.
    """
    path = path or os.path.join(ROOT, "data", "IT2a-n.txt")
    paras, cur = [], []
    open_para = False
    for folio, locus, ltype, raw, meta in V.parse_ivtff(path):
        code = re.sub(r"\d+$", "", ltype)
        if body_only and code.lstrip("@+*&=")[:1] not in ("P",):
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
        if not ws:
            continue
        if starts and open_para and cur:
            paras.append(cur)
            cur = []
        open_para = True
        cur.append(ws)
        if ends:
            paras.append(cur)
            cur = []
            open_para = False
    if cur:
        paras.append(cur)
    return paras


def entropy(counter):
    t = sum(counter.values())
    return -sum((v / t) * math.log2(v / t) for v in counter.values()) if t else 0.0


def zipf_slope(words, rmax=500):
    """Least-squares slope of log(freq) vs log(rank)."""
    c = Counter(words).most_common(rmax)
    xs = [math.log(i + 1) for i in range(len(c))]
    ys = [math.log(n) for _, n in c]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.0


def measure_document(paras):
    lines = [ln for p in paras for ln in p]
    words = [w for ln in lines for w in ln]
    out = {}

    # --- line fill ---------------------------------------------------------
    cpl = Counter(sum(len(w) for w in ln) for ln in lines)
    out["line chars mean"] = sum(k * v for k, v in cpl.items()) / sum(cpl.values())
    out["line chars sd"] = math.sqrt(
        sum(v * (k - out["line chars mean"]) ** 2 for k, v in cpl.items()) / sum(cpl.values()))
    wpl = Counter(len(ln) for ln in lines)
    out["words per line mean"] = sum(k * v for k, v in wpl.items()) / sum(wpl.values())
    out["lines"] = len(lines)

    # --- paragraph shape ---------------------------------------------------
    plens = Counter(len(p) for p in paras)
    out["paras"] = len(paras)
    out["para lines mean"] = sum(k * v for k, v in plens.items()) / sum(plens.values())

    # --- gallows placement -------------------------------------------------
    firsts = Counter()
    for p in paras:
        for ln in p:
            if ln:
                firsts[onset(ln[0])] += 1
    tot_f = sum(firsts.values())
    out["para/line-initial gallows %"] = 100 * sum(
        c for o, c in firsts.items() if o in GALLOWS) / tot_f if tot_f else 0
    out["all gallows %"] = 100 * sum(
        1 for w in words if any(w.startswith(g) for g in GALLOWS)) / len(words)

    # --- onset classes -----------------------------------------------------
    ons = Counter(onset(w) for w in words)
    tot_o = sum(ons.values())
    out["onset ent ropy"] = entropy(ons)
    out["qo- onset %"] = 100 * ons.get("qo", 0) / tot_o
    out["ch- onset %"] = 100 * ons.get("ch", 0) / tot_o
    out["y- onset %"] = 100 * ons.get("y", 0) / tot_o

    # --- (first,last) character pair coverage ------------------------------
    pairs = Counter((w[0], w[-1]) for w in words)
    out["top10 (first,last) pairs %"] = 100 * sum(
        c for _, c in pairs.most_common(10)) / len(words)
    out["distinct (first,last) pairs"] = len(pairs)

    # --- Zipf --------------------------------------------------------------
    out["zipf slope (top500)"] = zipf_slope(words, 500)
    out["hapax share of types %"] = 100 * sum(
        1 for _, c in Counter(words).items() if c == 1) / len(set(words))

    # --- repetition --------------------------------------------------------
    out["adjacent identical words %"] = 100 * sum(
        1 for a, b in zip(words, words[1:]) if a == b) / max(1, len(words) - 1)
    bg = Counter(zip(words, words[1:]))
    out["repeated word-pair %"] = 100 * sum(
        c for c in bg.values() if c > 1) / max(1, sum(bg.values()))

    # --- positional character distribution ---------------------------------
    fwd = [Counter() for _ in range(4)]
    bwd = [Counter() for _ in range(4)]
    for w in words:
        for i in range(min(4, len(w))):
            fwd[i][w[i]] += 1
            bwd[i][w[-1 - i]] += 1
    for i in range(4):
        out[f"H pos{i+1} from start"] = entropy(fwd[i])
        out[f"H pos{i+1} from end"] = entropy(bwd[i])

    # --- length tail -------------------------------------------------------
    n = len(words)
    out["len>=8 %"] = 100 * sum(1 for w in words if len(w) >= 8) / n
    out["len>=10 %"] = 100 * sum(1 for w in words if len(w) >= 10) / n
    out["len<=2 %"] = 100 * sum(1 for w in words if len(w) <= 2) / n

    return out, words


def compare(real, gen, label=""):
    keys = list(real)
    print(f"{'metric':30s} {'real':>10s} {'gen':>10s} {'err%':>8s}")
    print("-" * 62)
    errs = []
    for k in keys:
        a, b = gen[k], real[k]
        if abs(a) < 1e-12 and abs(b) < 1e-12:
            e = 0.0
        elif abs(b) < 1e-9:
            e = abs(a) * 100
        else:
            e = abs(a - b) / abs(b) * 100
        errs.append(e)
        print(f"{k:30s} {b:10.3f} {a:10.3f} {e:8.1f}")
    print("-" * 62)
    print(f"{'mean error':30s} {'':>10s} {'':>10s} {sum(errs)/len(errs):8.1f}")
    return errs


if __name__ == "__main__":
    doc = load_real_document()
    real, words = measure_document(doc)
    print(f"real document: {real['paras']} paragraphs, {real['lines']} lines, {len(words)} words\n")
    for k, v in real.items():
        print(f"  {k:32s} {v:10.3f}")
