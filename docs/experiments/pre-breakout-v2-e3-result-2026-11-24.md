# Predict V2 — E3 retrospective result and E3b decision

E3 run [45434889849](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45434889849) completed successfully. 51,390 causal snapshots; 47,670 inside previous range (geometric proxy, not exact PRD pre-breakout state). Each side: 28,445 training rows, 9,471 validation, 9,536 retrospective test. 436 side rows purged/censored.

| Side | Validation AUC | Test AUC | Validation Brier model / constant | Test Brier model / constant |
|---|---:|---:|---:|---:|
| LONG | 0.531656 | 0.541517 | 0.0759873 / 0.0759879 | 0.0975962 / 0.0970198 |
| SHORT | 0.667224 | 0.642345 | 0.1082907 / 0.1116034 | 0.0914563 / 0.0947810 |

Model gate p>=0.5 (both sides): validation 2 trades +2.4033R; test 6 trades -0.2989R; adverse costs 0.24% yield +2.1049R and -0.9982R respectively. Baseline test 304 trades -96.9543R; compression 184 trades -63.1952R at 0.16% round-trip. No consistent financial edge. Lower total loss is mostly lower exposure.

E3b post-hoc stability audit of frozen probabilities: per-symbol, per-day, leave-one-symbol-out, fixed calibration bins and joint cross-asset temporal block bootstrap (6/24/48h, 1000 replicates, fixed seed). Both sides retained; no threshold optimization, refit or model selection on test. Intervals are descriptive and small-block limited. Any subsequent SHORT-focused model is a new hypothesis requiring a fresh prospective test. No production or schedule changes; no orders or alerts.
