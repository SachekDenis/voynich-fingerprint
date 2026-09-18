# Frozen result: Voynich generator

Configuration: `{"version": 3, "merges": 140, "p_copy": 0.03, "recency_alpha": 0.6, "recency_window": 120, "buffer_size": 700, "cross_onset": true, "p_repeat": 0.005, "p_pair": 0.28, "copy_decay": 0.0, "use_onset": false, "gallows_scale": 0.85, "line_fit": true, "fit_penalty": 0.75, "seeds": [7, 21, 44]}`
Split: train = even-numbered leaves, held-out = odd-numbered leaves (body text)

**Tier-1 mean error: 2.7%** (15 metrics) &nbsp;|&nbsp; **Tier-2 mean error: 4.3%** (29 metrics) &nbsp;|&nbsp; **overall: 3.7%** over 44 metrics

## Tier 1 — text statistics

| metric | held-out target | generator | error |
|---|---|---|---|
| h1 (char) | 3.863 | 3.855 | 0.2% |
| h2 (char) | 1.842 | 1.860 | 1.0% |
| H(word) | 10.140 | 10.156 | 0.2% |
| TTR | 0.275 | 0.252 | 8.6% |
| hapax % | 19.713 | 17.224 | 12.6% |
| mean word len | 5.173 | 5.181 | 0.2% |
| sd word len | 1.863 | 1.894 | 1.7% |
| H init | 3.386 | 3.401 | 0.4% |
| H final | 2.996 | 2.999 | 0.1% |
| len dist TV | 0.000 | 0.026 | 2.6% |
| top-5 onsets % | 70.175 | 70.368 | 0.3% |
| top-5 finals % | 91.640 | 93.150 | 1.6% |
| final-y % | 40.302 | 41.629 | 3.3% |
| top-10 word share % | 12.813 | 11.949 | 6.7% |
| cross-word MI | 0.068 | 0.068 | 0.7% |

## Tier 2 — structure

| metric | held-out target | generator | error |
|---|---|---|---|
| line chars sd | 16.050 | 14.284 | 11.0% |
| words per line mean | 8.125 | 8.687 | 6.9% |
| lines | 2023.000 | 2167.667 | 7.2% |
| paras | 392.000 | 392.000 | 0.0% |
| para lines mean | 5.161 | 5.530 | 7.2% |
| para/line-initial gallows % | 21.997 | 19.527 | 11.2% |
| all gallows % | 10.653 | 11.059 | 3.8% |
| onset ent ropy | 3.489 | 3.471 | 0.5% |
| qo- onset % | 15.192 | 15.375 | 1.2% |
| ch- onset % | 15.782 | 16.267 | 3.1% |
| y- onset % | 4.399 | 4.499 | 2.3% |
| top10 (first,last) pairs % | 50.402 | 50.550 | 0.3% |
| distinct (first,last) pairs | 187.000 | 186.667 | 0.2% |
| zipf slope (top500) | -0.904 | -0.924 | 2.2% |
| hapax share of types % | 71.586 | 68.405 | 4.4% |
| adjacent identical words % | 0.870 | 1.051 | 20.7% |
| repeated word-pair % | 15.284 | 17.168 | 12.3% |
| H pos1 from start | 3.203 | 3.205 | 0.1% |
| H pos1 from end | 2.451 | 2.380 | 2.9% |
| H pos2 from start | 3.260 | 3.268 | 0.3% |
| H pos2 from end | 2.893 | 2.919 | 0.9% |
| H pos3 from start | 3.478 | 3.514 | 1.0% |
| H pos3 from end | 3.275 | 3.301 | 0.8% |
| H pos4 from start | 3.604 | 3.617 | 0.4% |
| H pos4 from end | 3.364 | 3.397 | 1.0% |
| len>=8 % | 8.329 | 9.193 | 10.4% |
| len>=10 % | 1.758 | 1.824 | 3.7% |
| len<=2 % | 7.240 | 7.175 | 0.9% |
