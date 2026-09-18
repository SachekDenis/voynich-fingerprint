"""Parsing and cleaning utilities for IVTFF 2.0 Voynich transliteration files."""
import re
import os
from collections import Counter, defaultdict

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

FOLIO_RE = re.compile(r"^<([^>]+)>\s*(.*)$")
INLINE_TAG_RE = re.compile(r"<[^>]*>")


def folio_sort_key(folio):
    m = re.match(r"^f?(\d+)([rv])", folio)
    if not m:
        return (0, "", "")
    return (int(m.group(1)), m.group(2), folio)


def parse_ivtff(path):
    """Yield (folio, locus, locus_type, paragraph_id, raw_text, meta) for every text line."""
    folio = None
    meta = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n").rstrip("\r")
            if not line.strip():
                continue
            if line.startswith("#"):
                continue
            m = FOLIO_RE.match(line)
            if not m:
                continue
            header, rest = m.group(1), m.group(2)
            if "." not in header:
                meta = {k: v.rstrip(">") for k, v in re.findall(r"\$(\w+)=([^\s>]+)", rest)}
                folio = header.strip()
                continue
            # locus header like f1r.1,@P0
            parts = header.split(",", 1)
            locus = parts[0]
            ltype = parts[1] if len(parts) > 1 else ""
            yield folio, locus, ltype, rest.strip(), dict(meta)


def strip_markup(text):
    """Remove inline <> tags, IVTFF special codes, keep only transliteration chars."""
    t = INLINE_TAG_RE.sub("", text)
    t = t.replace("<->", "-").replace("<%>", "").replace("<$>", "")
    return t.strip()


# Characters that carry information vs. those that are editorial comments.
EDITORIAL = set("?!*[]{}()")


def clean_word(w):
    """Return cleaned word or None if unusable for statistics."""
    w = w.strip(".,;:")
    if not w:
        return None
    if any(c in w for c in "[]{}()"):
        return None
    return w


def iter_words(path, min_len=1, drop_uncertain=True):
    """Yield (folio, section, currier_language, hand, word), handling line-break hyphens."""
    pending = None  # word split across lines with trailing '-'
    for folio, locus, ltype, raw, meta in parse_ivtff(path):
        text = strip_markup(raw)
        text = text.replace("<%>", "").replace("<$>", "")
        if pending:
            text = pending + text
            pending = None
        # A trailing '-' means the word continues on the next line.
        if text.endswith("-"):
            pending = text[:-1]
            continue
        section = section_of(folio)
        lang = meta.get("L", "?")
        hand = meta.get("H", "?")
        for tok in re.split(r"[.,\s]+", text):
            if not tok:
                continue
            tok = tok.strip("-")
            w = clean_word(tok)
            if w is None:
                continue
            if drop_uncertain and re.search(r"[?!]", w):
                continue
            if len(w) < min_len:
                continue
            yield folio, section, lang, hand, w


# ---- Section assignment by folio (standard Beinecke division) ----

ILLUSTRATION_SECTION = {
    "T": "text-only", "H": "herbal", "Z": "zodiac", "B": "biological",
    "P": "pharmaceutical", "C": "cosmological", "A": "astronomical",
    "S": "stars", "M": "misc",
}


def section_of(folio):
    """Standard Beinecke/voynich.nu section division by folio number."""
    m = re.match(r"^f?(\d+)", folio)
    if not m:
        return "other"
    n = int(m.group(1))
    if n <= 66:
        return "herbal"
    if n <= 69:
        return "astronomical"
    if n <= 73:
        return "zodiac"
    if n <= 74:
        return "other"
    if n <= 84:
        return "biological"
    if n <= 86:
        return "cosmological"
    if n <= 102:
        return "pharmaceutical"
    return "recipes"


def load_words(path, **kw):
    return list(iter_words(path, **kw))


def word_counts(words, field=4):
    return Counter(w[field] for w in words)


def basic_stats(words):
    wc = word_counts(words)
    toks = sum(wc.values())
    types = len(wc)
    hapax = sum(1 for w, c in wc.items() if c == 1)
    return {
        "tokens": toks,
        "types": types,
        "type_token_ratio": types / toks if toks else 0,
        "hapax": hapax,
        "hapax_ratio": hapax / toks if toks else 0,
        "hapax_of_types": hapax / types if types else 0,
    }


def char_entropy(words):
    """H0 (uniform), H1 (letter unigram), H2 (letter bigram conditional)."""
    import math
    from collections import Counter
    chars = Counter()
    bigrams = Counter()
    for row in words:
        w = row[-1]
        for c in w:
            chars[c] += 1
        for i in range(len(w) - 1):
            bigrams[w[i:i + 2]] += 1
    n = sum(chars.values())
    h0 = math.log2(len(chars)) if chars else 0
    h1 = -sum((c / n) * math.log2(c / n) for c in chars.values())
    nb = sum(bigrams.values())
    # conditional entropy h2 = H(X,Y) - H(X)
    hxy = -sum((c / nb) * math.log2(c / nb) for c in bigrams.values())
    h2 = hxy - h1
    return h0, h1, h2


def word_entropy(words):
    """Unigram word entropy and conditional (bigram-of-words) entropy."""
    import math
    wc = word_counts(words)
    n = sum(wc.values())
    h1 = -sum((c / n) * math.log2(c / n) for c in wc.values())
    return h1, n, len(wc)
