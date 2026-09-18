"""Robustness check: is the low conditional entropy of Voynichese an artifact of EVA digraphs?

Compares the same statistic across three independent transliteration alphabets,
including v101 (Currier), in which each manuscript glyph maps to exactly one character.
"""
import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

ENTITY_RE = re.compile(r"@(\d+);")


def de_entity(text):
    """Map @NNN; hybrid entities to a single private-use codepoint (one symbol)."""
    return ENTITY_RE.sub(lambda m: chr(0xE000 + int(m.group(1))), text)


def words_of(path, entity=False):
    out = []
    for folio, locus, ltype, raw, meta in V.parse_ivtff(path):
        t = V.strip_markup(raw)
        if entity:
            t = de_entity(t)
        t = t.replace("<%>", "").replace("<$>", "")
        for tok in re.split(r"[.,\s]+", t):
            tok = tok.strip("-")
            if not tok or re.search(r"[?!]", tok):
                continue
            if any(c in tok for c in "[]{}()"):
                continue
            out.append((folio, meta.get("L", "?"), tok))
    return out


def metrics(ws):
    chars, bigs = Counter(), Counter()
    for w in ws:
        for c in w:
            chars[c] += 1
        for i in range(len(w) - 1):
            bigs[w[i:i + 2]] += 1
    n = sum(chars.values())
    h0 = math.log2(len(chars))
    h1 = -sum((c / n) * math.log2(c / n) for c in chars.values())
    nb = sum(bigs.values())
    hxy = -sum((c / nb) * math.log2(c / nb) for c in bigs.values())
    h2 = hxy - h1
    return len(chars), h0, h1, h2


FILES = [
    ("EVA (Takahashi)", "IT2a-n.txt", False),
    ("v101 (Currier)", "GC2a-n.txt", True),
    ("ZL (Landini/Zandbergen)", "ZL3b-n.txt", False),
    ("VT (Voynich text)", "VT0e-n.txt", False),
    ("RF (Friedman)", "RF1b-e.txt", False),
]

print(f"{'alphabet':26s} {'tokens':>7s} {'|A|':>5s} {'H0':>6s} {'h1':>6s} {'h2':>6s}  h2/h1")
print("-" * 68)
for label, fname, ent in FILES:
    p = os.path.join(DATA, fname)
    if not os.path.exists(p):
        print(f"{label:26s} (missing {fname})")
        continue
    ws = [w for _, _, w in words_of(p, entity=ent)]
    a, h0, h1, h2 = metrics(ws)
    print(f"{label:26s} {len(ws):7d} {a:5d} {h0:6.3f} {h1:6.3f} {h2:6.3f}  {h2/h1:5.3f}")

# reference point: same metric on a natural language in its normal orthography
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refstats import tok_from_conllu
for name in ["latin", "ocs", "italian"]:
    p = os.path.join(ROOT, "data", "ref", f"{name}.conllu")
    if os.path.exists(p):
        ws = tok_from_conllu(p)
        a, h0, h1, h2 = metrics(ws)
        print(f"{name+' (natural)':26s} {len(ws):7d} {a:5d} {h0:6.3f} {h1:6.3f} {h2:6.3f}  {h2/h1:5.3f}")
