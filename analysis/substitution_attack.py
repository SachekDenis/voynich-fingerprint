"""Hill-climbing attack on monoalphabetic substitution, with a control experiment.

Control: a real language encrypted with a random simple substitution must be broken
by the solver.  Then the same solver is pointed at Voynichese.  Comparing the two
separates "the attack does not work" from "the hypothesis is wrong".
"""
import os
import random
import re
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def load_letters(path, limit=200000):
    """Read the FORM column (field 2) of a CoNLL-U file; letters only."""
    from refstats import tok_from_conllu
    return tok_from_conllu(path, limit=limit)


def alphabet_of(words):
    return sorted({c for w in words for c in w})


def build_model(words, alpha):
    idx = {c: i for i, c in enumerate(alpha)}
    A = len(alpha)
    flat = np.full(sum(len(w) for w in words) + len(words), A, dtype=np.int16)  # A = word separator
    pos = 0
    for w in words:
        for c in w:
            flat[pos] = idx[c]
            pos += 1
        flat[pos] = A
        pos += 1
    # quadgram counts
    counts = np.zeros((A + 1, A + 1, A + 1, A + 1), dtype=np.float64)
    a, b, c, d = flat[:-3], flat[1:-2], flat[2:-1], flat[3:]
    np.add.at(counts, (a, b, c, d), 1.0)
    counts += 0.1  # smoothing
    logp = np.log(counts / counts.sum())
    return idx, flat, logp


def score(flat, logp):
    return logp[flat[:-3], flat[1:-2], flat[2:-1], flat[3:]].sum()


def attack(ct_words, ct_alpha, logp, pt_alpha, iters=60000, restarts=3, seed=0):
    """Recover a mapping ct_alpha -> pt_alpha by hill climbing; returns best mapping and score."""
    A = len(pt_alpha)
    ct_map = {c: i for i, c in enumerate(ct_alpha)}
    # represent ciphertext words already in cipher-alphabet indices
    seq = []
    for w in ct_words:
        seq.extend(ct_map[c] for c in w)
        seq.append(A)
    base = np.array(seq, dtype=np.int16)

    best_overall = None
    rng = random.Random(seed)
    for r in range(restarts):
        perm = list(range(A))
        rng.shuffle(perm)
        perm = np.array(perm + [A], dtype=np.int16)  # separator maps to itself
        cur = score(perm[base], logp)
        if best_overall is None or cur > best_overall[0]:
            best_overall = (cur, perm.copy())
        for it in range(iters):
            i, j = rng.randrange(A), rng.randrange(A)
            if i == j:
                continue
            perm[i], perm[j] = perm[j], perm[i]
            new = score(perm[base], logp)
            if new > cur:
                cur = new
                if cur > best_overall[0]:
                    best_overall = (cur, perm.copy())
            else:
                perm[i], perm[j] = perm[j], perm[i]
    return best_overall


def word_accuracy(ct_words, mapping, pt_words_set, true_map=None):
    """Fraction of ciphertext words decoded to a correct plaintext word."""
    return None


def decode_words(ct_words, ct_alpha, mapping_arr, pt_alpha):
    ct_map = {c: i for i, c in enumerate(ct_alpha)}
    out = []
    for w in ct_words:
        out.append("".join(pt_alpha[mapping_arr[ct_map[c]]] for c in w))
    return out


def main():
    # limit is a token count here, not a character count
    latin = load_letters(os.path.join(ROOT, "data", "ref", "latin.conllu"),
                         limit=26000)
    pt_alpha = alphabet_of(latin)
    print(f"Latin alphabet ({len(pt_alpha)}): {''.join(pt_alpha)}")

    lm_words = latin[:20000]       # language model
    target = latin[20000:26000]    # held-out attack target
    _, _, logp = build_model(lm_words, pt_alpha)
    print(f"Target plaintext: {len(target)} words, {sum(map(len,target))} chars")

    rng = random.Random(42)

    # ---------- CONTROL: random monoalphabetic substitution of Latin ----------
    perm_true = list(range(len(pt_alpha)))
    rng.shuffle(perm_true)
    ct_alpha = pt_alpha
    inv = {pt_alpha[i]: pt_alpha[perm_true[i]] for i in range(len(pt_alpha))}
    ct_words = ["".join(inv[c] for c in w) for w in target]

    print("\n[CONTROL] attacking a random substitution of Latin ...")
    sc, mapping = attack(ct_words, ct_alpha, logp, pt_alpha, iters=20000, restarts=4, seed=1)
    dec = decode_words(ct_words, ct_alpha, mapping, pt_alpha)
    truth = target
    exact = sum(1 for a, b in zip(dec, truth) if a == b)
    print(f"  solver score {sc:.0f}; words decoded exactly: {exact}/{len(truth)} "
          f"= {100*exact/len(truth):.1f}%")
    print(f"  sample plaintext : {' '.join(truth[:12])}")
    print(f"  sample recovered : {' '.join(dec[:12])}")

    # ---------- TEST: the real Voynichese ----------
    vms = [w[4] for w in V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt"))]
    v_alpha = alphabet_of(vms)
    print(f"\nVoynich alphabet ({len(v_alpha)}): {''.join(v_alpha)}")
    # restrict to the first 6000 words for a comparable run
    v_target = vms[:6000]
    print(f"[TEST] attacking Voynichese: {len(v_target)} words, "
          f"{sum(map(len,v_target))} chars")
    sc2, mapping2 = attack(v_target, v_alpha, logp, pt_alpha, iters=20000, restarts=4, seed=1)
    dec2 = decode_words(v_target, v_alpha, mapping2, pt_alpha)
    print(f"  solver score {sc2:.0f}")
    print(f"  sample decoded   : {' '.join(dec2[:16])}")

    # ---------- Baselines for a fair comparison ----------
    n1 = sum(len(w) + 1 for w in ct_words)
    n2 = sum(len(w) + 1 for w in v_target)

    def score_per_char(words, alpha, mapping_arr):
        A = len(pt_alpha)
        m = {c: i for i, c in enumerate(alpha)}
        seq = []
        for w in words:
            seq.extend(m[c] for c in w)
            seq.append(A)
        arr = np.array(seq, dtype=np.int16)
        return score(mapping_arr[arr], logp) / len(seq)

    ident = np.array(list(range(len(pt_alpha))) + [len(pt_alpha)], dtype=np.int16)
    base_plain = score_per_char(target, pt_alpha, ident)          # untouched Latin
    random.seed(7)
    A = len(pt_alpha)
    rnd_map = np.arange(A + 1, dtype=np.int16)
    rnd_perm = list(range(A))
    random.shuffle(rnd_perm)
    rnd_map[:len(v_alpha)] = rnd_perm[:len(v_alpha)]
    base_random = score_per_char(v_target, v_alpha, rnd_map)

    print("\n  ---- score per character (higher = closer to real Latin) ----")
    print(f"  Latin plaintext (reference ceiling) : {base_plain:8.3f}")
    print(f"  control   substitution, after attack: {sc/n1:8.3f}")
    print(f"  Voynichese, after attack            : {sc2/n2:8.3f}")
    print(f"  Voynichese, random mapping (floor)  : {base_random:8.3f}")


if __name__ == "__main__":
    main()
