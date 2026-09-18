"""Does one procedure explain every section of the book?

Everything so far split the corpus by leaf parity, so training and test always contained
the same mix of sections. That leaves a question open: is the generator fitted to the
herbal able to produce the recipes? If the sections need different parameters, then one
procedure does not explain the book, and the section differences -- the 'dialects' --
are something the model has not captured.

Two things this test has to get right, both learned the hard way:

  * Paragraphs come from the manuscript's own <%> / <$> marks, not from the locus type
    (@ marks only the first paragraph of a page). Using the locus type merges a page of
    recipes into one 43-line 'paragraph', which is an artefact of the transcription.
  * The generated document must be the same SIZE as the section it is being compared
    to. Repeat rate, hapax share and TTR all drift with sample size; generating one
    paragraph per target paragraph while the source section has different paragraph
    lengths silently compares 2 000 words against 16 000.

Both were wrong in the first version of this test, and both inflated the error.
"""
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from tier2_metrics import measure_document, GALLOWS
from voynich_artgen import ArtGenerator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTIONS = ["herbal", "astronomical", "zodiac", "biological", "cosmological",
            "pharmaceutical", "recipes"]


def section_docs(path=None):
    """Words and the real document (paragraphs of lines) per section, single pass."""
    path = path or os.path.join(ROOT, "data", "IT2a-n.txt")
    words, paras = defaultdict(list), defaultdict(list)
    cur, cur_sec, open_para = [], None, False
    for folio, locus, ltype, raw, meta in V.parse_ivtff(path):
        code = re.sub(r"\d+$", "", ltype)
        if code.lstrip("@+*&=")[:1] != "P":
            continue
        sec = V.section_of(folio)
        starts = raw.lstrip().startswith("<%>")
        ends = raw.rstrip().endswith("<$>")
        t = V.strip_markup(raw).replace("<%>", "").replace("<$>", "")
        ws = [x.strip("-") for x in re.split(r"[.,\s]+", t)]
        ws = [x for x in ws if x and not re.search(r"[?!]", x)
              and not any(c in x for c in "[]{}()")]
        if starts and open_para and cur:
            paras[cur_sec].append(cur)
            cur, open_para = [], False
        if not ws:
            continue
        if cur and cur_sec != sec:
            paras[cur_sec].append(cur)
            cur = []
        open_para = True
        cur_sec = sec
        cur.append(ws)
        words[sec].extend(ws)
        if ends:
            paras[sec].append(cur)
            cur, open_para = [], False
    if cur:
        paras[cur_sec].append(cur)
    return words, paras


def build(train_words, merges=140):
    g = ArtGenerator(train_words, merges=merges)
    g.calibrate()
    g.calibrate_onset(train_words)
    g.calibrate_cross_onset(train_words)
    g.calibrate_common(train_words)
    g.calibrate_pairs(train_words)
    return g


def finish(g, train_doc, test_doc, cfg):
    g.calibrate_lengths(train_doc)
    g.fit_penalty = cfg["fit_penalty"]
    g.calibrate_proposal()
    g.calibrate_layout(train_doc, gallows_p=0.0)
    g.gallows_scale = cfg["gallows_scale"]
    real2, _ = measure_document(test_doc)
    probe = [ln for p in g.document(30, seed=3) for ln in p]
    nat = sum(1 for ln in probe if ln and any(ln[0].startswith(x) for x in GALLOWS)) / len(probe)
    g.line_gallows_p = max(0.0, (real2["para/line-initial gallows %"] / 100 - nat) / (1 - nat))
    return real2


def generate_matched(g, cfg, seed, target_words):
    """Generate until the word count matches the target section's, not its paragraph count."""
    n = 60
    doc = None
    for _ in range(4):
        doc = g.document(n, seed=seed, p_copy=cfg["p_copy"],
                         recency_alpha=cfg["recency_alpha"],
                         buffer_size=cfg["buffer_size"],
                         cross_onset=cfg["cross_onset"], p_repeat=cfg["p_repeat"],
                         p_pair=cfg["p_pair"], line_fit=cfg["line_fit"],
                         gallows_scale=cfg["gallows_scale"])
        got = sum(len(ln) for p in doc for ln in p)
        if got and abs(got - target_words) / target_words < 0.03:
            break
        n = max(5, int(round(n * target_words / got)))
    return doc


def run(src, dst, cfg, words, paras, verbose=False, layout_from=None):
    if src not in paras or dst not in paras or len(words[src]) < 3000 or len(words[dst]) < 800:
        return None
    g = build(list(words[src]))
    real2 = finish(g, paras[layout_from or src], paras[dst], cfg)
    doc = generate_matched(g, cfg, 7, len(words[dst]))
    gw = [w for p in doc for ln in p for w in ln]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tune_artgen import tier1, err
    t1 = tier1(gw, words[dst])
    t2, _ = measure_document(doc)
    e1 = sum(err(*t1[k]) for k in t1) / len(t1)
    e2 = sum(err(t2[k], real2[k]) for k in real2) / len(real2)
    if verbose:
        rows = sorted(((err(t2[k], real2[k]), k, t2[k], real2[k]) for k in real2), reverse=True)
        print(f"\n{src} -> {dst}: worst tier-2 metrics "
              f"({len(gw)} generated words vs {len(words[dst])} real)")
        print(f"  {'metric':32s} {'gen':>10s} {'real':>10s} {'err%':>8s}")
        print("  " + "-" * 64)
        for e, k, a, b in rows[:10]:
            print(f"  {k:32s} {a:10.3f} {b:10.3f} {e:8.1f}")
    return e1, e2, len(words[src]), len(words[dst]), len(gw)


if __name__ == "__main__":
    cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "FROZEN_CONFIG.json"), encoding="utf-8"))
    words, paras = section_docs()
    print("words per section: " +
          ", ".join(f"{s} {len(words[s])}" for s in SECTIONS if s in words))
    print(f"\n{'train':16s} {'test':16s} {'train n':>8s} {'test n':>7s} {'gen n':>7s} "
          f"{'tier-1':>7s} {'tier-2':>7s}")
    print("-" * 80)
    for sec in SECTIONS:
        if sec not in words or len(words[sec]) < 800:
            continue
        r = run(sec, sec, cfg, words, paras)
        if r:
            print(f"{sec:16s} {sec:16s} {r[2]:8d} {r[3]:7d} {r[4]:7d} {r[0]:6.1f}% {r[1]:6.1f}%")
    print()
    pairs = [("herbal", "recipes"), ("recipes", "herbal"),
             ("herbal", "biological"), ("biological", "herbal"),
             ("pharmaceutical", "recipes"), ("herbal", "pharmaceutical"),
             ("biological", "recipes")]
    for a, b in pairs:
        r = run(a, b, cfg, words, paras)
        if r:
            print(f"{a:16s} -> {b:14s} {r[2]:8d} {r[3]:7d} {r[4]:7d} {r[0]:6.1f}% {r[1]:6.1f}%")
    print("\nworst metrics for herbal -> recipes and the within-section control:")
    run("herbal", "recipes", cfg, words, paras, verbose=True)
    run("herbal", "herbal", cfg, words, paras, verbose=True)

    # How much of the cross-section error is paper rather than text?  Mean characters
    # per line runs from 27.0 (astronomical) to 52.5 (recipes), following how much of
    # the page the drawing takes, and a writer plainly copies the column width from the
    # page in front of him. So give the generator the target's geometry and see what is
    # left. This is a diagnostic, not a claim about the model: it borrows the target's
    # layout on purpose.
    print("\nsame test, but the generator is told the target section's layout "
          "(line width and paragraph shape):")
    print(f"  {'train -> test':26s} {'as-is':>16s} {'layout from target':>20s}")
    print("  " + "-" * 64)
    for a, b in [("herbal", "recipes"), ("recipes", "herbal"),
                 ("herbal", "biological"), ("biological", "herbal"),
                 ("pharmaceutical", "recipes"), ("herbal", "pharmaceutical")]:
        x = run(a, b, cfg, words, paras)
        y = run(a, b, cfg, words, paras, layout_from=b)
        if x and y:
            print(f"  {a + ' -> ' + b:26s} {x[0]:6.1f}%/{x[1]:5.1f}%   "
                  f"{y[0]:7.1f}%/{y[1]:5.1f}%")
    print("\n  tier-2 improves by a quarter to a third; tier-1 barely moves. Layout is a")
    print("  real but secondary part of the section difference -- the rest is in the text.")
