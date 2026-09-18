"""Statistical fingerprint comparison: Voynichese vs. natural-language corpora."""
import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "data", "ref")

WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def tok_from_conllu(path, limit=40000):
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            form = parts[1].lower()
            if not form or form == "_":
                continue
            if not WORD_RE.fullmatch(form):
                continue
            out.append(form)
            if len(out) >= limit:
                return out
    return out


def tok_from_text(path, limit=40000, lower=True):
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            for w in WORD_RE.findall(line):
                if lower:
                    w = w.lower()
                out.append(w)
                if len(out) >= limit:
                    return out
    return out


def fingerprint(words):
    """Compute the statistical fingerprint vector of a token list."""
    n = len(words)
    wc = Counter(words)
    types = len(wc)
    hapax = sum(1 for c in wc.values() if c == 1)

    # character unigram / bigram entropy
    chars, bigs = Counter(), Counter()
    for w in words:
        for c in w:
            chars[c] += 1
        for i in range(len(w) - 1):
            bigs[w[i:i + 2]] += 1
    nc = sum(chars.values())
    h1 = -sum((c / nc) * math.log2(c / nc) for c in chars.values())
    nb = sum(bigs.values())
    hxy = -sum((c / nb) * math.log2(c / nb) for c in bigs.values())
    h2 = hxy - h1

    # word entropy
    hw = -sum((c / n) * math.log2(c / n) for c in wc.values())

    # word-length stats
    lens = Counter(len(w) for w in words)
    mean_len = sum(k * v for k, v in lens.items()) / n
    var_len = sum(v * (k - mean_len) ** 2 for k, v in lens.items()) / n
    sd_len = math.sqrt(var_len) if var_len > 0 else 0

    # positional character entropy (from start and from end, capped at 4)
    pos_fwd = [Counter() for _ in range(4)]
    pos_bwd = [Counter() for _ in range(4)]
    for w in words:
        for i in range(min(4, len(w))):
            pos_fwd[i][w[i]] += 1
            pos_bwd[i][w[len(w) - 1 - i]] += 1

    def H(c):
        t = sum(c.values())
        return -sum((v / t) * math.log2(v / t) for v in c.values()) if t else 0.0

    h_init = sum(H(p) for p in pos_fwd) / 4
    h_final = sum(H(p) for p in pos_bwd) / 4

    return {
        "tokens": n,
        "types": types,
        "ttr": types / n,
        "hapax_%": 100 * hapax / n,
        "h1_char": h1,
        "h2_char": h2,
        "h_word": hw,
        "mean_len": mean_len,
        "sd_len": sd_len,
        "h_pos_init": h_init,
        "h_pos_final": h_final,
        "len_hist": {k: v / n for k, v in sorted(lens.items())},
    }


def fmt_row(name, fp):
    return (f"{name:14s} {fp['tokens']:7d} {fp['types']:6d} {fp['h2_char']:6.3f} "
            f"{fp['h_word']:6.3f} {fp['hapax_%']:7.2f} {fp['mean_len']:6.2f} "
            f"{fp['sd_len']:5.2f} {fp['h_pos_init']:6.3f} {fp['h_pos_final']:6.3f}")


HEADER = (f"{'corpus':14s} {'tokens':>7s} {'types':>6s} {'h2':>6s} {'H(word)':>6s} "
          f"{'hapax%':>7s} {'len_mu':>6s} {'len_sd':>5s} {'Hinit':>6s} {'Hfin':>6s}")


def main():
    results = {}

    vw = [w[4] for w in V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt"))]
    results["Voynichese"] = fingerprint(vw)
    results["Voy-A"] = fingerprint([w[4] for w in V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt")) if w[2] == "A"])
    results["Voy-B"] = fingerprint([w[4] for w in V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt")) if w[2] == "B"])

    conllu = ["latin", "ocs", "italian", "german", "greek", "english",
              "hebrew", "croatian", "spanish", "turkish", "arabic"]
    for name in conllu:
        p = os.path.join(REF, f"{name}.conllu")
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            results[name] = fingerprint(tok_from_conllu(p))

    for name, fn in [("dante_it", "dante_it.txt"), ("augustine_lat", "confessions_lat.txt")]:
        p = os.path.join(REF, fn)
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            results[name] = fingerprint(tok_from_text(p))

    print(HEADER)
    print("-" * len(HEADER))
    for name, fp in results.items():
        print(fmt_row(name, fp))

    print("\nWord-length distribution (probability of length k):")
    allnames = list(results)
    ks = list(range(1, 13))
    print(f"{'corpus':14s} " + " ".join(f"{k:>5d}" for k in ks))
    for name in allnames:
        lh = results[name]["len_hist"]
        print(f"{name:14s} " + " ".join(f"{lh.get(k,0):5.3f}" for k in ks))

    import json
    out = os.path.join(ROOT, "analysis", "fingerprints.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
