"""What makes the manuscript's long words more internally correlated than ours?

Within-word character MI at offsets 6-12 is the one metric the generator under-produces
(0.140 against 0.181 at offset 8, measured on words of at least that length). Before
building a mechanism, this measures what the difference actually is:

  * match rate      P(char[i] == char[i+d]) inside a word
  * positional bias how concentrated the character at each position is
  * repeat structure how often a long word repeats one of its own bigrams
  * conditional entropy H(char[i+d] | char[i])
"""
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def match_profile(words, min_len=8, dmax=10):
    """P(char[i] == char[i+d]) over words long enough to contain the pair."""
    out = []
    for d in range(1, dmax + 1):
        same = tot = 0
        for w in words:
            if len(w) < d + 1:
                continue
            for i in range(len(w) - d):
                tot += 1
                if w[i] == w[i + d]:
                    same += 1
        out.append((d, 100 * same / tot if tot else float("nan"), tot))
    return out


def cond_entropy(words, d=8, min_len=9):
    """H(char[i+d] | char[i]) inside long words, and the marginal H for comparison."""
    joint = Counter()
    gave = Counter()
    got = Counter()
    for w in words:
        if len(w) < min_len:
            continue
        for i in range(len(w) - d):
            joint[(w[i], w[i + d])] += 1
            gave[w[i]] += 1
            got[w[i + d]] += 1

    def H(c):
        t = sum(c.values())
        return -sum((v / t) * math.log2(v / t) for v in c.values())
    n = sum(joint.values())
    if not n:
        return float("nan"), float("nan"), 0
    hxy = -sum((v / n) * math.log2(v / n) for v in joint.values())
    return H(gave), H(got), hxy


def bigram_repeat(words, min_len=8):
    """Share of long words that contain a bigram twice."""
    n = hits = 0
    for w in words:
        if len(w) < min_len:
            continue
        n += 1
        b = Counter(w[i:i + 2] for i in range(len(w) - 1))
        if any(v > 1 for v in b.values()):
            hits += 1
    return 100 * hits / max(1, n), n


def char_by_position(words, min_len=8, np_=8):
    """Entropy of the character at each position in long words."""
    cols = [Counter() for _ in range(np_)]
    for w in words:
        if len(w) < min_len:
            continue
        for i in range(np_):
            cols[i][w[i]] += 1
            cols[i][w[-1 - i]] += 1
    def H(c):
        t = sum(c.values())
        return -sum((v / t) * math.log2(v / t) for v in c.values()) if t else 0
    return [round(H(c), 3) for c in cols]


def compare(name, words):
    mp = match_profile(words)
    hx, hy, hxy = cond_entropy(words)
    br, n = bigram_repeat(words)
    cp = char_by_position(words)
    print(f"\n{name}  (words of 8+ characters used for the within-word figures)")
    print("  match rate P(c[i]==c[i+d]): " +
          " ".join(f"d{d}:{v:.1f}%" for d, v, _ in mp[:6]))
    print(f"  H(c[i])   = {hx:.3f}   H(c[i+8]) = {hy:.3f}   H(both) = {hxy:.3f}")
    print(f"  long words containing a repeated bigram: {br:.1f}%  (n={n})")
    print("  positional entropy, first eight positions: " + " ".join(map(str, cp[:4])))
    print("  positional entropy, last  eight positions: " + " ".join(map(str, cp[4:])))


if __name__ == "__main__":
    import json
    import voynich_lib as V
    from refstats import tok_from_conllu
    from tier2_metrics import measure_document, GALLOWS
    from voynich_artgen import ArtGenerator
    from tune_artgen import split_by_folio, flatten

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "FROZEN_CONFIG.json"), encoding="utf-8"))
    tr, te = split_by_folio()
    train = flatten(tr)
    test = flatten(te)
    real2, _ = measure_document(te)
    g = ArtGenerator(train, merges=cfg["merges"])
    g.calibrate()
    g.calibrate_onset(train)
    g.calibrate_cross_onset(train)
    g.calibrate_common(train)
    g.calibrate_pairs(train)
    g.calibrate_lengths(tr)
    g.fit_penalty = cfg["fit_penalty"]
    g.calibrate_proposal()
    g.calibrate_layout(tr, gallows_p=0.0)
    g.gallows_scale = cfg["gallows_scale"]
    probe = [ln for p in g.document(40, seed=3) for ln in p]
    nat = sum(1 for ln in probe if ln and any(ln[0].startswith(x) for x in GALLOWS)) / len(probe)
    g.line_gallows_p = max(0.0, (real2["para/line-initial gallows %"] / 100 - nat) / (1 - nat))
    doc = g.document(real2["paras"], seed=7, p_copy=cfg["p_copy"],
                     recency_alpha=cfg["recency_alpha"], buffer_size=cfg["buffer_size"],
                     cross_onset=cfg["cross_onset"], p_repeat=cfg["p_repeat"],
                     p_pair=cfg["p_pair"], line_fit=cfg["line_fit"],
                     gallows_scale=cfg["gallows_scale"])
    gen = flatten(doc)

    compare("manuscript", test)
    compare("generator (bigram chain)", gen)
    compare("latin", tok_from_conllu(os.path.join(ROOT, "data", "ref", "latin.conllu"))[:len(test)])
