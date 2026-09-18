# Frozen result: Voynich generator

Configuration: `{"version": 3, "merges": 140, "p_copy": 0.03, "recency_alpha": 0.6, "recency_window": 120, "buffer_size": 700, "cross_onset": true, "p_repeat": 0.005, "p_pair": 0.28, "copy_decay": 0.0, "use_onset": false, "gallows_scale": 0.85, "line_fit": true, "fit_penalty": 0.75, "seeds": [7, 21, 44]}`
Split: train = even-numbered leaves, held-out = odd-numbered leaves (body text)

**Tier-1 mean error: 2.8%** (15 metrics) &nbsp;|&nbsp; **Tier-2 mean error: 4.6%** (29 metrics) &nbsp;|&nbsp; **overall: 4.0%** over 44 metrics

## Tier 1 — text statistics

| metric | held-out target | generator | error |
|---|---|---|---|
| h1 (char) | 3.863 | 3.855 | 0.2% |
| h2 (char) | 1.842 | 1.860 | 1.0% |
| H(word) | 10.140 | 10.178 | 0.4% |
| TTR | 0.275 | 0.249 | 9.7% |
| hapax % | 19.713 | 17.019 | 13.7% |
| mean word len | 5.173 | 5.181 | 0.2% |
| sd word len | 1.863 | 1.889 | 1.4% |
| H init | 3.386 | 3.402 | 0.5% |
| H final | 2.996 | 3.001 | 0.2% |
| len dist TV | 0.000 | 0.020 | 2.0% |
| top-5 onsets % | 70.175 | 70.135 | 0.1% |
| top-5 finals % | 91.640 | 93.106 | 1.6% |
| final-y % | 40.302 | 41.845 | 3.8% |
| top-10 word share % | 12.813 | 11.870 | 7.4% |
| cross-word MI | 0.068 | 0.068 | 0.2% |

## Tier 2 — structure

| metric | held-out target | generator | error |
|---|---|---|---|
| line chars sd | 16.050 | 14.341 | 10.6% |
| words per line mean | 8.125 | 8.674 | 6.8% |
| lines | 2023.000 | 2279.333 | 12.7% |
| paras | 145.000 | 145.000 | 0.0% |
| para lines mean | 13.952 | 15.720 | 12.7% |
| para/line-initial gallows % | 21.997 | 19.880 | 9.6% |
| all gallows % | 10.653 | 11.298 | 6.0% |
| onset ent ropy | 3.489 | 3.474 | 0.4% |
| qo- onset % | 15.192 | 15.368 | 1.2% |
| ch- onset % | 15.782 | 16.378 | 3.8% |
| y- onset % | 4.399 | 4.590 | 4.4% |
| top10 (first,last) pairs % | 50.402 | 50.246 | 0.3% |
| distinct (first,last) pairs | 187.000 | 188.667 | 0.9% |
| zipf slope (top500) | -0.904 | -0.920 | 1.7% |
| hapax share of types % | 71.586 | 68.436 | 4.4% |
| adjacent identical words % | 0.870 | 0.969 | 11.4% |
| repeated word-pair % | 15.284 | 17.626 | 15.3% |
| H pos1 from start | 3.203 | 3.207 | 0.1% |
| H pos1 from end | 2.451 | 2.375 | 3.1% |
| H pos2 from start | 3.260 | 3.281 | 0.7% |
| H pos2 from end | 2.893 | 2.928 | 1.2% |
| H pos3 from start | 3.478 | 3.512 | 1.0% |
| H pos3 from end | 3.275 | 3.302 | 0.8% |
| H pos4 from start | 3.604 | 3.607 | 0.1% |
| H pos4 from end | 3.364 | 3.398 | 1.0% |
| len>=8 % | 8.329 | 9.012 | 8.2% |
| len>=10 % | 1.758 | 1.868 | 6.2% |
| len<=2 % | 7.240 | 7.277 | 0.5% |
