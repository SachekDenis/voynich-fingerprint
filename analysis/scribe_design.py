"""How small can the manual be?

The computer generator uses 140 BPE units, a 140x140 transition table, a cross-word
onset table and rejection sampling on a joint distribution of length and ending. A
person with a quill cannot carry any of that. This measures what a person CAN carry:

  1. how many syllable forms cover what share of the text,
  2. how much smaller the transition table gets if the next form is conditioned on the
     last LETTER of the current one instead of on the whole form,
  3. whether the length distribution survives without rejection sampling -- i.e. with a
     plain "stop after so many shapes" dice rule.

Everything on the training half only.
"""
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from voynich_generator import VoynichModel, apply_bpe, BOS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def H(counter):
    t = sum(counter.values())
    return -sum((v / t) * math.log2(v / t) for v in counter.values()) if t else 0.0


def cond_H(joint, marg=None):
    """H(Y | X) from a joint table, counts."""
    tot = sum(sum(c.values()) for c in joint.values())
    out = 0.0
    for x, c in joint.items():
        n = sum(c.values())
        out += (n / tot) * H(c)
    return out


def main():
    rows = V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt"))
    tr = [w[4] for w in rows if int(w[0][1:].split("r")[0].split("v")[0]) % 2 == 0]
    te = [w[4] for w in rows if int(w[0][1:].split("r")[0].split("v")[0]) % 2 == 1]
    m = VoynichModel(tr, merges=140)

    uf = Counter()
    for w, n in m.wc.items():
        for u in m.seqs[w]:
            uf[u] += n
    tot = sum(uf.values())
    print(f"syllable forms when learned from text: {len(uf)}")
    cum, marks = 0, []
    for K in (20, 30, 40, 50, 60, 80, 100, 120, 140):
        c = sum(x for _, x in uf.most_common(K))
        marks.append((K, 100 * c / tot))
    print("  coverage of the running text by the K most frequent forms:")
    print("   " + "  ".join(f"K={K}:{v:.0f}%" for K, v in marks))

    # 1. how much of a real word can be spelled with only the top K forms?
    for K in (30, 40, 50, 60, 80):
        top = set(u for u, _ in uf.most_common(K))
        whole = sum(1 for w in te if all(u in top for u in apply_bpe(w, m.ops)))
        chars = sum(1 for w in te for c in w)
        cov = sum(len(w) for w in te if all(u in top for u in apply_bpe(w, m.ops))) / chars
        print(f"  K={K:3d}: {100*whole/len(te):5.1f}% of held-out words writable whole, "
              f"{100*cov:5.1f}% of characters")

    # 2. transition table size: whole form vs last letter
    j_form = defaultdict(Counter)
    j_char = defaultdict(Counter)
    j_first = defaultdict(Counter)
    prev_char = defaultdict(Counter)
    starts = Counter()
    stops = defaultdict(Counter)
    for w, n in m.wc.items():
        syms = m.seqs[w]
        for i, u in enumerate(syms):
            if i == 0:
                starts[u] += n
            else:
                j_form[syms[i - 1]][u] += n
                j_char[syms[i - 1][-1]][u] += n
                prev_char[syms[i - 1][-1]][syms[i][0]] += n
            if i == len(syms) - 1:
                stops[i + 1][u] += n
    print(f"\ntransition tables a scribe must carry:")
    print(f"  H(next form | whole previous form) = {cond_H(j_form):.2f} bits "
          f"({len(j_form)} rows)")
    print(f"  H(next form | last letter)         = {cond_H(j_char):.2f} bits "
          f"({len(j_char)} rows)")
    print(f"  H(first letter of next | last letter) = {cond_H(prev_char):.2f} bits")
    print(f"  H(first form) = {H(starts):.2f} bits over {len(starts)} forms")

    # 3. length without rejection: is "number of forms" enough, or is the ending joint?
    lens = Counter()
    for w, n in m.wc.items():
        lens[len(m.seqs[w])] += n
    print(f"\nforms per word: mean {sum(k*v for k,v in lens.items())/sum(lens.values()):.2f}, "
          f"distribution {dict(sorted(lens.items()))}")
    end_by_len = defaultdict(Counter)
    for w, n in m.wc.items():
        end_by_len[len(m.seqs[w])][m.seqs[w][-1]] += n
    print("  H(final form | number of forms): "
          + ", ".join(f"n={k}:{H(c):.2f}" for k, c in sorted(end_by_len.items())))
    print(f"  H(final form) unconditioned: {H(sum(end_by_len.values(), Counter())):.2f}")

    # 4. cross-word rule in its smallest form: Currier's y -> qo
    print("\nonset class of a word, by the last letter of the previous word:")
    from tier2_metrics import onset
    joint = defaultdict(Counter)
    base = Counter(onset(w) for w in te)
    for a, b in zip(te, te[1:]):
        joint[a[-1]][onset(b)] += 1
    allon = Counter()
    for c, cc in joint.items():
        allon.update(cc)
    classes = [o for o, _ in base.most_common(8)]
    print(f"  {'prev ends':>10s} {'n':>6s} " + " ".join(f"{o:>7s}" for o in classes))
    for c in sorted(joint, key=lambda c: -sum(joint[c].values()))[:8]:
        n = sum(joint[c].values())
        print(f"  {c:>10s} {n:6d} " + " ".join(
            f"{100*joint[c].get(o,0)/n:6.1f}%" for o in classes))
    print(f"  {'(overall)':>10s} {sum(base.values()):6d} " + " ".join(
        f"{100*base.get(o,0)/sum(base.values()):6.1f}%" for o in classes))


if __name__ == "__main__":
    main()
