"""Do the labels beside the drawings behave like names?

If the manuscript were a herbal or an astronomical handbook, the short texts written
next to the pictures would be names -- of plants, of stars, of months -- and names have
a measurable signature: they are rare, mostly unique, and they are LONGER than ordinary
words, because names accumulate morphology and borrowings that common words wear away.

So the test is not "do the labels look like names" but "do they carry the signature of
names". Two measurements settle it:

  * against the body text of the same manuscript, and
  * against a rarity-matched control drawn from that body text, because a set of rare
    words will show a high type/token ratio and a high hapax share for free.

Result: the labels mimic the name surface (high type/token ratio, high hapax share) but
their word length is exactly the body average, whereas matched rare words of the same
text are 38 standard deviations longer. They look like a list of names and have none of
the formal properties of one.
"""
import math
import os
import random
import re
import statistics as st
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from refstats import fingerprint, tok_from_conllu

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABEL_TYPES = ("L", "R")          # locus codes used for labels and radial text


def split_labels(path):
    body, labels = [], []
    for folio, locus, ltype, raw, meta in V.parse_ivtff(path):
        t = V.strip_markup(raw).replace("<%>", "").replace("<$>", "")
        ws = [w.strip("-") for w in re.split(r"[.,\s]+", t) if w.strip("-")]
        ws = [w for w in ws if w and not re.search(r"[?!]", w)
              and not any(c in w for c in "[]{}()")]
        if not ws:
            continue
        code = re.sub(r"\d+$", "", ltype)
        if any(k in code for k in LABEL_TYPES) and code not in ("@P0", "+P0", "*P0"):
            labels.extend(ws)
        else:
            body.extend(ws)
    return body, labels


def describe(name, ws):
    fp = fingerprint(ws)
    print(f"| {name} | {fp['tokens']} | {fp['ttr']:.3f} | {fp['hapax_%']:.1f} | "
          f"{fp['h2_char']:.3f} | {fp['mean_len']:.2f} |")
    return fp


def main():
    body, labels = split_labels(os.path.join(ROOT, "data", "IT2a-n.txt"))
    N = len(labels)
    print(f"body {len(body)} words, labels {N} words\n")
    print("| set | tokens | TTR | hapax % | h2 | mean word length |")
    print("|---|---|---|---|---|---|")
    describe("body text", body)
    describe("labels", labels)

    # rarity-matched control: random draws of N body words, and N body hapax
    bc = Counter(body)
    hapax = [w for w in body if bc[w] == 1]
    rng = random.Random(1)
    sims = [fingerprint(rng.sample(hapax, min(N, len(hapax)))) for _ in range(300)]
    lab = fingerprint(labels)
    print(f"\nmatched control = {N} random hapax words of the same text, 300 draws:")
    for key in ("ttr", "hapax_%", "h2_char", "mean_len", "h_pos_final"):
        vals = [s[key] for s in sims]
        mu, sd = st.mean(vals), st.pstdev(vals)
        z = (lab[key] - mu) / sd if sd else 0.0
        print(f"  {key:12s} control {mu:8.3f}  labels {lab[key]:8.3f}   z = {z:+.2f}")

    # how much of the label vocabulary is drawn from the body's own palette?
    bv, lv = set(body), set(labels)
    print(f"\nlabel types also present in the body text: {len(lv & bv)/len(lv)*100:.1f}%")
    tot = sum(bc.values())
    pv = {w: c / tot for w, c in bc.items()}
    exp = sum(1 - (1 - pv.get(w, 0)) ** N for w in lv) / len(lv) * 100
    print(f"expected if drawn from the body distribution: {exp:.1f}%")

    # and how do real name-like words behave in a language?
    for n in ("latin", "italian"):
        p = os.path.join(ROOT, "data", "ref", f"{n}.conllu")
        if not os.path.exists(p):
            continue
        ws = tok_from_conllu(p)
        c = Counter(ws)
        rare = [w for w in ws if c[w] <= 2]
        describe(f"{n}, rare words (name proxy)", rare)


if __name__ == "__main__":
    main()
