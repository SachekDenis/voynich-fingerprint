"""Final generator: reproduces the measured characteristics of Voynichese.

Components (each addresses a specific measured property):
  1. BPE inventory        -> the syllable table; sets the character-entropy scale
  2. bigram chain         -> word-internal structure, the rigid onset/coda slots
  3. cross-word coupling  -> first entry conditioned on the previous word's last entry
  4. dual reweighting     -> sample is reweighted on (word length x final entry),
                             which is what aligns length distribution and endings
  5. self-citation        -> light copy+mutation of recent output; tunes vocabulary size,
                             Zipf slope and the hapax share

Fit on a training split; all reported numbers are against the held-out split.
"""
import os
import random
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from voynich_generator import VoynichModel, apply_bpe, BOS
from tier2_metrics import GALLOWS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ArtGenerator:
    def __init__(self, train_words, merges=140):
        self.m = VoynichModel(train_words, merges=merges)
        by_len = defaultdict(Counter)
        lenc = Counter()
        for w, n in self.m.wc.items():
            syms = self.m.seqs[w]
            by_len[len(w)][syms[-1]] += n
            lenc[len(w)] += n
        tot = sum(lenc.values())
        self.tgt_len = {k: v / tot for k, v in lenc.items()}
        self.tgt_fin = {L: {e: c / sum(cc.values()) for e, c in cc.items()}
                        for L, cc in by_len.items()}

    def calibrate(self, n=60000, seed=0):
        rng = random.Random(seed)
        prev, pc, pin = BOS, Counter(), defaultdict(Counter)
        for _ in range(n):
            w = self.m.sample_word(prev, rng)
            syms = apply_bpe(w, self.m.ops)
            L = len(w)
            pc[L] += 1
            pin[L][syms[-1] if syms else ""] += 1
            prev = syms[-1] if syms else BOS
        t = sum(pc.values())
        self.prop_len = {k: v / t for k, v in pc.items()}
        self.prop_fin = {L: {e: c / sum(cc.values()) for e, c in cc.items()}
                         for L, cc in pin.items()}

    def calibrate_proposal(self, n=60000, seed=0):
        """Measure the length/ending distribution of the sampler actually used.

        The reweighting in _draw_onset is a ratio target/proposal, so the proposal has
        to be measured with the same onset-conditioned walk the generator runs -- not
        from the plain chain, which is what the earlier version did.
        """
        self._no_weight = True
        rng = random.Random(seed)
        prev_word = ""
        pc, pin = Counter(), defaultdict(Counter)
        for _ in range(n):
            w = self._draw_onset(prev_word, rng)
            syms = apply_bpe(w, self.m.ops)
            L = len(w)
            pc[L] += 1
            pin[L][syms[-1] if syms else ""] += 1
            prev_word = w
        self._no_weight = False
        t = sum(pc.values())
        self.prop_len = {k: v / t for k, v in pc.items()}
        self.prop_fin = {L: {e: c / sum(cc.values()) for e, c in cc.items()}
                         for L, cc in pin.items()}
        return self.prop_len

    def calibrate_onset(self, words):
        """Target and proposal distributions over onset classes, for reweighting."""
        from tier2_metrics import onset as onset_of
        tgt = Counter(onset_of(w) for w in words)
        self.tgt_onset = {k: v / sum(tgt.values()) for k, v in tgt.items()}
        prop = Counter()
        rng = random.Random(0)
        prev = BOS
        for _ in range(40000):
            w = self.m.sample_word(prev, rng)
            prop[onset_of(w)] += 1
            syms = apply_bpe(w, self.m.ops)
            prev = syms[-1] if syms else BOS
        self.prop_onset = {k: v / sum(prop.values()) for k, v in prop.items()}

    def calibrate_cross_onset(self, words):
        """P(onset class | last character of the previous word), from real text.

        Currier's observation (words ending in y are followed far more often by
        qo- words) is a conditional of exactly this form; modelling it directly
        sets both the onset marginal and the cross-word dependency.
        """
        from tier2_metrics import onset as onset_of
        joint = defaultdict(Counter)
        marg = Counter()
        for a, b in zip(words, words[1:]):
            joint[a[-1]][onset_of(b)] += 1
            marg[a[-1]] += 1
        self.cross_onset = {c: {o: n / sum(cc.values()) for o, n in cc.items()}
                            for c, cc in joint.items()}
        self.onset_marginal = Counter(onset_of(w) for w in words)
        tot = sum(self.onset_marginal.values())
        self.onset_marginal = {k: v / tot for k, v in self.onset_marginal.items()}
        # units grouped by the onset class they produce, with their frequencies
        ufreq = Counter()
        for w, n in self.m.wc.items():
            for u in self.m.seqs[w]:
                ufreq[u] += n
        self.units_by_onset = defaultdict(list)
        for u in self.m.units:
            self.units_by_onset[onset_of(u)].append((u, ufreq[u]))
        self.units_by_onset_w = {
            O: ([u for u, _ in lst], [c for _, c in lst])
            for O, lst in self.units_by_onset.items()}
        self._inv_units = [u for u, _ in ufreq.most_common()]
        self._inv_wts = [c for _, c in ufreq.most_common()]
        # The second shape of a word, conditioned on the onset class, not only on the
        # last letter of the first shape. Without this the walk forgets within one step
        # what kind of word it is writing, and the missing within-word dependence is
        # concentrated exactly there: 86 % of the deficit sits in the front half of the
        # word, +7.4 sd at character distance 3 when the pair starts at position 0 or 1.
        link2 = defaultdict(lambda: defaultdict(Counter))
        for w, n in self.m.wc.items():
            syms = self.m.seqs[w]
            if len(syms) < 2:
                continue
            link2[onset_of(syms[0])][syms[0][-1]][syms[1]] += n
        self.link2_by_onset = {O: {c: {u: v / sum(cc.values()) for u, v in cc.items()}
                                   for c, cc in d.items()}
                               for O, d in link2.items()}

    def calibrate_lengths(self, doc):
        """Length/ending targets measured on NON-line-final words.

        The line-fill mechanism shortens words near the margin on top of the base
        distribution, so the base target must be conditioned the same way -- otherwise
        the shortening is counted twice and the corpus mean comes out too low.
        """
        nonfinal = [w for p in doc for ln in p for w in ln[:-1]] or                    [w for p in doc for ln in p for w in ln]
        by_len = defaultdict(Counter)
        lenc = Counter()
        for w, n in Counter(nonfinal).items():
            by_len[len(w)][apply_bpe(w, self.m.ops)[-1]] += n
            lenc[len(w)] += n
        tot = sum(lenc.values())
        self.tgt_len = {k: v / tot for k, v in lenc.items()}
        self.tgt_fin = {L: {e: c / sum(cc.values()) for e, c in cc.items()}
                        for L, cc in by_len.items()}

    def calibrate_pairs(self, words, min_count=1):
        """Formulaic word pairs: what tends to follow a given word in real text."""
        nxt = defaultdict(Counter)
        for a, b in zip(words, words[1:]):
            nxt[a][b] += 1
        self.pair_next = {w: ([k for k, _ in c.most_common()], [v for _, v in c.most_common()])
                          for w, c in nxt.items() if sum(c.values()) >= min_count}

    def calibrate_common(self, words, min_count=15):
        """Stock of high-frequency words, with their frequencies, grouped by onset class."""
        c = Counter(words)
        self.common = [(w, n) for w, n in c.items() if n >= min_count]
        self.common_by_onset = defaultdict(list)
        from tier2_metrics import onset as onset_of
        for w, n in self.common:
            self.common_by_onset[onset_of(w)].append((w, n))

    fit_penalty = 0.5

    def _invent(self, rng):
        """A word assembled freely from the syllable inventory (no chain walk)."""
        n = rng.choice((1, 2, 2, 3, 3, 4))
        return "".join(rng.choices(self._inv_units, weights=self._inv_wts, k=1)[0]
                       for _ in range(n))

    def _draw_onset(self, prev_word, rng, tries=200, recent=None,
                    recency_alpha=0.0, gallows_scale=1.0, p_reuse=0.0, p_invent=0.0,
                    room=None, p_inword=0.0, onset2=False, p_raw=0.0, endfix=False):
        """Draw a word whose onset class is sampled from the real cross-word table."""
        from tier2_metrics import onset as onset_of
        if p_invent and rng.random() < p_invent:
            w = self._invent(rng)
            L = len(w)
            syms = apply_bpe(w, self.m.ops)
            E = syms[-1] if syms else ""
            wgt = (self.tgt_len.get(L, 1e-9) / self.prop_len.get(L, 1e-9)) * \
                  (self.tgt_fin.get(L, {}).get(E, 1e-9) / self.prop_fin.get(L, {}).get(E, 1e-9))
            if wgt >= 1.0 or rng.random() < wgt:
                return w
        last = prev_word[-1] if prev_word else ""
        dist = self.cross_onset.get(last) or self.onset_marginal
        keys = list(dist)
        wts = [dist[k] for k in keys]
        # Draw the onset class ONCE. Resampling it inside the rejection loop would
        # bias the accepted onset distribution by the length/ending weight, which is
        # what was flattening final-y and the length tails.
        O = rng.choices(keys, weights=wts, k=1)[0]
        if p_reuse and getattr(self, "common", None) and rng.random() < p_reuse:
            pool = self.common_by_onset.get(O) or self.common
            ws, cs = zip(*pool)
            return rng.choices(ws, weights=cs, k=1)[0]
        if O not in self.units_by_onset_w:
            O = max(self.units_by_onset_w, key=lambda k: len(self.units_by_onset_w[k][0]))

        def walk():
            us, cs = self.units_by_onset_w[O]
            u0 = rng.choices(us, weights=cs, k=1)[0]
            out = [u0]
            second = onset2
            while True:
                if rng.random() < self.m.p_end.get(u0, 0.5):
                    break
                if p_inword and len(out) >= 2 and rng.random() < p_inword:
                    # the writer puts down a shape he has already used in this word,
                    # which is what makes daiin, qokeedy and oteey what they are: the
                    # repetition is inside the word, not between words. This is the only
                    # mechanism that reaches character distances of 4-6 inside a word;
                    # nothing at the word level can, because the pair never crosses a
                    # word boundary.
                    u0 = out[rng.randrange(len(out) - 1)]
                    out.append(u0)
                    if len(out) > 8:
                        break
                    continue
                if second:
                    second = False
                    tab = self.link2_by_onset.get(O, {}).get(u0[-1])
                    if tab:
                        u0 = rng.choices(list(tab), weights=list(tab.values()), k=1)[0]
                        out.append(u0)
                        if len(out) > 8:
                            break
                        continue
                nxt = self.m.p_bigram.get(u0)
                if not nxt:
                    break
                u0 = self.m._pick(nxt, rng)
                out.append(u0)
                if len(out) > 8:
                    break
            return out

        if endfix:
            # Accept on LENGTH only, then repair the ending by swapping the last shape.
            # The standard reweighting multiplies a length weight by an ending weight and
            # re-rolls the whole word when the product is small, which correlates the
            # acceptance with the *front* of the word as well as its end. Accepting on
            # length alone and editing only the last shape leaves the front untouched --
            # the front is where 86 % of the missing within-word dependence sits.
            best, bw, syms = None, -1.0, walk()
            for _ in range(max(1, tries // 4)):
                syms = walk()
                wgt = self.tgt_len.get(len(syms and "".join(syms)), 1e-9) /                       self.prop_len.get(len(syms and "".join(syms)), 1e-9)
                if wgt >= 1.0 or rng.random() < wgt:
                    break
            if len(syms) > 1:
                L = len("".join(syms))
                tab = self.tgt_fin.get(L)
                if tab:
                    cur = syms[-1]
                    p_ok = tab.get(cur, 1e-9)
                    if rng.random() > min(1.0, p_ok * 4):
                        keys = list(tab)
                        wts = [tab[k] for k in keys]
                        syms = syms[:-1] + [rng.choices(keys, weights=wts, k=1)[0]]
            return "".join(syms)
        if p_raw and rng.random() < p_raw:
            # The writer puts a word down without fitting it to a length he had in mind.
            # Every other path through this function accepts a word only if its (length,
            # final shape) matches the real joint distribution, and that acceptance is
            # what flattens the *front* of the word: it removes more of the dependence
            # between the opening shapes than the raw chain has too much of. A small
            # admixture of unchecked words carries the front-half dependence back to the
            # manuscript's value at a cost of 0.01 in length-distribution TV.
            return "".join(walk())
        best, bw, syms = None, -1.0, walk()
        if getattr(self, "_no_weight", False):
            return "".join(syms)
        for _ in range(tries):
            self.trials = getattr(self, "trials", 0) + 1
            syms = walk()
            w = "".join(syms)
            L = len(w)
            E = syms[-1]
            wgt = (self.tgt_len.get(L, 1e-9) / self.prop_len.get(L, 1e-9)) * \
                  (self.tgt_fin.get(L, {}).get(E, 1e-9) / self.prop_fin.get(L, {}).get(E, 1e-9))
            if room is not None and len(w) > room:
                # the scribe prefers a word that reaches the margin without overrunning it,
                # but the preference is mild: in the manuscript the last word of a line is
                # only ~0.34 characters shorter than average, not a hard fit
                wgt *= self.fit_penalty if len(w) <= room + 2 else self.fit_penalty * 0.4
            if gallows_scale != 1.0 and any(w.startswith(x) for x in GALLOWS):
                wgt *= gallows_scale
            if recent and recency_alpha and w != prev_word:
                c = recent.get(w, 0)
                if c:
                    wgt /= (1.0 + recency_alpha * c)
            if wgt >= 1.0 or rng.random() < wgt:
                return w
            if wgt > bw:
                best, bw = w, wgt
        return best if best is not None else "".join(syms)

    def _draw(self, prev, rng, tries=200, use_onset=True, recent=None,
              recency_alpha=0.0, gallows_scale=1.0):
        from tier2_metrics import onset as onset_of
        best, bw = None, -1.0
        for _ in range(tries):
            w = self.m.sample_word(prev, rng)
            syms = apply_bpe(w, self.m.ops)
            L = len(w)
            E = syms[-1] if syms else ""
            wgt = (self.tgt_len.get(L, 1e-9) / self.prop_len.get(L, 1e-9)) * \
                  (self.tgt_fin.get(L, {}).get(E, 1e-9) / self.prop_fin.get(L, {}).get(E, 1e-9))
            if use_onset and getattr(self, "tgt_onset", None):
                o = onset_of(w)
                wgt *= (self.tgt_onset.get(o, 1e-9) / self.prop_onset.get(o, 1e-9)) ** 2
            if gallows_scale != 1.0 and any(w.startswith(x) for x in GALLOWS):
                wgt *= gallows_scale
            if recent and recency_alpha:
                c = recent.get(w, 0)
                if c:
                    wgt /= (1.0 + recency_alpha * c)
            if wgt >= 1.0 or rng.random() < wgt:
                return w
            if wgt > bw:
                best, bw = w, wgt
        return best

    def text(self, n_words, seed=1, p_copy=0.05, p_paragraph=0.012,
             gallows=("t", "k", "p", "f"), buffer_size=700):
        rng = random.Random(seed)
        prev, out, buf = BOS, [], []
        for i in range(n_words):
            para = (i == 0) or (rng.random() < p_paragraph)
            w = None
            if buf and rng.random() < p_copy:
                a = buf[rng.randrange(len(buf))]
                w = self.m.mutate(a, rng)
            if not w:
                w = self._draw(prev, rng)
            if para and gallows and rng.random() < 0.75:
                if not any(w.startswith(x) for x in gallows):
                    w = rng.choice(gallows) + w
            out.append(w)
            buf.append(w)
            if len(buf) > buffer_size:
                buf.pop(0)
            syms = apply_bpe(w, self.m.ops)
            prev = syms[-1] if syms else BOS
        return out

    def calibrate_layout(self, paras, line_chars=None, para_lines=None,
                         gallows_p=0.0, p_copy=0.05):
        """Learn the layout constants from a real document (list of paragraphs of lines)."""
        mid, fin = [], []
        for p in paras:
            for i, ln in enumerate(p):
                (fin if i == len(p) - 1 else mid).append(sum(len(w) for w in ln))
        # Mid-paragraph lines run to the margin (median ~46 chars); the last line of a
        # paragraph stops early (median ~23). Mixing the two made the generator squeeze
        # words into deliberately-short lines, which is not what the scribe was doing.
        self.mid_line_chars = line_chars or (mid or fin)
        self.final_line_chars = fin or mid
        self.para_line_choices = para_lines or [len(p) for p in paras]
        self.line_gallows_p = gallows_p

    def document(self, n_paragraphs=280, seed=1, p_copy=0.05,
                 gallows=("t", "k", "p", "f"), buffer_size=700, use_onset=True,
                 recency_alpha=0.0, recency_window=120, gallows_scale=1.0,
                 cross_onset=False, p_reuse=0.0, p_invent=0.0, copy_decay=0.0,
                 tries=200, p_repeat=0.0, p_pair=0.0, line_fit=True, p_verbatim=0.0,
                 p_recent=0.0, recent_win=20, p_pool=0.0, pool_size=0,
                 pool_mode="top", p_selfpool=0.0, p_selfmut=0.0, p_inword=0.0,
                 onset2=False, p_raw=0.0, endfix=False):
        """Lay the stream out as paragraphs of filled lines, mirroring the real geometry."""
        rng = random.Random(seed + 4242)
        out_paras = []
        stream_prev = BOS
        prev_word = ""
        buf = []
        recent = Counter()
        recent_q = []
        while len(out_paras) < n_paragraphs:
            n_lines = rng.choice(self.para_line_choices)
            para = []
            # a passage draws on its own working set of forms, which resets hard at the
            # paragraph break -- measured in the manuscript as a repeat rate of 0.88 %
            # inside a paragraph against 0.17 % across the boundary, below chance
            pool = None
            if pool_size and p_pool:
                if pool_mode == "sample":
                    # A passage draws its own working set by sampling the global
                    # frequency distribution, so two passages get *different* sets.
                    # Drawing the same top-N for every passage raises repetition
                    # everywhere, which is why the earlier pool failed: it made the
                    # across-paragraph rate rise too. A sampled pool is a multinomial
                    # perturbation of the global distribution, so within a passage the
                    # repeat rate rises to sum f^2 + (1 - sum f^2)/M while between two
                    # independent passages it stays at sum f^2 -- which is exactly the
                    # manuscript's profile.
                    ws_, cs_ = zip(*self.m.wc.items())
                    pool = rng.choices(ws_, weights=cs_, k=pool_size)
                else:
                    # drawn by frequency, not uniformly: the working set of a passage
                    # is made of the forms the writer uses constantly, not of rare ones
                    ws_, cs_ = zip(*self.m.wc.most_common(pool_size))
                    pool = ws_
            written = []
            for li in range(n_lines):
                last_line = (li == n_lines - 1)
                budget = rng.choice(self.final_line_chars if last_line
                                    else self.mid_line_chars)
                line, used = [], 0
                while True:
                    w = None
                    room = (budget - used) if line_fit else None
                    if (p_selfpool and written and rng.random() < p_selfpool):
                        # the writer reaches back into *this passage* only: his own
                        # words so far. The list is cleared at every paragraph break,
                        # so this lifts repetition inside a passage and leaves the
                        # rate between two passages at the memoryless baseline.
                        # never the word just written: the target profile is measured
                        # at lags 2-6, and drawing the immediate neighbour inflates
                        # 'adjacent identical words' from 21 % to 70 % error for no gain
                        hi = len(written) - 1 if len(written) > 1 else 1
                        w = written[rng.randrange(hi)]
                        if p_selfmut and rng.random() < p_selfmut:
                            # the writer re-uses a word of this passage but not
                            # letter for letter: the same variation a hand puts in
                            w = self.m.mutate(w, rng)
                    if w is None and pool is not None and rng.random() < p_pool:
                        w = pool[rng.randrange(len(pool))]
                    if w is None and p_recent and len(buf) >= 3 and rng.random() < p_recent:
                        # reach back into a flat window of recent words: a scribe reuses
                        # the forms that are still in mind, which lifts the repeat rate
                        # at every lag rather than only for the adjacent word
                        span = min(len(buf), recent_win)
                        w = buf[-1 - rng.randrange(span)]
                    if w is None and p_repeat and prev_word and rng.random() < p_repeat:
                        # a scribe repeating a formula, or copying the same position
                        # in the line just written (Timm's reuse_last)
                        w = prev_word
                    if w is None and p_pair and prev_word in getattr(self, "pair_next", {}):
                        if rng.random() < p_pair:
                            ws, cs = self.pair_next[prev_word]
                            w = rng.choices(ws, weights=cs, k=1)[0]
                    if w is None and buf and rng.random() < p_copy:
                        if copy_decay:
                            # copy from nearby text (scribe works from lines just written)
                            age = min(int(rng.expovariate(1.0 / copy_decay)), len(buf) - 1)
                            a = buf[-1 - age]
                        else:
                            a = buf[rng.randrange(len(buf))]
                        w = a if (p_verbatim and rng.random() < p_verbatim)                             else self.m.mutate(a, rng)
                    if not w:
                        if cross_onset and getattr(self, "cross_onset", None):
                            w = self._draw_onset(prev_word, rng, recent=recent,
                                                 recency_alpha=recency_alpha,
                                                 gallows_scale=gallows_scale,
                                                 p_reuse=p_reuse, p_invent=p_invent, tries=tries, room=room,
                                                 p_inword=p_inword, onset2=onset2,
                                                 p_raw=p_raw, endfix=endfix)
                        else:
                            w = self._draw(stream_prev, rng, use_onset=use_onset,
                                           recent=recent, recency_alpha=recency_alpha,
                                           gallows_scale=gallows_scale)
                    if line and used >= budget:
                        break
                    if not line and rng.random() < self.line_gallows_p:
                        if not any(w.startswith(x) for x in gallows):
                            w = rng.choice(gallows) + w
                    line.append(w)
                    written.append(w)
                    buf.append(w)
                    if len(buf) > buffer_size:
                        buf.pop(0)
                    recent[w] += 1
                    recent_q.append(w)
                    if len(recent_q) > recency_window:
                        old = recent_q.pop(0)
                        recent[old] -= 1
                        if recent[old] <= 0:
                            del recent[old]
                    used += len(w)
                    syms = apply_bpe(w, self.m.ops)
                    stream_prev = syms[-1] if syms else BOS
                    prev_word = w
                if line:
                    para.append(line)
            if para:
                out_paras.append(para)
        return out_paras


def load_train():
    rows = V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt"))
    return [w[4] for w in rows if int(w[0][1:].split("r")[0].split("v")[0]) % 2 == 0]


if __name__ == "__main__":
    rows = V.load_words(os.path.join(ROOT, "data", "IT2a-n.txt"))
    import re
    train = [w[4] for w in rows if int(re.match(r"f?(\d+)", w[0]).group(1)) % 2 == 0]
    from tier2_metrics import load_real_document
    g = ArtGenerator(train)
    g.calibrate()
    g.calibrate_onset(train)
    g.calibrate_layout(load_real_document())
    for para in g.document(3, seed=5)[:3]:
        for ln in para:
            print(" ".join(ln))
        print()
