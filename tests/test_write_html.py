"""
Tests for the dashboard-card classification logic in pipeline/write_html.py.

These exist to lock in -- and then prove the fix for -- the documented gap where
count_indicator_statuses() and build_indicator_cards() hand-roll their own
is_stress/is_watch logic instead of calling classify_indicator(), the project's
single source of truth (see build_vulnerability.py module docstring). Before the
fix, neither function honors the LEVEL_THRESHOLDS absolute overrides
(ipc_yoy_pct, dop_usd, UMCSENT) or the gas_premium_dop MoM override, and
build_indicator_cards()'s z-score bar width is inverted for "negative"-direction
indicators. Each test below is written to FAIL against the pre-fix code and PASS
once both functions call classify_indicator().

Run with:
    pytest tests/test_write_html.py -v
"""

import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.build_vulnerability import (
    VULNERABILITY_COMPONENTS,
    GAS_MOM_THRESHOLD_DOP,
    classify_indicator,
)
from pipeline.write_html import count_indicator_statuses, build_indicator_cards


# Calm, non-stressed default raw values for every scored component, paired with
# a neutral zscore of 0.0. None of these breach any LEVEL_THRESHOLDS boundary.
_CALM_VALUES = {
    "remesas_usd_mm": 1000.0,
    "ipc_yoy_pct": 4.0,
    "dop_usd": 60.0,
    "reserves_usd_mm": 5000.0,
    "imae_index": 3.0,
    "sb_morosidad_pct": 2.0,
    "sb_solvencia_pct": 15.0,
    "UNRATE": 4.0,
    "UMCSENT": 70.0,
    "sb_tasa_activa_pct": 10.0,
    "gas_premium_dop": 290.0,
    "tourism_daily_spend_usd": 150.0,
}


def _make_scored(overrides=None, prior_overrides=None) -> pd.DataFrame:
    """
    Two-row synthetic 'scored' frame (prior month, current month) with every
    VULNERABILITY_COMPONENTS column + its _zscore column present and calm.
    `overrides` patches the current (last) row; `prior_overrides` patches the
    prior row (needed for gas_premium_dop's month-over-month override).
    """
    overrides = overrides or {}
    prior_overrides = prior_overrides or {}
    idx = pd.to_datetime(["2026-04-01", "2026-05-01"])
    data = {}
    for col in VULNERABILITY_COMPONENTS:
        prior_val = prior_overrides.get(col, _CALM_VALUES[col])
        cur_val, cur_z = overrides.get(col, (_CALM_VALUES[col], 0.0))
        data[col] = [prior_val, cur_val]
        data[f"{col}_zscore"] = [0.0, cur_z]
    return pd.DataFrame(data, index=idx)


class TestLevelThresholdOverridesWired:
    """LEVEL_THRESHOLDS must force stress even when the z-score alone wouldn't."""

    def test_ipc_yoy_level_override_counted_as_stress(self):
        # Mild z-score (0.3, well under the 1.5 stress band) but value >= 7.0%.
        scored = _make_scored(overrides={"ipc_yoy_pct": (7.5, 0.3)})
        stress, watch, normal = count_indicator_statuses(scored)
        assert stress >= 1, "ipc_yoy_pct >= 7.0% must count as stress regardless of z-score"

    def test_ipc_yoy_level_override_rendered_as_alerta(self):
        scored = _make_scored(overrides={"ipc_yoy_pct": (7.5, 0.3)})
        html = build_indicator_cards(scored)
        card = html.split('data-status="')[1:]
        ipc_card = next(c for c in html.split("indicator-card") if "Inflaci" in c)
        assert 'data-status="stress"' in ipc_card
        assert "ALERTA" in ipc_card

    def test_dop_usd_level_override_counted_as_stress(self):
        # Mild z-score but value >= 65.0.
        scored = _make_scored(overrides={"dop_usd": (66.0, 0.2)})
        stress, watch, normal = count_indicator_statuses(scored)
        assert stress >= 1, "dop_usd >= 65.0 must count as stress regardless of z-score"

    def test_umcsent_level_override_counted_as_stress(self):
        # Mild z-score but value <= 60.0 (UMCSENT direction is "negative").
        scored = _make_scored(overrides={"UMCSENT": (55.0, -0.2)})
        stress, watch, normal = count_indicator_statuses(scored)
        assert stress >= 1, "UMCSENT <= 60.0 must count as stress regardless of z-score"


class TestGasMomOverrideWired:
    """gas_premium_dop's absolute MoM override must fire even with a mild z-score."""

    def test_gas_mom_jump_counted_as_stress(self):
        # Prior month flat at 290.0, current month jumps +14.5 (>= GAS_MOM_THRESHOLD_DOP),
        # but the rolling z-score is mild (0.4, under the 1.5 stress band) -- exactly the
        # scenario GAS_MOM_THRESHOLD_DOP exists to catch.
        assert 14.5 >= GAS_MOM_THRESHOLD_DOP
        scored = _make_scored(
            overrides={"gas_premium_dop": (304.5, 0.4)},
            prior_overrides={"gas_premium_dop": 290.0},
        )
        stress, watch, normal = count_indicator_statuses(scored)
        assert stress >= 1, "gas_premium_dop MoM jump >= threshold must count as stress"

    def test_gas_mom_jump_rendered_as_alerta(self):
        scored = _make_scored(
            overrides={"gas_premium_dop": (304.5, 0.4)},
            prior_overrides={"gas_premium_dop": 290.0},
        )
        html = build_indicator_cards(scored)
        gas_card = next(c for c in html.split("indicator-card") if "Gasolina" in c)
        assert 'data-status="stress"' in gas_card
        assert "ALERTA" in gas_card


class TestBarWidthDirectionAware:
    """
    build_indicator_cards()'s z-score bar must represent stress magnitude
    consistently regardless of the indicator's configured direction.
    """

    def test_negative_direction_severe_stress_renders_large_bar(self):
        # reserves_usd_mm is direction="negative": a strongly NEGATIVE z-score
        # is the stressed case. The bar must be large (it's currently inverted
        # and renders small/looks-fine for this exact case).
        weight, direction = VULNERABILITY_COMPONENTS["reserves_usd_mm"]
        assert direction == "negative"
        scored = _make_scored(overrides={"reserves_usd_mm": (3000.0, -2.5)})
        expected = classify_indicator("reserves_usd_mm", 3000.0, -2.5)["contribution"] * 100
        assert expected > 80, "sanity: classify_indicator should report severe stress here"

        html = build_indicator_cards(scored)
        card = next(c for c in html.split("indicator-card") if "Reservas" in c)
        m = re.search(r"width:([\d.]+)%", card)
        assert m, "expected a zscore-bar width in the rendered card"
        rendered_pct = float(m.group(1))
        assert rendered_pct > 80, (
            f"reserves_usd_mm z=-2.5 (severe stress) should render a large bar, "
            f"got {rendered_pct}% (expected close to {expected:.1f}%)"
        )


class TestCountMatchesClassifyIndicator:
    """
    count_indicator_statuses()'s totals must agree with independently calling
    classify_indicator() on every component -- the project's documented
    'can never disagree' invariant.
    """

    def test_totals_match_classify_indicator_for_all_components(self):
        overrides = {
            "remesas_usd_mm": (800.0, -1.8),     # negative direction, stress
            "ipc_yoy_pct": (5.0, 1.0),            # positive direction, watch
            "dop_usd": (61.0, 0.5),               # normal
            "sb_morosidad_pct": (4.0, 1.6),       # positive direction, stress
        }
        scored = _make_scored(overrides=overrides)

        expected_stress = expected_watch = expected_normal = 0
        for col, (weight, direction) in VULNERABILITY_COMPONENTS.items():
            val, z = overrides.get(col, (_CALM_VALUES[col], 0.0))
            mom = None
            if col == "gas_premium_dop":
                mom = val - _CALM_VALUES[col]
            result = classify_indicator(col, val, z, mom_delta=mom)
            if result["is_stress"]:
                expected_stress += 1
            elif result["is_watch"]:
                expected_watch += 1
            else:
                expected_normal += 1

        stress, watch, normal = count_indicator_statuses(scored)
        assert (stress, watch, normal) == (expected_stress, expected_watch, expected_normal)
