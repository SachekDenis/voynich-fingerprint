"""Scorecard: does the generator reproduce every measured characteristic of the text?

Fit on even-numbered leaves, evaluate against the odd-numbered leaves' fingerprint.
Nothing about the test half is used in fitting, so gaps are out-of-sample.
"""
import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from refstats import fingerprint
from voynich_generator import VoynichModel, generate, apply_bpe

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def folio_num(f):
    m = re.match(r"f?(\d+)", f)
    return int(m.group(1)) if m else 0


def load_split():
    rows = V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt"))
    train = [w[4] for w in rows if folio_num(w[0]) % 2 == 0]
    test = [w[4] for w in rows if folio_num(w[0]) % 2 == 1]
    return train, test


def onset(w):
    for g in ("cth", "ckh", "cph", "cfh", "ch", "sh", "qo"):
        if w.startswith(g):
            return g
    return w[0]


def edge_stats(words):
    ins, fin = Counter(), Counter()
    for w in words:
        ins[onset(w)] += 1
        fin[w[-1]] += 1
    t = len(words)
    return (sum(c for _, c in ins.most_common(5)) / t,
            sum(c for _, c in fin.most_common(5)) / t,
            fin["y"] / t,
            sum(c for _, c in Counter(words).most_common(10)) / t)


def cross_MI(words):
    def H(c, t):
        return -sum((v / t) * math.log2(v / t) for v in c.values())
    joint, A, B = Counter(), Counter(), Counter()
    n = 0
    for a, b in zip(words, words[1:]):
        joint[(a[-1], b[0])] += 1
        A[a[-1]] += 1
        B[b[0]] += 1
        n += 1
    return (H(A, n) + H(B, n) - H(joint, n)) / min(H(A, n), H(B, n))


def tv(p, q, ks):
    return 0.5 * sum(abs(p.get(k, 0) - q.get(k, 0)) for k in ks)


def scorecard(name, words, ref_fp, real_vocab):
    fp = fingerprint(words)
    o5, f5, fy, top10 = edge_stats(words)
    mi = cross_MI(words)
    ks = list(range(1, 16))
    nov = sum(1 for w in set(words) if w not in real_vocab) / len(set(words))

    rows = [
        ("h1 (char)", fp["h1_char"], ref_fp["h1_char"]),
        ("h2 (char)", fp["h2_char"], ref_fp["h2_char"]),
        ("H(word)", fp["h_word"], ref_fp["h_word"]),
        ("TTR", fp["ttr"], ref_fp["ttr"]),
        ("hapax %", fp["hapax_%"], ref_fp["hapax_%"]),
        ("mean len", fp["mean_len"], ref_fp["mean_len"]),
        ("sd len", fp["sd_len"], ref_fp["sd_len"]),
        ("H init", fp["h_pos_init"], ref_fp["h_pos_init"]),
        ("H final", fp["h_pos_final"], ref_fp["h_pos_final"]),
        ("len dist TV", tv(fp["len_hist"], ref_fp["len_hist"], ks), 0.0),
        ("top5 onset %", 100 * o5, ref_fp.get("_o5", 0)),
        ("top5 final %", 100 * f5, ref_fp.get("_f5", 0)),
        ("final-y %", 100 * fy, ref_fp.get("_fy", 0)),
        ("top10 word share %", 100 * top10, ref_fp.get("_t10", 0)),
        ("cross-word MI", mi, ref_fp.get("_mi", 0)),
    ]
    return rows, nov


def main():
    train, test = load_split()
    print(f"train {len(train)} words | test {len(test)} words (split by leaf parity)")

    real_vocab = set(train) | set(test)
    test_fp = fingerprint(test)
    o5, f5, fy, t10 = edge_stats(test)
    test_fp["_o5"], test_fp["_f5"], test_fp["_fy"], test_fp["_t10"] = 100*o5, 100*f5, 100*fy, 100*t10
    test_fp["_mi"] = cross_MI(test)

    model = VoynichModel(train, merges=140)
    print(f"BPE table: {len(model.units)} units, largest: {model.units[:12]}")

    results = {}
    for p_copy in (0.0, 0.05, 0.10, 0.15, 0.20):
        gen = generate(model, len(test), seed=7, p_copy=p_copy, matched=True)
        rows, nov = scorecard(f"p_copy={p_copy}", gen, test_fp, real_vocab)
        results[p_copy] = (rows, nov, gen)
    print(f"\n{'metric':22s} {'TEST (target)':>14s} " +
          " ".join(f"{'gen p='+str(p):>13s}" for p in results))
    print("-" * (22 + 15 + 14 * len(results)))
    names = [r[0] for r in results[0.0][0]]
    for i, nm in enumerate(names):
        target = results[0.0][0][i][2]
        vals = " ".join(f"{results[p][0][i][1]:13.3f}" for p in results)
        print(f"{nm:22s} {target:14.3f} {vals}")
    print(f"\n{'novel types %':22s} {'-':>14s} " +
          " ".join(f"{100*results[p][1]:13.1f}" for p in results))

    best = results[0.40][2]
    print("\nsample output:")
    for i in range(0, 240, 60):
        print("  " + " ".join(best[i:i + 60]))


if __name__ == "__main__":
    main()
