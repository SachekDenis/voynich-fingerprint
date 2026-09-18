"""Where does the manuscript's long-range character correlation come from?

Our generator reproduces 43 of 44 metrics but under-produces character mutual
information at offsets of 6 to 12. This script asks what that quantity is actually
measuring, and whether the gap is real.

Three things are checked in order:

  1. is the gap an artefact of comparing the whole manuscript (labels, radial and
     circular text included) against a generator that only makes paragraph text?
  2. what is the shape of MI(d) -- where exactly do the two diverge?
  3. is the divergence carried by pairs *inside* a word or pairs that *cross* a word
     boundary?  A character stream with no separators mixes the two, and only the
     second kind is long-range in any meaningful sense.
"""
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V


def mi_at(seq, d, mask=None):
    """MI between seq[i] and seq[i+d]; mask selects which pairs to count."""
    joint, A, B = Counter(), Counter(), Counter()
    n = 0
    for i in range(len(seq) - d):
        if mask is not None and not mask[i]:
            continue
        a, b = seq[i], seq[i + d]
        joint[(a, b)] += 1
        A[a] += 1
        B[b] += 1
        n += 1
    if n < 50:
        return float("nan"), n
    def H(c):
        return -sum((v / n) * math.log2(v / n) for v in c.values())
    return H(A) + H(B) - H(joint), n


def stream(words):
    """Concatenated characters plus, for every position, its word index and offset."""
    seq, widx, off = [], [], []
    for k, w in enumerate(words):
        for j, c in enumerate(w):
            seq.append(c)
            widx.append(k)
            off.append(j)
    return seq, widx, off


def profile(words, dmax=30, label=""):
    seq, widx, off = stream(words)
    within = [widx[i] == widx[i] for i in range(len(seq))]
    rows = []
    for d in range(1, dmax + 1):
        m_within = [i < len(seq) - d and widx[i] == widx[i + d] for i in range(len(seq))]
        m_across = [i < len(seq) - d and widx[i] != widx[i + d] for i in range(len(seq))]
        mi_all, _ = mi_at(seq, d)
        mi_w, nw = mi_at(seq, d, m_within)
        mi_a, na = mi_at(seq, d, m_across)
        rows.append((d, mi_all, mi_w, nw, mi_a, na))
    print(f"\n{label}: MI(d), within-word vs across-word")
    print(f"  {'d':>3s} {'all':>7s} {'within':>8s} {'n_w':>7s} {'across':>8s} {'n_a':>7s}")
    for d, a, w, nw, c, na in rows:
        ws = f"{w:8.4f}" if w == w else "     n/a"
        cs = f"{c:8.4f}" if c == c else "     n/a"
        print(f"  {d:3d} {a:7.4f} {ws} {nw:7d} {cs} {na:7d}")
    return rows


def word_recurrence(words, kmax=6):
    """P(word[i+k] == word[i]) and P(edit-distance-1 neighbour at i+k)."""
    out = {}
    for k in range(1, kmax + 1):
        same = 0
        near = 0
        n = len(words) - k
        for i in range(n):
            a, b = words[i], words[i + k]
            if a == b:
                same += 1
            elif len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1:
                near += 1
        out[k] = (100 * same / n, 100 * near / n)
    return out


if __name__ == "__main__":
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from tier2_metrics import load_real_document, measure_document
    from tune_artgen import split_by_folio, flatten

    tr, te = split_by_folio()
    real_body = flatten(te)
    real_all = [w[4] for w in V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt"))]
    print(f"body-only words {len(real_body)}, all loci {len(real_all)}")

    # 1. does the gap survive when both sides are body text?
    for name, ws in (("manuscript: ALL loci", real_all),
                     ("manuscript: body only", real_body)):
        seq, widx, off = stream(ws)
        far = sum(mi_at(seq, d)[0] for d in range(6, 13)) / 7
        print(f"  {name:26s} far MI (d=6..12) = {far:.4f}")

    profile(real_body[:20000], label="manuscript (body)")
    profile(real_all[:20000], label="manuscript (all loci)")
