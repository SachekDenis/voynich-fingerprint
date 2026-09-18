"""The manual: can a person with a quill reproduce the text?

The computer generator reaches the fingerprint by rejection sampling on a joint
(length x ending) distribution and by a 151-row transition table, and needs no other
explanation of the text than those tables. The question here is different: what is the
smallest procedure a PERSON could execute, and how close does it come?

The scribe carries:

  A  a form table      ~60 syllable shapes, most used first. One pen movement each.
  B  openings          14 standard ways to start a word, by the previous word's ending
  C  a link table      21 rows: after writing this letter, the shape that usually follows
  D  length            16 numbers: how many letters the next word has
  E  closings          14 stock endings, chosen for the word's length
  F  carry-over        the last letter of the previous word sets the opening
  G  stock phrases     word pairs he writes together out of habit
  H  page rules        fill the column the drawing leaves; a few lines to a passage;
                       open a line with a tall stroke now and then

Procedure for one word: look at the last letter written (F), write an opening (B),
decide the word's length (D) and its ending (E) and fill the middle (C) until the word
is that size. Occasionally write a word from the same passage again with one shape
changed, and after a word that has a habitual partner, write the partner (G).

Nothing in the procedure is a statistic, and nothing is ever thrown away and re-rolled.
Hyper-parameters are chosen on one half of the training leaves and reported on the
held-out half, so no number here is fitted to the text it is scored against.
"""
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from tier2_metrics import measure_document, onset, GALLOWS
from voynich_generator import VoynichModel
from tune_artgen import split_by_folio, flatten, tier1, err

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START = "^"


def _norm(c):
    t = sum(c.values())
    return {k: v / t for k, v in c.items()} if t else {}


def pick(dist, rng):
    ks = list(dist)
    return rng.choices(ks, weights=[dist[k] for k in ks], k=1)[0]


# ---------------------------------------------------------------------------
# A-G: the manual
# ---------------------------------------------------------------------------

class Manual:
    def __init__(self, train_words, n_forms=60, merges=140, max_body=3,
                 n_open=14, n_close=14, length_cap=12):
        self.m = VoynichModel(train_words, merges=merges)
        self.max_body = max_body
        self.length_cap = length_cap

        uf = Counter()
        for w, n in self.m.wc.items():
            for u in self.m.seqs[w]:
                uf[u] += n
        self.forms = [u for u, _ in uf.most_common(n_forms)]          # A
        self.known = set(self.forms)
        self.fallback = self.forms[0]

        start = defaultdict(Counter)      # B, by onset class
        link = defaultdict(Counter)       # C, by last letter
        coda = defaultdict(Counter)       # E, by word length
        short = defaultdict(Counter)      # words written with a single shape
        lens = Counter()                  # D
        for w, n in self.m.wc.items():
            syms = [s for s in self.m.seqs[w] if s in self.known] or [self.fallback]
            lens[len(w)] += n
            if len(syms) == 1:
                short[min(len(w), 3)][syms[0]] += n
            for i, u in enumerate(syms):
                if i == 0:
                    start[onset(u)][u] += n
                else:
                    link[syms[i - 1][-1]][u] += n
                if i == len(syms) - 1:
                    coda[min(len(w), length_cap)][u] += n
        self.start = {o: _norm(c) for o, c in start.items()}
        self.link = {c: _norm(cc) for c, cc in link.items()}
        self.lens = _norm(lens)
        self.short_by_len = {k: _norm(c) for k, c in short.items()}
        self.coda_form = {k: _norm(c) for k, c in coda.items()}

        # E spoken as letters: a shape table of 60 cannot spell the true last shape of
        # most words, so the closing is carried as letters instead -- -y above all,
        # which closes 40 % of the manuscript's words.
        opens, closes = Counter(), Counter()
        close_by_len = defaultdict(Counter)
        open_by_prev = defaultdict(Counter)
        prev_of = {}
        for a, b in zip(train_words, train_words[1:]):
            prev_of.setdefault(b, a[-1])
        for w, n in self.m.wc.items():
            if len(w) < 4:
                continue
            op = w[:2] if len(w) > 3 else w[:1]
            cl = w[-3:] if len(w) > 5 else (w[-2:] if len(w) > 3 else w[-1:])
            opens[op] += n
            closes[cl] += n
            close_by_len[min(len(w), length_cap)][cl] += n
            open_by_prev[prev_of.get(w, "")][op] += n
        self.open_list = [o for o, _ in opens.most_common(n_open)]
        self.close_list = [c for c, _ in closes.most_common(n_close)]
        self.open_w = _norm(Counter({o: opens[o] for o in self.open_list}))
        self.close_w = _norm(Counter({c: closes[c] for c in self.close_list}))
        self.close_by_len = {}
        for L, c in close_by_len.items():
            keep = Counter({k: v for k, v in c.items() if k in self.close_list})
            self.close_by_len[L] = _norm(keep) if keep else self.close_w
        self.open_by_prev = {}
        for p, c in open_by_prev.items():
            keep = Counter({k: v for k, v in c.items() if k in self.open_list})
            self.open_by_prev[p] = _norm(keep) if keep else self.open_w

        # F: cross-word carry-over, as an onset class table
        cross = defaultdict(Counter)
        for a, b in zip(train_words, train_words[1:]):
            cross[a[-1]][onset(b)] += 1
        self.cross = {c: _norm(cc) for c, cc in cross.items()}
        self.cross_default = _norm(Counter(onset(w) for w in train_words))

        # G: stock phrases
        nxt = defaultdict(Counter)
        for a, b in zip(train_words, train_words[1:]):
            nxt[a][b] += 1
        self.pairs = {w: _norm(c) for w, c in nxt.items() if sum(c.values()) >= 2}

    def opening(self, prev_word, rng):
        row = self.cross.get(prev_word[-1] if prev_word else "", self.cross_default)
        O = pick(row, rng)
        st = self.start.get(O)
        if not st:
            st = self.start[max(self.start, key=lambda k: sum(self.start[k].values()))]
        return pick(st, rng)

    def step(self, word, rng):
        row = self.link.get(word[-1] if word else START)
        return pick(row, rng) if row else None


# ---------------------------------------------------------------------------
# the write
# ---------------------------------------------------------------------------

def as_syms(man, word):
    out, i, order = [], 0, sorted(man.known, key=len, reverse=True)
    while i < len(word):
        for u in order:
            if word.startswith(u, i):
                out.append(u)
                i += len(u)
                break
        else:
            out.append(word[i])
            i += 1
    return out


def write_word(man, prev, rng):
    """Decide the length and the ending, write the opening, fill to size."""
    L = pick(man.lens, rng)
    if L <= 2:
        s = man.short_by_len.get(L) or man.short_by_len.get(1)
        return pick(s, rng) if s else man.opening(prev, rng)
    cl = pick(man.close_by_len.get(min(L, man.length_cap), man.close_w), rng)
    word = man.opening(prev, rng)
    k = 1
    while len(word) + len(cl) < L - 1 and k <= man.max_body + 2:
        nxt = man.step(word, rng)
        if nxt is None or len(word) + len(nxt) + len(cl) > L + 1:
            break
        word += nxt
        k += 1
    return word + cl


def vary(man, word, rng):
    """The same word again with one shape swapped for its usual neighbour.

    Only a swap: inserting or dropping a shape is the obvious way to make the text
    repeat itself, and it was tried -- it doubles the number of one- and two-letter
    words, because the hand that is supposed to be filling a line to a decided length
    keeps making the word shorter instead. A swap leaves the length alone.
    """
    syms = as_syms(man, word)
    if len(syms) < 2:
        return word
    i = rng.randrange(len(syms))
    nxt = man.link.get(syms[i - 1][-1] if i else START)
    if nxt:
        syms[i] = pick(nxt, rng)
    return "".join(syms)


def make_scribe(man, p_pair=0.5, p_reuse=0.1, pool_size=80):
    def write(prev, rng, pool):
        if prev and rng.random() < p_pair:
            row = man.pairs.get(prev)
            if row:
                return pick(row, rng)
        if pool and rng.random() < p_reuse:
            return vary(man, pool[rng.randrange(len(pool))], rng)
        w = write_word(man, prev, rng)
        pool.append(w)
        if len(pool) > pool_size:
            pool.pop(0)
        return w
    return write


def scribe_document(write, n_lines, widths, para_lines, rng, gallows_p=0.10):
    """Lay the words out the way the page is laid out: fill the column the drawing
    leaves, close the line, start a new one, and open a line with a tall stroke
    now and then."""
    out, prev, li = [], "", 0
    while li < n_lines:
        n_in_para = para_lines[rng.randrange(len(para_lines))]
        para, pool = [], []          # the passage owns its forms; nothing older is used
        for _ in range(n_in_para):
            if li >= n_lines:
                break
            budget = widths[rng.randrange(len(widths))]
            line, used, first = [], 0, True
            while True:
                w = write(prev, rng, pool)
                if first and rng.random() < gallows_p:
                    if not any(w.startswith(g) for g in GALLOWS):
                        w = rng.choice(("t", "k", "p", "f")) + w
                if line and used + len(w) > budget:
                    break
                line.append(w)
                used += len(w)
                prev = w
                first = False
                if used >= budget:
                    break
            if line:
                para.append(line)
                li += 1
        if para:
            out.append(para)
    return out


def score(doc, te_doc, te_words):
    gw = flatten(doc)
    t1 = tier1(gw, te_words)
    real2, _ = measure_document(te_doc)
    t2, _ = measure_document(doc)
    e1 = sum(err(*t1[k]) for k in t1) / len(t1)
    e2 = sum(err(t2[k], real2[k]) for k in real2) / len(real2)
    return e1, e2, t1, t2, real2, gw


def write_out(write, te_doc, seed=11, gallows_p=0.10):
    rng = random.Random(seed)
    lines = [ln for p in te_doc for ln in p]
    widths = [sum(len(w) for w in ln) for ln in lines]
    return scribe_document(write, len(lines), widths, [len(p) for p in te_doc], rng,
                           gallows_p=gallows_p)


# ---------------------------------------------------------------------------

def split_by_mod(paras, folios):
    """Split the training leaves in two, so hyper-parameters can be chosen honestly."""
    def mod(f):
        return int(re.match(r"f?(\d+)", f).group(1)) % 4
    A = [p for p, f in zip(paras, folios) if mod(f) == 0]
    B = [p for p, f in zip(paras, folios) if mod(f) == 2]
    return A, B


def split_with_folios():
    """As tune_artgen.split_by_folio, but keeping the folio of each paragraph."""
    path = os.path.join(ROOT, "data", "IT2a-n.txt")
    paras, folios, cur, curf, open_para = [], [], [], [], False
    for folio, locus, ltype, raw, meta in V.parse_ivtff(path):
        code = re.sub(r"\d+$", "", ltype)
        if code.lstrip("@+*&=")[:1] != "P":
            continue
        starts = raw.lstrip().startswith("<%>")
        ends = raw.rstrip().endswith("<$>")
        t = V.strip_markup(raw).replace("<%>", "").replace("<$>", "")
        ws = [x.strip("-") for x in re.split(r"[.,\s]+", t)]
        ws = [x for x in ws if x and not re.search(r"[?!]", x)
              and not any(c in x for c in "[]{}()")]
        if starts and open_para and cur:
            paras.append(cur)
            folios.append(curf[0])
            cur, curf = [], []
        if not ws:
            continue
        open_para = True
        cur.append(ws)
        curf.append(folio)
        if ends:
            paras.append(cur)
            folios.append(curf[0])
            cur, curf = [], []
            open_para = False
    if cur:
        paras.append(cur)
        folios.append(curf[0])
    return paras, folios


def main():
    cfg = json.load(open(V.frozen_path("FROZEN_CONFIG.json"), encoding="utf-8"))
    tr_doc, te_doc = split_by_folio()
    tr, te = flatten(tr_doc), flatten(te_doc)
    allp, allf = split_with_folios()
    even = [(p, f) for p, f in zip(allp, allf)
            if int(re.match(r"f?(\d+)", f).group(1)) % 2 == 0]
    A, B = split_by_mod([p for p, _ in even], [f for _, f in even])
    wa, wb = flatten(A), flatten(B)
    print(f"train {len(tr)} words   held-out {len(te)} words, "
          f"{len([l for p in te_doc for l in p])} lines")
    print(f"  selection split inside the training half: {len(wa)} / {len(wb)} words\n")

    # --- choose the hyper-parameters on the selection half only ------------------
    grid = []
    for n_forms in (40, 60, 80):
        for p_pair in (0.3, 0.5):
            for p_reuse in (0.05, 0.12):
                for gallows_p in (0.08, 0.12):
                    grid.append((n_forms, p_pair, p_reuse, gallows_p))
    print(f"choosing from {len(grid)} settings on the selection half...")
    rows = []
    for n_forms, p_pair, p_reuse, gallows_p in grid:
        man = Manual(wa, n_forms=n_forms, merges=cfg["merges"])
        w = make_scribe(man, p_pair=p_pair, p_reuse=p_reuse)
        doc = write_out(w, B, gallows_p=gallows_p)
        e1, e2, *_ = score(doc, B, wb)
        rows.append(((e1 * 15 + e2 * 29) / 44, n_forms, p_pair, p_reuse, gallows_p))
    rows.sort()
    print(f"  {'forms':>6s} {'stock pairs':>12s} {'re-use':>8s} {'gallows':>8s} {'sel. error':>11s}")
    for ov, nf, pp, pr, gp in rows[:6]:
        print(f"  {nf:6d} {pp:12.2f} {pr:8.2f} {gp:8.2f} {ov:10.1f}%")
    _, n_forms, p_pair, p_reuse, gallows_p = rows[0]
    print(f"\nchosen: {n_forms} shapes, stock pairs {p_pair}, re-use {p_reuse}, "
          f"gallows {gallows_p}")

    # --- final run: manual refitted on ALL training leaves, scored on the held-out half
    man = Manual(tr, n_forms=n_forms, merges=cfg["merges"])
    write = make_scribe(man, p_pair=p_pair, p_reuse=p_reuse)
    doc = write_out(write, te_doc, gallows_p=gallows_p)
    e1, e2, t1, t2, real2, gw = score(doc, te_doc, te)
    ov = (e1 * 15 + e2 * 29) / 44
    print(f"\nHELD-OUT RESULT  tier-1 {e1:.1f}%   tier-2 {e2:.1f}%   "
          f"overall {ov:.1f}%  over 44 metrics")
    print(f"  (the computer generator, with rejection sampling: 3.7%)")
    print(f"  generated {len(gw)} words vs {len(te)} held out\n")

    print(f"  {'metric':30s} {'scribe':>10s} {'held-out':>10s} {'err%':>8s}")
    print("  " + "-" * 62)
    for k in sorted(t1, key=lambda k: -err(*t1[k])):
        a, b = t1[k]
        print(f"  {k:30s} {a:10.3f} {b:10.3f} {err(a,b):8.1f}")
    print("  " + "-" * 62)
    for k in sorted(real2, key=lambda k: -err(t2[k], real2[k])):
        print(f"  {k:30s} {t2[k]:10.3f} {real2[k]:10.3f} {err(t2[k],real2[k]):8.1f}")

    print("\nwritten by the procedure, first passage:\n")
    for ln in doc[0][:5]:
        print("   " + " ".join(ln))
    print("\nthe real passage:\n")
    for ln in te_doc[0][:5]:
        print("   " + " ".join(ln))

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "SCRIBE_MANUAL.txt"), "w", encoding="utf-8") as fh:
        fh.write(manual_text(man, n_forms, p_pair, p_reuse, gallows_p))
    with open(os.path.join(here, "scribe_sample.txt"), "w", encoding="utf-8") as fh:
        for p in doc:
            for ln in p:
                fh.write(" ".join(ln) + "\n")
            fh.write("\n")
    json.dump({"tier1_pct": e1, "tier2_pct": e2, "overall_pct": ov,
               "n_forms": n_forms, "p_pair": p_pair, "p_reuse": p_reuse,
               "gallows_p": gallows_p, "generated_words": len(gw),
               "held_out_words": len(te)},
              open(os.path.join(here, "SCRIBE_RESULT.json"), "w", encoding="utf-8"),
              indent=1)
    print("\nwrote SCRIBE_MANUAL.txt, SCRIBE_RESULT.json, scribe_sample.txt")


def manual_text(man, n_forms, p_pair, p_reuse, gallows_p):
    L = ["THE SCRIBE'S MANUAL", "=" * 66, "",
         "Everything needed to write text of this kind by hand. No counting,",
         "no arithmetic: each rule below is one look-up and one roll of a die.", ""]
    L.append(f"A.  FORM TABLE -- the {n_forms} shapes, most used first.")
    L.append("    One pen movement each.")
    for i in range(0, len(man.forms), 8):
        L.append("      " + "   ".join(f"{u:>7s}" for u in man.forms[i:i + 8]))
    L.append("")
    L.append("B.  OPENINGS -- the standard ways a word starts.")
    for o in sorted(man.start, key=lambda o: -sum(man.start[o].values()))[:10]:
        top = sorted(man.start[o].items(), key=lambda x: -x[1])[:4]
        L.append(f"      after a word with onset {o:>3s}: " +
                 ", ".join(f"{u} {p:.2f}" for u, p in top))
    L.append("")
    L.append("C.  LINK TABLE -- after writing this letter, the next shape.")
    for c in sorted(man.link, key=lambda c: -sum(man.link[c].values()))[:14]:
        top = sorted(man.link[c].items(), key=lambda x: -x[1])[:5]
        L.append(f"      {c:>3s}: " + ", ".join(f"{u} {p:.2f}" for u, p in top))
    L.append("")
    L.append("D.  LENGTH -- how many letters the next word has.")
    top = sorted(man.lens.items(), key=lambda x: -x[1])[:12]
    L.append("      " + ", ".join(f"{k}: {p:.2f}" for k, p in sorted(top)))
    L.append("")
    L.append("E.  CLOSINGS -- the stock endings, by the word's length.")
    for k in sorted(man.close_by_len)[:10]:
        top = sorted(man.close_by_len[k].items(), key=lambda x: -x[1])[:5]
        L.append(f"      length {k:2d}: " + ", ".join(f"{u} {p:.2f}" for u, p in top))
    L.append("")
    L.append("F.  CARRY-OVER -- the last letter of the previous word sets the onset.")
    for c in sorted(man.cross, key=lambda c: -sum(man.cross[c].values()))[:12]:
        top = sorted(man.cross[c].items(), key=lambda x: -x[1])[:4]
        L.append(f"      after ...{c:>3s}: " + ", ".join(f"{u} {p:.2f}" for u, p in top))
    L.append("")
    L.append(f"G.  STOCK PHRASES -- after a word that has a habitual partner, write the")
    L.append(f"    partner instead of thinking of a new word: {p_pair:.0%} of the time.")
    L.append("")
    L.append("H.  PAGE RULES")
    L.append("      fill the column that the drawing leaves and no more")
    L.append("      a passage runs a few lines; when it ends, start a fresh one and")
    L.append("        take your forms from that passage, not from the page before")
    L.append("      open a line with a tall stroke now and then")
    L.append(f"      now and then write a word again from the same passage with one")
    L.append(f"        shape swapped for the one that usually follows it ({p_reuse:.0%})")
    L.append(f"      tall stroke at a line opening, about {gallows_p:.0%} of lines")
    L.append("")
    L.append("PROCEDURE for one word")
    L.append("      1. glance at the last letter you wrote -> onset class (F)")
    L.append("      2. write the opening (B)")
    L.append("      3. decide how long this word is (D) and how it ends (E)")
    L.append("      4. fill the middle with shapes (C) until the word is that size")
    L.append("      5. if a line is already running, keep the word short enough to")
    L.append("         reach the margin without running past it")
    return "\n".join(L)


if __name__ == "__main__":
    main()
