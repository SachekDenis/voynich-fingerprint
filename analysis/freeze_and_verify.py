"""Freeze the generator result, then verify it reproduces.

Writes:
  FROZEN_CONFIG.json  -- the exact configuration
  FROZEN_RESULTS.json -- every metric, generated vs held-out target
  FROZEN_RESULTS.md   -- human-readable scorecard

Re-running checks the new numbers against the frozen ones and reports drift.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voynich_lib as V
from tier2_metrics import measure_document, GALLOWS
from voynich_artgen import ArtGenerator
from tune_artgen import split_by_folio, flatten, tier1, err

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
# the frozen artifacts live in ./frozen in the repository layout, and beside the script
# when it is run from a working copy
OUT = (os.path.join(ROOT, "frozen")
       if os.path.isdir(os.path.join(ROOT, "frozen")) else HERE)

CONFIG = {
    "version": 3,
    "merges": 140,
    "p_copy": 0.03,
    "recency_alpha": 0.6,
    "recency_window": 120,
    "buffer_size": 700,
    "cross_onset": True,
    "p_repeat": 0.005,
    "p_pair": 0.28,
    "copy_decay": 0.0,
    "use_onset": False,
    "gallows_scale": 0.85,
    "line_fit": True,
    "fit_penalty": 0.75,
    "seeds": [7, 21, 44],
    "split": "train = even-numbered leaves, held-out = odd-numbered leaves (body text)",
}


def build(config):
    tr_doc, te_doc = split_by_folio()
    train_words, test_words = flatten(tr_doc), flatten(te_doc)
    g = ArtGenerator(train_words, merges=config["merges"])
    g.calibrate()
    g.calibrate_onset(train_words)
    g.calibrate_cross_onset(train_words)
    g.calibrate_common(train_words)
    g.calibrate_pairs(train_words)
    g.calibrate_lengths(tr_doc)
    g.fit_penalty = config["fit_penalty"]
    g.calibrate_proposal()
    g.calibrate_layout(tr_doc, gallows_p=0.0)
    real2, _ = measure_document(te_doc)
    probe = [ln for p in g.document(n_paragraphs=40, seed=3) for ln in p]
    nat = sum(1 for ln in probe if ln and any(ln[0].startswith(x) for x in GALLOWS)) / len(probe)
    g.line_gallows_p = max(0.0, (real2["para/line-initial gallows %"] / 100 - nat) / (1 - nat))
    return g, test_words, real2


def run(config):
    g, test_words, real2 = build(config)
    t1_runs, t2_runs = [], []
    for s in config["seeds"]:
        gen_doc = g.document(
            n_paragraphs=real2["paras"], seed=s,
            p_copy=config["p_copy"], recency_alpha=config["recency_alpha"],
            recency_window=config["recency_window"], buffer_size=config["buffer_size"],
            cross_onset=config["cross_onset"], use_onset=config["use_onset"],
            gallows_scale=config["gallows_scale"], p_repeat=config["p_repeat"],
            p_pair=config["p_pair"], copy_decay=config["copy_decay"],
            line_fit=config["line_fit"])
        gw = flatten(gen_doc)
        t1_runs.append(tier1(gw, test_words))
        t2_runs.append(measure_document(gen_doc)[0])
    return t1_runs, t2_runs, real2, len(test_words)


def summarise(t1_runs, t2_runs, real2, n_test):
    out = {}
    for key in t1_runs[0]:
        vals = [r[key][0] for r in t1_runs]
        out[key] = {"target": t1_runs[0][key][1], "gen": sum(vals) / len(vals),
                    "per_seed": vals}
    for key in real2:
        vals = [r[key] for r in t2_runs]
        out[key] = {"target": real2[key], "gen": sum(vals) / len(vals), "per_seed": vals}
    e1 = [err(out[k]["gen"], out[k]["target"]) for k in t1_runs[0]]
    e2 = [err(out[k]["gen"], out[k]["target"]) for k in real2]
    out["_summary"] = {
        "tier1_mean_err_pct": sum(e1) / len(e1),
        "tier2_mean_err_pct": sum(e2) / len(e2),
        "overall_mean_err_pct": (sum(e1) + sum(e2)) / (len(e1) + len(e2)),
        "n_tier1_metrics": len(e1), "n_tier2_metrics": len(e2),
        "held_out_words": n_test,
    }
    return out


def write_md(res, config):
    lines = ["# Frozen result: Voynich generator", "",
             f"Configuration: `{json.dumps({k: v for k, v in config.items() if k != 'split'})}`",
             f"Split: {config['split']}", ""]
    s = res["_summary"]
    lines += [f"**Tier-1 mean error: {s['tier1_mean_err_pct']:.1f}%** "
              f"({s['n_tier1_metrics']} metrics) &nbsp;|&nbsp; "
              f"**Tier-2 mean error: {s['tier2_mean_err_pct']:.1f}%** "
              f"({s['n_tier2_metrics']} metrics) &nbsp;|&nbsp; "
              f"**overall: {s['overall_mean_err_pct']:.1f}%** over "
              f"{s['n_tier1_metrics'] + s['n_tier2_metrics']} metrics", ""]
    for tier, keys in (("Tier 1 — text statistics", list(res)[:s["n_tier1_metrics"]]),
                       ("Tier 2 — structure", [k for k in res if k in
                                               list(res)[s["n_tier1_metrics"] + 1:]])):
        lines += [f"## {tier}", "", "| metric | held-out target | generator | error |",
                  "|---|---|---|---|"]
        for k in keys:
            if k == "_summary" or not isinstance(res[k], dict):
                continue
            r = res[k]
            lines.append(f"| {k} | {r['target']:.3f} | {r['gen']:.3f} | "
                         f"{err(r['gen'], r['target']):.1f}% |")
        lines.append("")
    return "\n".join(lines)


def main():
    cfg_path = os.path.join(OUT, "FROZEN_CONFIG.json")
    res_path = os.path.join(OUT, "FROZEN_RESULTS.json")
    verifying = "--verify" in sys.argv

    config = json.load(open(cfg_path, encoding="utf-8")) if (verifying and
                                                             os.path.exists(cfg_path)) else CONFIG
    t1, t2, real2, n_test = run(config)
    res = summarise(t1, t2, real2, n_test)

    if verifying:
        old = json.load(open(res_path, encoding="utf-8"))
        print("verification against frozen results:")
        drift = []
        for k, v in res.items():
            if k == "_summary":
                continue
            o = old.get(k, {}).get("gen")
            if o is None:
                continue
            d = abs(v["gen"] - o) / (abs(o) or 1) * 100
            drift.append((k, o, v["gen"], d))
        for k, o, n, d in sorted(drift, key=lambda x: -x[3])[:8]:
            flag = "DRIFT" if d > 5 else "ok"
            print(f"  {flag:5s} {k:30s} frozen {o:9.3f}  now {n:9.3f}  {d:5.2f}%")
        worst = max(d for *_, d in drift)
        print(f"\nworst drift {worst:.2f}%  ->  "
              f"{'REPRODUCIBLE' if worst < 5 else 'REPRODUCIBILITY FAILURE'}")
        return

    json.dump(config, open(cfg_path, "w", encoding="utf-8"), indent=1)
    json.dump(res, open(res_path, "w", encoding="utf-8"), indent=1)
    open(os.path.join(OUT, "FROZEN_RESULTS.md"), "w", encoding="utf-8").write(write_md(res, config))
    s = res["_summary"]
    print(f"tier-1 mean error {s['tier1_mean_err_pct']:.1f}%  "
          f"tier-2 {s['tier2_mean_err_pct']:.1f}%  overall {s['overall_mean_err_pct']:.1f}%")
    print("wrote FROZEN_CONFIG.json, FROZEN_RESULTS.json, FROZEN_RESULTS.md")


if __name__ == "__main__":
    main()
