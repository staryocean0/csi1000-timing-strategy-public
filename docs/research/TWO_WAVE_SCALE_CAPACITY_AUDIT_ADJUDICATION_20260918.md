# Capacity audit adjudication — 2026-09-18

Issue #393 found that no single existing morphology axis can cleanly recover most explicit AMBIGUOUS cases under low false-capture budgets. The best descriptive single-axis interval captures at most 4/13 ambiguous cases at 5% false capture, 6/13 at 10%, and 8/13 at 20%.

Validity has real raw information (direction-free AUC about 0.859/0.839/0.836 for close-jump concentration, close-range concentration, and local jump isolation), but v3 uses five rule identities across six folds and mean invalid recall drops from about 0.625 in training to about 0.478 held-out. This supports a temporally robust selection revision rather than inventing new raw validity features.

No audit interval or threshold is a candidate. No full fit, lag promotion, label change, R4/router/PnL or production authority occurred.
