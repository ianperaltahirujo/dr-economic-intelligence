"""
DR Vulnerability Score - Backtest and Weight Optimizer
Evaluates current weights against known DR stress periods and proposes
optimized weights that would have produced stronger signals historically.

Known stress periods used for calibration:
    COVID collapse     2020-03 to 2020-09  (GDP -6.7%, tourism zeroed)
    Inflation peak     2022-06 to 2022-12  (IPC >9% YoY, peso -7%)
    Post-COVID stress  2021-01 to 2021-06  (slow recovery, US uncertainty)

Methodology:
    1. Score all months 2012-present with current weights
    2. Measure mean score in stress periods vs calm periods
    3. Run constrained optimization to maximize stress/calm separation
    4. Print proposed weights and require human approval before applying

Usage:
    python pipeline/backtest_weights.py          # run backtest only
    python pipeline/backtest_weights.py --apply  # apply optimized weights
                                                 # (requires confirmation)
"""

import sys
import argparse
import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.build_vulnerability import (
    VULNERABILITY_COMPONENTS,
    ZSCORE_WINDOW,
    compute_zscores,
)

# ── Known DR stress periods ───────────────────────────────────────────────────
# Each entry: (label, start, end, severity)
# severity: 'high' = confirmed crisis, 'moderate' = notable stress
# These are ground truth labels for calibration.

STRESS_PERIODS = [
    ("COVID collapse",      "2020-03", "2020-09", "high"),
    ("Post-COVID recovery", "2021-01", "2021-06", "moderate"),
    ("Inflation peak",      "2022-06", "2022-12", "high"),
    ("US rate shock",       "2023-01", "2023-06", "moderate"),
]

# Calm/baseline periods — economy performing normally
CALM_PERIODS = [
    ("Pre-COVID expansion", "2017-01", "2019-12"),
    ("Post-inflation norm", "2024-01", "2024-12"),
]


# ── Score with arbitrary weights ──────────────────────────────────────────────

def score_with_weights(scored_df: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    """
    Compute vulnerability scores for all months using a given weight vector.
    Weight order must match VULNERABILITY_COMPONENTS order.

    Args:
        scored_df: DataFrame with z-score columns already computed
        weights:   Array of weights summing to 1.0, one per component

    Returns:
        Series of vulnerability scores indexed by date
    """
    cols = list(VULNERABILITY_COMPONENTS.keys())
    directions = [v[1] for v in VULNERABILITY_COMPONENTS.values()]

    weighted_scores = []
    weight_available = []

    for col, direction, weight in zip(cols, directions, weights):
        zscore_col = f"{col}_zscore"
        if zscore_col not in scored_df.columns:
            continue

        z = scored_df[zscore_col].clip(-3, 3)
        raw_stress = (z + 3) / 6 * 100
        stress = (100 - raw_stress) if direction == "negative" else raw_stress

        weighted_scores.append(stress * weight)
        weight_available.append((~stress.isna()).astype(float) * weight)

    score_sum  = pd.concat(weighted_scores, axis=1).sum(axis=1, skipna=True)
    weight_sum = pd.concat(weight_available, axis=1).sum(axis=1)

    scores = np.where(weight_sum >= 0.3, score_sum / weight_sum, np.nan)
    return pd.Series(scores, index=scored_df.index)


# ── Backtest evaluation ───────────────────────────────────────────────────────

def evaluate_weights(scored_df: pd.DataFrame, weights: np.ndarray) -> dict:
    """
    Score all months and evaluate how well the weights separate stress from calm.

    Returns dict with:
        scores          — full time series of scores
        stress_mean     — mean score during high-stress periods
        calm_mean       — mean score during calm periods
        separation      — stress_mean - calm_mean (higher = better)
        stress_detail   — per-period breakdown
    """
    scores = score_with_weights(scored_df, weights)

    stress_scores = []
    calm_scores   = []
    stress_detail = []

    for label, start, end, severity in STRESS_PERIODS:
        mask = (scores.index >= start) & (scores.index <= end)
        period_scores = scores[mask].dropna()
        if not period_scores.empty:
            mean_score = period_scores.mean()
            stress_scores.extend(period_scores.tolist())
            stress_detail.append({
                "period":     label,
                "severity":   severity,
                "start":      start,
                "end":        end,
                "mean_score": round(mean_score, 1),
                "max_score":  round(period_scores.max(), 1),
                "months":     len(period_scores),
            })

    for label, start, end in CALM_PERIODS:
        mask = (scores.index >= start) & (scores.index <= end)
        period_scores = scores[mask].dropna()
        calm_scores.extend(period_scores.tolist())

    stress_mean = np.mean(stress_scores) if stress_scores else 0
    calm_mean   = np.mean(calm_scores)   if calm_scores   else 0
    separation  = stress_mean - calm_mean

    return {
        "scores":       scores,
        "stress_mean":  round(stress_mean, 1),
        "calm_mean":    round(calm_mean, 1),
        "separation":   round(separation, 1),
        "stress_detail": stress_detail,
    }


# ── Weight optimizer ──────────────────────────────────────────────────────────

def optimize_weights(scored_df: pd.DataFrame, current_weights: np.ndarray) -> np.ndarray:
    """
    Find weights that maximize stress/calm separation using scipy minimize.

    Constraints:
        - All weights >= 0.03 (no indicator completely ignored)
        - All weights <= 0.40 (no single indicator dominates)
        - Weights sum to 1.0
        - Each weight stays within 2x or 0.5x of its current value
          (prevents wild departures from domain knowledge)

    Returns optimized weight array in VULNERABILITY_COMPONENTS order.
    """
    n = len(current_weights)

    def objective(w):
        # Minimize negative separation (= maximize separation)
        result = evaluate_weights(scored_df, w)
        return -result["separation"]

    # Constraints: weights sum to 1
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    # Bounds: each weight between 0.03 and 0.40,
    # and within 2x / 0.5x of current value
    bounds = []
    for w in current_weights:
        lo = max(0.03, w * 0.5)
        hi = min(0.40, w * 2.0)
        bounds.append((lo, hi))

    result = minimize(
        objective,
        x0=current_weights,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-9},
    )

    if not result.success:
        print(f"  WARNING: Optimizer did not fully converge: {result.message}")

    # Normalize to sum exactly to 1.0
    optimized = np.abs(result.x)
    optimized = optimized / optimized.sum()
    return optimized


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="DR Vulnerability Score Backtest")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply optimized weights to build_vulnerability.py after confirmation"
    )
    args = parser.parse_args()

    print("Loading scored data from data/processed/vulnerability_scored.csv...")
    try:
        scored_df = pd.read_csv(
            "data/processed/vulnerability_scored.csv",
            index_col=0,
            parse_dates=True
        )
        scored_df.index = pd.to_datetime(scored_df.index)
    except FileNotFoundError:
        print("ERROR: Run run_pipeline.py first to generate vulnerability_scored.csv")
        sys.exit(1)

    # Current weights in VULNERABILITY_COMPONENTS order
    current_weights = np.array([v[0] for v in VULNERABILITY_COMPONENTS.values()])
    component_names = list(VULNERABILITY_COMPONENTS.keys())

    print(f"Loaded {len(scored_df)} months of scored data "
          f"({scored_df.index.min().date()} to {scored_df.index.max().date()})\n")

    # ── Evaluate current weights ──
    print("=" * 54)
    print("  CURRENT WEIGHTS BACKTEST")
    print("=" * 54)
    current_eval = evaluate_weights(scored_df, current_weights)

    print(f"\nStress period performance:")
    for d in current_eval["stress_detail"]:
        flag = "HIGH" if d["severity"] == "high" else "MOD "
        print(f"  [{flag}] {d['period']:<25} "
              f"mean={d['mean_score']:>5.1f}  max={d['max_score']:>5.1f}  "
              f"({d['months']} months)")

    print(f"\nSummary:")
    print(f"  Stress period mean score: {current_eval['stress_mean']}")
    print(f"  Calm period mean score:   {current_eval['calm_mean']}")
    print(f"  Separation:               {current_eval['separation']} points")

    if current_eval["separation"] < 10:
        print("\n  WARNING: Separation < 10 points. Model struggles to distinguish"
              " stress from normal conditions. Optimization strongly recommended.")
    elif current_eval["separation"] < 20:
        print("\n  NOTE: Moderate separation. Optimization may improve signal quality.")
    else:
        print("\n  OK: Good stress/calm separation.")

    # ── Optimize weights ──
    print(f"\n{'='*54}")
    print("  OPTIMIZING WEIGHTS")
    print("=" * 54)
    print("  Constraints: each weight 0.03-0.40, within 2x of current,")
    print("  sum = 1.0\n")

    optimized_weights = optimize_weights(scored_df, current_weights)
    optimized_eval    = evaluate_weights(scored_df, optimized_weights)

    print("Optimized weight performance:")
    for d in optimized_eval["stress_detail"]:
        flag = "HIGH" if d["severity"] == "high" else "MOD "
        print(f"  [{flag}] {d['period']:<25} "
              f"mean={d['mean_score']:>5.1f}  max={d['max_score']:>5.1f}  "
              f"({d['months']} months)")

    print(f"\nSummary:")
    print(f"  Stress period mean score: {optimized_eval['stress_mean']}")
    print(f"  Calm period mean score:   {optimized_eval['calm_mean']}")
    print(f"  Separation:               {optimized_eval['separation']} points")
    improvement = optimized_eval["separation"] - current_eval["separation"]
    print(f"  Improvement:              +{improvement:.1f} points")

    # ── Weight comparison table ──
    print(f"\n{'='*54}")
    print("  WEIGHT COMPARISON")
    print("=" * 54)
    print(f"\n  {'Indicator':<28} {'Current':>8} {'Optimized':>10} {'Change':>8}")
    print(f"  {'-'*28} {'-'*8} {'-'*10} {'-'*8}")
    for name, curr, opt in zip(component_names, current_weights, optimized_weights):
        change = opt - curr
        arrow  = "+" if change > 0.005 else ("-" if change < -0.005 else " ")
        print(f"  {name:<28} {curr*100:>7.1f}%  {opt*100:>8.1f}%  "
              f"  {arrow}{abs(change)*100:.1f}%")

    # ── Apply decision ──
    print(f"\n{'='*54}")

    if not args.apply:
        print("\n  To apply these weights, run:")
        print("  python pipeline/backtest_weights.py --apply")
        print("\n  Review the weight changes above before applying.")
        return

    # Require explicit confirmation even with --apply flag
    print("\n  Apply optimized weights to build_vulnerability.py?")
    print("  This will modify VULNERABILITY_COMPONENTS in place.")
    confirm = input("  Type 'yes' to confirm: ").strip().lower()

    if confirm != "yes":
        print("  Aborted. No changes made.")
        return

    # Write updated weights back to build_vulnerability.py
    _apply_weights(component_names, optimized_weights)
    print("\n  Weights updated in pipeline/build_vulnerability.py")
    print("  Run run_pipeline.py to generate a new report with updated weights.")


def _apply_weights(names: list, weights: np.ndarray) -> None:
    """
    Update VULNERABILITY_COMPONENTS weights in build_vulnerability.py.
    Rewrites only the weight values, preserving stress direction and comments.
    """
    bv_path = Path("pipeline/build_vulnerability.py")
    source  = bv_path.read_text(encoding="utf-8")

    weight_map = dict(zip(names, weights))

    lines     = source.splitlines()
    new_lines = []
    in_block  = False

    for line in lines:
        if "VULNERABILITY_COMPONENTS" in line and "=" in line and "{" in line:
            in_block = True

        if in_block:
            for col_name, new_weight in weight_map.items():
                # Match lines like:  "    "remesas_usd_mm":   (0.20, "negative"),"
                if f'"{col_name}"' in line and "(" in line:
                    import re
                    line = re.sub(
                        r'\((\d+\.\d+),',
                        f'({new_weight:.2f},',
                        line
                    )
                    break

        new_lines.append(line)

        if in_block and line.strip() == "}":
            in_block = False

    bv_path.write_text("\n".join(new_lines), encoding="utf-8")


if __name__ == "__main__":
    main()