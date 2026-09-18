"""Metrics taken from the published Voynich literature, added for comparison.

These four are standard in the field but were missing from our own metric set, so any
generator claiming to reproduce the manuscript should be checked against them too:

  Heaps' law          vocabulary growth V = K n^b          (Ponnaluri 2024)
  Brevity law         mean word length falls with rank     (Ponnaluri 2024)
  bigram concentration  share of text carried by the few highest-probability
                        character bigrams                 (Lindemann & Bowern 2020)
  long-range MI       mutual information between characters d apart
                        (Landini 2001 found the text is not memoryless)
"""
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def heaps(words):
    """Vocabulary growth: least-squares slope of log V against log n."""
    seen = set()
    pts = []
    for i, w in enumerate(words, 1):
        seen.add(w)
        if i % max(1, len(words) // 400) == 0:
            pts.append((math.log(i), math.log(len(seen))))
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    num = sum((x - mx) * (y - my) for x, y in pts)
    den = sum((x - mx) ** 2 for x, _ in pts)
    b = num / den
    K = math.exp(my - b * mx)
    return b, K


def brevity(words):
    """Mean word length as a decreasing function of rank."""
    freq = Counter(words)
    mean_len = defaultdict(list)
    for w, c in freq.items():
        mean_len[c].append(len(w))
    xs, ys = [], []
    for c in sorted(mean_len):
        if len(mean_len[c]) < 3:
            continue
        xs.append(math.log(c))
        ys.append(sum(mean_len[c]) / len(mean_len[c]))
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.0


def bigram_concentration(words, thr=0.5):
    """Share of all character bigrams carried by high-probability transitions.

    Lindemann & Bowern report that a handful of bigrams covers a large share of the
    Voynich text, far more than in ordinary languages.
    """
    given = defaultdict(Counter)
    total = 0
    for w in words:
        for a, b in zip(w, w[1:]):
            given[a][b] += 1
            total += 1
    hot = set()
    for a, c in given.items():
        t = sum(c.values())
        for b, k in c.items():
            if k / t >= thr:
                hot.add((a, b))
    hits = 0
    for w in words:
        for a, b in zip(w, w[1:]):
            if (a, b) in hot:
                hits += 1
    return 100.0 * hits / max(1, total), len(hot)


def long_range_mi(words, maxd=12):
    """Mutual information between characters d apart, averaged over distances."""
    seq = [c for w in words for c in w]
    out = {}
    for d in range(1, maxd + 1):
        joint, A, B = Counter(), Counter(), Counter()
        for i in range(len(seq) - d):
            joint[(seq[i], seq[i + d])] += 1
            A[seq[i]] += 1
            B[seq[i + d]] += 1
        n = len(seq) - d
        if not n:
            break

        def H(c):
            return -sum((v / n) * math.log2(v / n) for v in c.values())
        out[d] = H(A) + H(B) - H(joint)
    return out


def report(name, words):
    b, K = heaps(words)
    br = brevity(words)
    conc, nhot = bigram_concentration(words)
    mi = long_range_mi(words)
    far = sum(mi[d] for d in range(6, 13)) / 7 if len(mi) >= 12 else float("nan")
    print(f"{name:22s} Heaps b={b:.3f}  Brevity={br:+.3f}  "
          f"hot bigrams={nhot:3d} covering {conc:5.1f}%  MI(d=6..12)={far:.3f}")
    return dict(heaps_b=b, heaps_K=K, brevity=br, hot_bigrams=nhot,
                hot_coverage=conc, mi_far=far, mi=mi)


if __name__ == "__main__":
    import voynich_lib as V
    from refstats import tok_from_conllu
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    vms = [w[4] for w in V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt"))]
    report("Voynichese", vms)
    for n in ("latin", "italian", "ocs", "german"):
        p = os.path.join(ROOT, "data", "ref", f"{n}.conllu")
        if os.path.exists(p):
            report(n, tok_from_conllu(p))
    # and the generator's output, if it is around
    import glob
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "gen", "gen_seed*.txt")))[:1]:
        ws = [w for line in open(p, encoding="utf-8")
              if line.strip() and not line.startswith("#") for w in line.split()]
        report("self-citation gen", ws)
