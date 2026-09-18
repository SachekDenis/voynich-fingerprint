"""Check report.pdf against the result files it claims to describe.

Every figure in the PDF is supposed to come from one of the JSON files the analysis
scripts write. This pulls the text out of the PDF and checks that the numbers it asserts
are the numbers those files contain, so the two cannot drift apart unnoticed.
"""
import base64
import json
import os
import re
import zlib

BS = chr(92)          # backslash, kept out of the shell's way

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def pdf_text(path):
    d = open(path, "rb").read()
    blob = ""
    for mm in re.finditer(rb"(\d+) 0 obj\s*<<(.*?)>>\s*stream\r?\n(.*?)endstream",
                          d, re.S):
        if b"ASCII85Decode" not in mm.group(2):
            continue
        body = mm.group(3).strip()
        if body.endswith(b"~>"):
            body = body[:-2]
        blob += zlib.decompress(base64.a85decode(body, adobe=False,
                                                  ignorechars=b" \t\r\n")).decode("latin-1")
    txt = " ".join(re.findall(r"\((.*?)\)\s*T[Jj]", blob))
    for oct_, ch in (("226", "-"), ("327", "x"), ("256", ">"), ("263", ">="),
                     ("243", "<="), ("227", "--")):
        txt = txt.replace(BS + oct_, ch)
    return txt


def main():
    txt = pdf_text(os.path.join(ROOT, "report.pdf"))
    J = lambda p: json.load(open(os.path.join(ROOT, p), encoding="utf-8"))
    fp = J("analysis/fingerprints.json")
    bm = J("analysis/BOOK_MODEL.json")
    rf = J("analysis/REPETITION_FIX.json")
    fr = J("frozen/FROZEN_RESULTS.json")["_summary"]
    sc = J("analysis/SCRIBE_RESULT.json")
    gc = J("analysis/GENERATOR_COMPARISON.json")
    mg = J("analysis/WORD_MI_GAP.json")
    sg = J("analysis/SECTION_GAP.json")
    mi = J("analysis/WORD_MI_POSITION.json")

    nat = {k: v["h2_char"] for k, v in fp.items()
           if k not in ("Voynichese", "Voy-A", "Voy-B")}
    nearest = min(nat, key=nat.get)
    def le2(v):
        return sum(c for k, c in v["len_hist"].items() if int(k) <= 2)
    short = sorted(((k, le2(v)) for k, v in fp.items()
                    if k not in ("Voynichese", "Voy-A", "Voy-B")), key=lambda x: x[1])
    print("checking report.pdf against the result files")
    print()

    checks = []

    def chk(name, ok, note=""):
        checks.append((name, bool(ok), note))

    # --- what the documents must contain, from the files that produce them
    chk("nearest-language gap 1.23 bits",
        f"{nat[nearest] - 1.893:.2f} bits" in txt, f"{nearest} {nat[nearest]:.3f}")
    chk("stale 1.09 bit gap gone", "1.09 bits" not in txt)
    chk("manuscript short-word share",
        f"{100 * le2(fp['Voynichese']):.1f} %" in txt,
        f"{100 * le2(fp['Voynichese']):.1f} %")
    chk("corpus short-word range",
        f"{100 * short[0][1]:.1f} %" in txt and f"{100 * short[-1][1]:.1f} %" in txt,
        f"{short[0][0]} {100*short[0][1]:.1f} .. {short[-1][0]} {100*short[-1][1]:.1f}")
    chk("stale 5.8 / 17.9-27.3 gone",
        not any(s in txt for s in ("5.8 %", "17.9", "27.3 %")))
    chk("headline overall", f"{fr['overall_mean_err_pct']:.1f} %" in txt)
    chk("headline tier-1/tier-2",
        f"{fr['tier1_mean_err_pct']:.1f} %" in txt and f"{fr['tier2_mean_err_pct']:.1f} %" in txt)
    chk("manual overall", f"{sc['overall_pct']:.1f} %" in txt)
    chk("Timm best tier-1/structural",
        f"{gc['results']['Timm (none)']['tier1_err_pct']:.1f} %" in txt
        and f"{gc['results']['Timm (none)']['structural_err_pct']:.1f} %" in txt)
    chk("book A pooled", f"{bm['A_pooled_whole_book']['overall_pct']:.2f} %" in txt)
    chk("book B pooled", f"{bm['B_pooled_model_per_section']['pooled_pct']:.2f} %" in txt)
    chk("book C pooled", f"{bm['C_per_section_parameters']['pooled_pct']:.2f} %" in txt)
    B = bm["B_pooled_model_per_section"]["per_section"]
    t1 = [v["tier1_pct"] for v in B.values()]
    chk("book B tier-1 range", f"{min(t1):.1f}-{max(t1):.1f} %" in txt,
        f"{min(t1):.1f}-{max(t1):.1f}")
    chk("stale 9.1-19.1 gone", "9.1-19.1" not in txt)
    chk("pool within ratio", f"{rf['two_split']['passage pool_normal']['within_ratio']:.2f} x" in txt)
    chk("frozen two-split error",
        f"{rf['two_split']['frozen_normal']['overall_pct']:.2f} / "
        f"{rf['two_split']['frozen_reversed']['overall_pct']:.2f} %" in txt)
    chk("stale single-seed frozen row gone",
        f"{rf['frozen']['overall_pct']:.2f} %" not in txt)
    chk("MI offsets 3 and 4",
        f"{mg['manuscript']['3']['true']:.3f}" in txt
        and f"{mg['manuscript']['4']['true']:.3f}" in txt)
    chk("MI beyond 6 is zero", "any measurable dependence" in txt)
    chk("front-half share", "front" in txt and "86" in txt)
    section_means = {}
    for c in ("layout", "lengths", "onset", "pairs"):
        section_means[c] = sum(v["swaps"][c]["removed_pct"] for v in sg.values()) / len(sg)
    chk("section gap shares",
        all(f"{round(v)} %" in txt for v in section_means.values()),
        ", ".join(f"{k} {round(v)}" for k, v in section_means.items()))
    chk("corpora provenance note", "11 UD treebanks" in txt)

    # --- things the PDF asserts that nothing in the repo computes
    chk("one-seed caveat present", "One seed on the selection split" in txt)

    # --- structural
    pages = len(re.findall(rb"/Type\s*/Page[^s]", open(os.path.join(ROOT, "report.pdf"), "rb").read()))

    width = max(len(n) for n, _, _ in checks)
    bad = 0
    for name, ok, note in checks:
        print(f"  {'OK  ' if ok else 'FAIL'} {name:<{width}} {note}")
        bad += not ok
    print()
    print(f"  {len(checks) - bad} of {len(checks)} checks passed; {pages} pages")


if __name__ == "__main__":
    main()
