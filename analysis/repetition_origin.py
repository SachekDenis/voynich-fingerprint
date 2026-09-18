"""Where does the manuscript's excess of word repetition actually sit?

The text repeats a word at 0.89 % per lag, flat out to lag 20, against 0.34 % that its
own frequency spectrum allows (Simpson's sum f^2). A flat excess has several possible
hand-made origins and they can be told apart by *where* the excess lives:

  local copying     the scribe re-reads or copies from nearby text   -> short lags only
  formulaic phrasing recipes and herbals repeat stock formulae       -> a peak at the
                                                                        phrase length
  topical clustering a passage about one plant reuses its vocabulary -> within a paragraph,
                                                                        decaying across it
  limited repertoire the writer's standing set of word-forms         -> flat, everywhere,
                                                                        and made of common
                                                                        words
  drift             the working set changes slowly over the book     -> flat within a
                                                                        page, decaying
                                                                        over pages

Four measurements separate them.
"""
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def split_with_context(path=None, body_only=True):
    """Word stream with the paragraph index of every token."""
    import re
    import voynich_lib as V
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = path or os.path.join(ROOT, "data", "IT2a-n.txt")
    words, para, folio, line = [], [], [], []
    p = -1
    for f, locus, ltype, raw, meta in V.parse_ivtff(path):
        code = re.sub(r"\d+$", "", ltype)
        if body_only and code.lstrip("@+*&=")[:1] != "P":
            continue
        starts = raw.lstrip().startswith("<%>")
        t = V.strip_markup(raw).replace("<%>", "").replace("<$>", "")
        ws = [w.strip("-") for w in re.split(r"[.,\s]+", t) if w.strip("-")]
        ws = [w for w in ws if w and not re.search(r"[?!]", w)
              and not any(c in w for c in "[]{}()")]
        if not ws:
            continue
        if starts:
            p += 1
        for w in ws:
            words.append(w)
            para.append(p)
            folio.append(f)
            line.append(locus)
    return words, para, folio, line


def repeat_rate(words, lag, mask=None):
    n = hit = 0
    for i in range(len(words) - lag):
        if mask is not None and not mask[i]:
            continue
        n += 1
        if words[i] == words[i + lag]:
            hit += 1
    return 100.0 * hit / n if n else float("nan"), n


def boundary_table(words, para, folio, line_of, lags=(2, 3, 4, 5, 6)):
    """Repeat rate for pairs that stay inside a unit against pairs that cross it.

    Averaged over lags 2-6, so the answer is not an artefact of one distance.
    """
    N = len(words)
    units = {"line": line_of, "paragraph": para, "folio": folio}
    for name, u in units.items():
        ins_n = ins_h = out_n = out_h = 0
        for lag in lags:
            for i in range(N - lag):
                if u[i] != u[i + lag]:
                    out_n += 1
                    out_h += words[i] == words[i + lag]
                else:
                    ins_n += 1
                    ins_h += words[i] == words[i + lag]
        print(f"  {name:10s} inside {100*ins_h/ins_n:6.3f}%   "
              f"across {100*out_h/out_n:6.3f}%   "
              f"(n {ins_n} / {out_n})")


def main():
    words, para, folio, line_of = split_with_context()
    N = len(words)
    print(f"{N} words, {len(set(para))} paragraphs, {len(set(folio))} folios\n")

    c = Counter(words)
    simp = sum((v / N) ** 2 for v in c.values()) * 100
    print(f"Simpson index of the word distribution: {simp:.3f} %  "
          f"(the rate for a memoryless text)")

    # 0. where does the texture change?  inside a unit vs across its boundary
    print("repeat rate, lags 2-6 pooled, by boundary:")
    boundary_table(words, para, folio, line_of)
    print()

    # 1. same paragraph vs different paragraph
    same = [i < N - 1 and para[i] == para[i + 1] for i in range(N)]
    for lag in (1, 2, 3, 4, 5, 6, 8, 10, 15, 20):
        m_same = [i < N - lag and para[i] == para[i + lag] for i in range(N)]
        m_diff = [i < N - lag and para[i] != para[i + lag] for i in range(N)]
        a, _ = repeat_rate(words, lag, m_same)
        b, _ = repeat_rate(words, lag, m_diff)
        print(f"  lag {lag:2d}   same paragraph {a:5.3f}%   different paragraph {b:5.3f}%")

    # 2. how far does the correlation reach?
    print("\nrepeat rate against lag, to lag 120 (in units of the memoryless rate)")
    row = []
    for lag in (1, 2, 5, 10, 20, 40, 60, 80, 100, 120):
        r, _ = repeat_rate(words, lag)
        row.append(f"{lag}:{r / simp:.2f}x")
    print("  " + "  ".join(row))

    # 3. which words carry the excess?  split by frequency band
    print("\nrepeat rate at lags 2-6 by frequency band of the first word")
    bands = [("1 (hapax)", lambda f: f == 1), ("2", lambda f: f == 2),
             ("3-5", lambda f: 3 <= f <= 5), ("6-20", lambda f: 6 <= f <= 20),
             ("21-100", lambda f: 21 <= f <= 100), ("100+", lambda f: f > 100)]
    for name, test in bands:
        hit = tot = 0
        for lag in range(2, 7):
            for i in range(N - lag):
                if not test(c[words[i]]):
                    continue
                tot += 1
                if words[i] == words[i + lag]:
                    hit += 1
        exp = 0.0
        for w in c:
            if test(c[w]):
                exp += (c[w] / N) ** 2
        print(f"  frequency {name:10s} observed {100*hit/tot:6.3f}%   "
              f"memoryless {100*exp:6.3f}%   ratio {100*hit/tot/(100*exp):4.2f}x")

    # 4. position in the paragraph
    print("\nrepeat rate at lags 2-6 by position of the first word in its paragraph")
    for lo, hi, name in ((0, 0, "paragraph-initial"), (1, 2, "words 2-3"),
                         (3, 8, "words 4-9"), (9, 10 ** 9, "later")):
        hit = tot = 0
        starts = {}
        cnt = defaultdict(int)
        for i in range(N):
            k = cnt[para[i]]
            cnt[para[i]] += 1
            starts[i] = k
        for lag in range(2, 7):
            for i in range(N - lag):
                if not (lo <= starts[i] <= hi):
                    continue
                tot += 1
                if words[i] == words[i + lag]:
                    hit += 1
        print(f"  {name:20s} {100*hit/tot:6.3f}%   (n={tot})")


if __name__ == "__main__":
    main()
