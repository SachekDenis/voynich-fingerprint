"""A generative model that reproduces the measured characteristics of Voynichese.

Architecture (all parameters fitted from a training split, no access to the test split):
  1. BPE inventory  -> the "syllable table"
  2. bigram chain over table entries, with BOS/EOS
  3. cross-word coupling: first entry conditioned on the previous word's last entry
  4. self-citation layer: with probability p, copy a recent word and mutate it
     (this is what produces Zipf, the word families, and the hapax structure)
  5. paragraph-initial gallows emulation

The point is NOT to resample the original text. Vocabulary, Table, and transitions are
learned; the output words are recombinations, and a large share are unattested.
"""
import os
import random
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOS = "<"
EOS = ">"


# --------------------------------------------------------------------------
# BPE: learn the "syllable table"
# --------------------------------------------------------------------------

def learn_bpe(word_counts, merges=140):
    vocab = {w: list(w) for w in word_counts}
    ops = []
    for _ in range(merges):
        pairs = Counter()
        for w, syms in vocab.items():
            c = word_counts[w]
            for a, b in zip(syms, syms[1:]):
                pairs[(a, b)] += c
        if not pairs:
            break
        best = max(pairs.items(), key=lambda kv: (kv[1], kv[0]))[0]
        ops.append(best)
        new = {}
        for w, syms in vocab.items():
            out, i = [], 0
            while i < len(syms):
                if i < len(syms) - 1 and (syms[i], syms[i + 1]) == best:
                    out.append(syms[i] + syms[i + 1])
                    i += 2
                else:
                    out.append(syms[i])
                    i += 1
            new[w] = out
        vocab = new
    return ops


def apply_bpe(word, ops):
    rank = {op: i for i, op in enumerate(ops)}
    syms = list(word)
    while len(syms) > 1:
        cand, best = None, None
        for i in range(len(syms) - 1):
            r = rank.get((syms[i], syms[i + 1]))
            if r is not None and (best is None or r < best):
                best, cand = r, i
        if cand is None:
            break
        syms = syms[:cand] + [syms[cand] + syms[cand + 1]] + syms[cand + 2:]
    return syms


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------

class VoynichModel:
    def __init__(self, words, merges=140):
        self.wc = Counter(words)
        self.ops = learn_bpe(self.wc, merges)
        self.seqs = {w: apply_bpe(w, self.ops) for w in self.wc}
        self._fit()

    def _fit(self):
        # unit inventory ordered by frequency
        unit_freq = Counter()
        for w, syms in self.seqs.items():
            for s in syms:
                unit_freq[s] += self.wc[w]
        self.units = [u for u, _ in unit_freq.most_common()]

        # within-word transitions, BOS/EOS included
        self.bigram = defaultdict(Counter)
        self.occur = Counter()        # how often each unit occurs at all
        self.end_count = Counter()    # how often each unit is word-final
        self.first = Counter()        # first unit of a word
        self.cross = defaultdict(Counter)  # P(first unit | previous word's last unit)
        self.start_gallows = Counter()     # first unit of a paragraph-initial word

        prev_last = BOS
        prev_para_end = True
        for w, n in self.wc.items():
            syms = self.seqs[w]
            if not syms:
                continue
            self.first[syms[0]] += n
            self.bigram[BOS][syms[0]] += n
            for a, b in zip(syms, syms[1:]):
                self.bigram[a][b] += n
            for u in syms:
                self.occur[u] += n
            self.end_count[syms[-1]] += n
            self.cross[prev_last][syms[0]] += n
            prev_last = syms[-1]

        # P(EOS | u) = P(u is word-final | u occurs)
        self.p_end = {u: self.end_count[u] / self.occur[u] for u in self.occur}
        self.p_bigram = {k: self._norm(c) for k, c in self.bigram.items()}
        self.p_first = self._norm(self.first)
        self.p_cross = {k: self._norm(c) for k, c in self.cross.items()}
        # cross[BOS] would otherwise be degenerate (it only ever saw the first type);
        # a document starts like any word, so use the word-initial distribution.
        self.p_cross[BOS] = self.p_first

        self.units_sorted = self.units
        self.total_words = sum(self.wc.values())

        # token-weighted word-length distribution (used to steer generation)
        lc = Counter()
        for w, n in self.wc.items():
            lc[len(w)] += n
        tot = sum(lc.values())
        self.len_dist = {k: v / tot for k, v in lc.items()}

        self.prop_len_dist = None
        self.p_final = self._norm(self.end_count)
        self._len_keys = [k for k, v in sorted(self.len_dist.items())]
        self._len_wts = [self.len_dist[k] for k in self._len_keys]

    def calibrate(self, n=30000, seed=0):
        """Measure the chain's own length distribution in the exact generation regime.

        Length control is importance reweighting, so the proposal has to be measured
        with the same context dependency the generator actually runs under
        (first unit conditioned on the previous word's last unit).
        """
        rng = random.Random(seed)
        prev_last = BOS
        prop = Counter()
        for _ in range(n):
            w = self.sample_word(prev_last, rng)
            prop[len(w)] += 1
            syms = apply_bpe(w, self.ops)
            if syms:
                prev_last = syms[-1]
        tot = sum(prop.values())
        self.prop_len_dist = {k: v / tot for k, v in prop.items()}
        return self.prop_len_dist

    @staticmethod
    def _norm(counter):
        tot = sum(counter.values())
        return {k: v / tot for k, v in counter.items()}

    # ---- sampling helpers -------------------------------------------------

    def _pick(self, dist, rng):
        r = rng.random()
        acc = 0.0
        for k, p in dist.items():
            acc += p
            if r <= acc:
                return k
        return next(iter(dist))

    def sample_word(self, prev_last, rng, bias_len=None):
        syms = []
        u = self._pick(self.p_cross.get(prev_last, self.p_first), rng)
        syms.append(u)
        while True:
            if rng.random() < self.p_end.get(u, 0.5):
                break
            nxt = self.p_bigram.get(u)
            if not nxt:
                break
            u = self._pick(nxt, rng)
            syms.append(u)
            if len(syms) > 8:
                break
        return "".join(syms)

    def sample_word_matched(self, prev_last, rng, tries=60):
        """Sample from the chain, reweighted so the word-length distribution matches."""
        if self.prop_len_dist is None:
            self.calibrate()
        best, best_w = None, -1.0
        for _ in range(tries):
            w = self.sample_word(prev_last, rng)
            L = len(w)
            p_t = self.len_dist.get(L, 1e-9)
            p_p = self.prop_len_dist.get(L, 1e-9)
            wgt = p_t / p_p
            if wgt >= 1.0:
                return w
            if rng.random() < wgt:
                return w
            if wgt > best_w:
                best, best_w = w, wgt
        return best if best is not None else self.sample_word(prev_last, rng)

    def sample_word_of_length(self, L, prev_last, rng):
        """Build a word of exactly L characters by drawing table entries that fit."""
        syms = []
        rem = L
        prev = BOS
        dist = self.p_cross.get(prev_last, self.p_first)
        while rem > 0:
            base = dist if prev is BOS else self.p_bigram.get(prev, self.p_first)
            cand = {u: p for u, p in base.items() if 0 < len(u) <= rem}
            if not cand:
                singles = {u: p for u, p in self.p_first.items() if len(u) == 1}
                cand = singles if singles else {"o": 1.0}
            u = self._pick(cand, rng)
            syms.append(u)
            rem -= len(u)
            prev = u
        return "".join(syms)

    def sample_word_v4(self, prev_last, rng):
        """Slot-structured: [onset + middle][final unit].

        The final unit is drawn from the real word-final unit distribution, so the
        ending statistics (final-y ~40%, top-5 finals ~91%) are exact; the middle is
        filled by the chain to hit the sampled word length.
        """
        L = rng.choices(self._len_keys, weights=self._len_wts, k=1)[0]
        fc = {u: p for u, p in self.p_final.items() if len(u) <= L}
        if not fc:
            fc = self.p_final
        E = self._pick(fc, rng)
        rem = L - len(E)
        syms = []
        prev = BOS
        dist = self.p_cross.get(prev_last, self.p_first)
        while rem > 0:
            base = dist if prev is BOS else self.p_bigram.get(prev, self.p_first)
            cand = {u: p for u, p in base.items() if 0 < len(u) <= rem}
            if not cand:
                cand = {u: p for u, p in self.p_first.items() if len(u) <= rem}
            if not cand:
                break
            weighted = {}
            for u, p in cand.items():
                if len(u) == rem:  # this unit would close the stem: must lead into E
                    q = self.p_bigram.get(u, {}).get(E, 1e-3)
                    weighted[u] = p * q
                else:
                    weighted[u] = p
            u = self._pick(weighted, rng)
            syms.append(u)
            rem -= len(u)
            prev = u
        return "".join(syms) + E

    def mutate(self, word, rng):
        syms = apply_bpe(word, self.ops)
        if not syms:
            return word
        op = rng.random()
        i = rng.randrange(len(syms))
        if op < 0.55 and len(syms) > 1:
            # swap a unit for a plausible neighbour in the table
            nb = self.p_bigram.get(syms[i])
            if nb:
                syms[i] = self._pick(nb, rng)
        elif op < 0.78:
            nb = self.p_bigram.get(syms[i])
            if nb:
                syms.insert(i + 1, self._pick(nb, rng))
        elif len(syms) > 1:
            del syms[i]
        return "".join(syms)


# --------------------------------------------------------------------------
# Text generation
# --------------------------------------------------------------------------

def generate(model, n_words, seed=1, p_copy=0.35, buffer_size=600,
             p_paragraph=0.012, gallows=("t", "k", "p", "f"), matched=False):
    rng = random.Random(seed)
    out = []
    buf = []
    prev_last = BOS
    draw = model.sample_word_matched if matched else model.sample_word
    for i in range(n_words):
        paragraph_start = (i == 0) or (rng.random() < p_paragraph)
        if buf and rng.random() < p_copy:
            src = buf[rng.randrange(len(buf))]
            w = model.mutate(src, rng)
            if not w or w == src:
                w = draw(prev_last, rng)
        else:
            w = draw(prev_last, rng)
        if paragraph_start and gallows and rng.random() < 0.75:
            g = rng.choice(gallows)
            if not any(w.startswith(x) for x in ("t", "k", "p", "f")):
                w = g + w
        out.append(w)
        buf.append(w)
        if len(buf) > buffer_size:
            buf.pop(0)
        prev_last = apply_bpe(w, model.ops)[-1]
    return out


def generate_v3(model, n_words, seed=1, p_copy=0.10, p_blend=0.35, buffer_size=800,
                p_paragraph=0.012, gallows=("t", "k", "p", "f"), lengths=None, slot=True):
    """Length-explicit generation: pick a word length from the table, then fill it."""
    rng = random.Random(seed)
    lens = list(lengths) if lengths else [k for k, v in sorted(model.len_dist.items())]
    wts = [model.len_dist[k] for k in lens]
    out, buf = [], []
    prev_last = BOS
    for i in range(n_words):
        paragraph_start = (i == 0) or (rng.random() < p_paragraph)
        w = None
        if buf and rng.random() < p_copy:
            a = buf[rng.randrange(len(buf))]
            if rng.random() < p_blend and len(buf) > 1:
                b = buf[rng.randrange(len(buf))]
                sa, sb = apply_bpe(a, model.ops), apply_bpe(b, model.ops)
                if len(sa) > 1 and len(sb) > 1:
                    k = rng.randrange(1, len(sa))
                    m = rng.randrange(1, len(sb))
                    w = "".join(sa[:k] + sb[len(sb) - m:])
            if not w:
                w = model.mutate(a, rng)
            if not w:
                w = None
        if not w:
            w = model.sample_word_v4(prev_last, rng) if slot else model.sample_word_of_length(
                rng.choices(lens, weights=wts, k=1)[0], prev_last, rng)
        if paragraph_start and gallows and rng.random() < 0.75:
            if not any(w.startswith(x) for x in ("t", "k", "p", "f")):
                w = rng.choice(gallows) + w
        out.append(w)
        buf.append(w)
        if len(buf) > buffer_size:
            buf.pop(0)
        syms = apply_bpe(w, model.ops)
        prev_last = syms[-1] if syms else BOS
    return out


def generate_v2(model, n_words, seed=1, p_copy=0.12, p_blend=0.35, buffer_size=800,
                p_paragraph=0.012, gallows=("t", "k", "p", "f"), matched=True):
    """Adds a blend operator: novel words built from two buffered words, which recur."""
    rng = random.Random(seed)
    out = []
    buf = []
    prev_last = BOS
    draw = model.sample_word_matched if matched else model.sample_word
    for i in range(n_words):
        paragraph_start = (i == 0) or (rng.random() < p_paragraph)
        w = None
        if buf and rng.random() < p_copy:
            a = buf[rng.randrange(len(buf))]
            if rng.random() < p_blend and len(buf) > 1:
                b = buf[rng.randrange(len(buf))]
                sa, sb = apply_bpe(a, model.ops), apply_bpe(b, model.ops)
                if len(sa) > 1 and len(sb) > 1:
                    k = rng.randrange(1, len(sa))
                    m = rng.randrange(1, len(sb))
                    w = "".join(sa[:k] + sb[len(sb) - m:])
            if not w:
                w = model.mutate(a, rng)
            if not w or w == a:
                w = draw(prev_last, rng)
        else:
            w = draw(prev_last, rng)
        if paragraph_start and gallows and rng.random() < 0.75:
            if not any(w.startswith(x) for x in ("t", "k", "p", "f")):
                w = rng.choice(gallows) + w
        out.append(w)
        buf.append(w)
        if len(buf) > buffer_size:
            buf.pop(0)
        prev_last = apply_bpe(w, model.ops)[-1]
    return out


def main():
    words = [w[4] for w in V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt"))]
    model = VoynichModel(words)
    print(f"BPE table size: {len(model.units)} units")
    print("largest units:", model.units[:18])
    gen = generate(model, len(words), seed=1)
    print("sample:", " ".join(gen[:40]))


if __name__ == "__main__":
    main()
