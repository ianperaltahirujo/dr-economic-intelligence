"""
DR Economic Intelligence - Weekly HTML Report Generator
Produces a professional Spanish-language website from pipeline results.
Output: docs/index.html (served by GitHub Pages)

Design: Dominican flag palette (white/black + DR blue #002D62 / DR red #CE1126)
Typography: IBM Plex Sans + IBM Plex Mono
Audience: La Sociedad management (non-technical)
Language: Spanish throughout

This module only builds the presentation layer. Every figure shown is read
straight from the pipeline result DataFrames, so the report always reflects
the latest scoring run without any manual editing.
"""

import sys
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.build_vulnerability import (
    VULNERABILITY_COMPONENTS,
    INDICATOR_LABELS,
    HIGH_STRESS_THRESHOLD,
    MODERATE_STRESS_THRESHOLD,
    classify_indicator,
    gas_mom_for,
)

# ── Hero lockup ──────────────────────────────────────────────
# "La Sociedad" wordmark served as vector (crisp at any resolution); the
# "DR Economic Intelligence" tagline is set in our own Reckless webfont below
# it. The looping chart-line video sits behind the lockup as a banner.
HERO_LOGO_SVG_SRC = "https://cdn.prod.website-files.com/66019da45405261eac2c08e8/660d5dbe7af23fb39d85e2ec_horizontal-logo-berlinblue.svg"
HERO_VIDEO_SRC = "assets/hero-bg.mp4"

# ── Spanish content ────────────────────────────────────────────────────────────

INDICATOR_DESCRIPTIONS_ES = {
    "remesas_usd_mm": (
        "Remesas familiares",
        "Transferencias de dinero enviadas desde el exterior hacia la República Dominicana. "
        "Una caída sostenida indica menor ingreso de divisas y presión sobre el consumo interno."
    ),
    "ipc_yoy_pct": (
        "Inflación interanual",
        "Variación porcentual del nivel de precios respecto al mismo mes del año anterior. "
        "Valores por encima del 6% indican presión inflacionaria significativa."
    ),
    "dop_usd": (
        "Tasa de cambio DOP/USD",
        "Pesos dominicanos por cada dólar estadounidense. "
        "Una depreciación acelerada del peso encarece las importaciones y presiona la inflación."
    ),
    "reserves_usd_mm": (
        "Reservas internacionales",
        "Activos en moneda extranjera del Banco Central. "
        "Constituyen el colchón de seguridad ante choques externos. Valores bajos reducen la capacidad de respuesta."
    ),
    "imae_index": (
        "Actividad económica (IMAE)",
        "Índice Mensual de Actividad Económica. Mide el pulso de la economía dominicana incluyendo turismo, "
        "manufactura y servicios. Una caída sostenida anticipa contracción económica."
    ),
    "sb_morosidad_pct": (
        "Morosidad bancaria",
        "Porcentaje de préstamos en mora sobre la cartera total del sistema bancario. "
        "Un aumento indica deterioro en la capacidad de pago de hogares y empresas."
    ),
    "sb_solvencia_pct": (
        "Solvencia bancaria",
        "Índice de adecuación de capital del sistema bancario. "
        "Refleja la capacidad del sistema financiero de absorber pérdidas. Valores altos son positivos."
    ),
    "UNRATE": (
        "Desempleo en EE.UU.",
        "Tasa de desempleo en los Estados Unidos. Un alza sostenida reduce los ingresos de la diáspora dominicana "
        "y presiona a la baja las remesas hacia el país."
    ),
    "UMCSENT": (
        "Confianza del consumidor en EE.UU.",
        "Índice de confianza del consumidor estadounidense (Universidad de Michigan). "
        "Una caída anticipa menor gasto en turismo hacia el Caribe, incluyendo la República Dominicana."
    ),
}

STATUS_TEXT_ES = {
    "HIGH":     ("ESTRÉS ALTO",    "El índice supera el umbral de alerta. Múltiples indicadores muestran presión simultánea."),
    "MODERATE": ("ESTRÉS MODERADO","Condiciones por encima del promedio histórico. Se recomienda seguimiento cercano."),
    "LOW":      ("CONDICIONES NORMALES", "Los indicadores se encuentran dentro de rangos históricos normales."),
}

MONTHS_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}


# ── Template briefing generator ────────────────────────────────────────────────

def generate_briefing(results: dict, scored: pd.DataFrame) -> str:
    score      = results.get("current_score", 0)
    score_date = results.get("score_date")
    alerts     = results.get("alerts", pd.DataFrame())

    if score_date:
        date_str = f"{MONTHS_ES[score_date.month]} de {score_date.year}"
    else:
        date_str = "el período más reciente"

    paragraphs = []

    if score >= HIGH_STRESS_THRESHOLD:
        opening = (
            f"El Índice de Vulnerabilidad Económica de la República Dominicana registró "
            f"<strong>{score:.1f} puntos</strong> en {date_str}, superando el umbral de alerta de "
            f"{HIGH_STRESS_THRESHOLD} puntos. Este nivel refleja presiones simultáneas en múltiples "
            f"frentes que merecen atención prioritaria."
        )
    elif score >= MODERATE_STRESS_THRESHOLD:
        opening = (
            f"El Índice de Vulnerabilidad Económica de la República Dominicana se situó en "
            f"<strong>{score:.1f} puntos</strong> en {date_str}, indicando condiciones de estrés "
            f"moderado. Varios indicadores se encuentran por encima de sus promedios históricos recientes, "
            f"aunque sin alcanzar niveles de alarma."
        )
    else:
        opening = (
            f"El Índice de Vulnerabilidad Económica de la República Dominicana se ubicó en "
            f"<strong>{score:.1f} puntos</strong> en {date_str}, dentro de rangos históricos normales. "
            f"Los principales indicadores macroeconómicos y financieros muestran estabilidad relativa."
        )
    paragraphs.append(opening)

    drivers = []
    if not alerts.empty:
        stress_alerts = alerts[alerts["is_stress"] == True]
        for _, alert in stress_alerts.iterrows():
            col = alert["indicator"]
            val = alert["value"]
            if col == "ipc_yoy_pct":
                drivers.append(f"la inflación interanual se mantiene en <strong>{val:.1f}%</strong>, por encima del promedio de los últimos cinco años")
            elif col == "dop_usd":
                drivers.append(f"el tipo de cambio alcanzó <strong>{val:.2f} DOP/USD</strong>, reflejando presión depreciatoria sobre el peso dominicano")
            elif col == "remesas_usd_mm":
                drivers.append(f"las remesas familiares totalizaron <strong>USD {val:.0f} millones</strong>, por debajo de su tendencia reciente")
            elif col == "sb_morosidad_pct":
                drivers.append(f"la morosidad bancaria se ubicó en <strong>{val:.2f}%</strong>, señalando deterioro en la calidad de la cartera de crédito")
            elif col == "UNRATE":
                drivers.append(f"el desempleo en EE.UU. subió a <strong>{val:.1f}%</strong>, lo que podría reducir el flujo de remesas hacia el país")
            elif col == "UMCSENT":
                drivers.append(f"la confianza del consumidor estadounidense cayó a <strong>{val:.1f} puntos</strong>, anticipando posible reducción en el turismo hacia la región")
            elif col == "reserves_usd_mm":
                drivers.append(f"las reservas internacionales se situaron en <strong>USD {val:,.0f} millones</strong>, por debajo de niveles óptimos")

    if drivers:
        paragraphs.append("Los principales factores que explican este resultado son: " + "; ".join(drivers) + ".")
    else:
        paragraphs.append("No se identificaron indicadores fuera de sus rangos históricos normales durante este período. La economía dominicana muestra resiliencia ante el entorno internacional.")

    recent = scored[list(VULNERABILITY_COMPONENTS.keys())].dropna(how="all").tail(1)
    if not recent.empty:
        context_parts = []
        if "remesas_usd_mm" in recent.columns and pd.notna(recent["remesas_usd_mm"].iloc[0]):
            context_parts.append(f"las remesas se mantienen en USD {recent['remesas_usd_mm'].iloc[0]:.0f} millones mensuales")
        if "sb_morosidad_pct" in recent.columns and pd.notna(recent["sb_morosidad_pct"].iloc[0]):
            mor_val = recent["sb_morosidad_pct"].iloc[0]
            if mor_val < 2.5:
                context_parts.append(f"la morosidad bancaria permanece contenida en {mor_val:.2f}%")
        if "sb_solvencia_pct" in recent.columns and pd.notna(recent["sb_solvencia_pct"].iloc[0]):
            sol_val = recent["sb_solvencia_pct"].iloc[0]
            if sol_val > 15:
                context_parts.append(f"el sistema bancario mantiene sólidos niveles de capitalización ({sol_val:.1f}%)")
        if context_parts:
            paragraphs.append("Entre los factores de estabilidad destacan que " + " y ".join(context_parts) + ".")

    paragraphs.append("Este informe es generado automáticamente cada semana por el sistema de inteligencia económica de La Sociedad a partir de fuentes oficiales: Banco Central de la República Dominicana (BCRD), Superintendencia de Bancos (SB) y la Reserva Federal de EE.UU. (FRED).")

    return "</p><p>".join(f"{p}" for p in paragraphs)


# ── Chart data builder ─────────────────────────────────────────────────────────

MIN_ESTIMATE_COMPONENTS = 2  # at least this many indicators must be present;
                              # a single indicator can swing the renormalized
                              # score to 0 or 100 on its own, which is not a
                              # meaningful reading, just division by a tiny
                              # weight. Two or more indicators means the
                              # score reflects at least some averaging.


def _renormalized_estimate(row: pd.Series) -> tuple[float, float, int] | None:
    """
    Display-only partial-coverage score for the historical chart, used only
    for months before full 12-indicator coverage exists. Sums
    weighted_score across whichever components have both a value and a
    z-score that month, then divides by the sum of weights actually in
    play (not 1.0), keeping the result on a 0-100 scale. This number is
    never written back into the scored DataFrame's vulnerability_score
    and never feeds any other output; it exists solely to give the
    "Historial completo del índice" chart a longer visual run, clearly
    marked as estimated.

    Renormalizing over a tiny available-weight subset is structurally
    unstable: with only 1 indicator present, that single indicator
    determines the entire renormalized score, since dividing its
    weighted_score by its own weight just returns its raw contribution
    (0 to 1) directly as the score. Confirmed on real data: a single
    indicator hitting a level-threshold override produced a 100/100
    reading driven by one input, with zero averaging from anything else.
    Requiring at least MIN_ESTIMATE_COMPONENTS indicators ensures the
    score reflects more than one input's behavior, even though the
    weighting across those few indicators is still renormalized (and
    therefore still more volatile than a full 12-indicator reading).

    Returns (score, weight_available, n_components_available) or None if
    fewer than MIN_ESTIMATE_COMPONENTS indicators are available that month.
    """
    total_weighted = 0.0
    total_weight_available = 0.0
    n_available = 0
    for col, (weight, direction) in VULNERABILITY_COMPONENTS.items():
        z_col = f"{col}_zscore"
        if z_col in row.index and not pd.isna(row.get(z_col)) and not pd.isna(row.get(col)):
            classification = classify_indicator(col, row[col], row[z_col])
            total_weighted += classification["weighted_score"]
            total_weight_available += weight
            n_available += 1
    if n_available < MIN_ESTIMATE_COMPONENTS:
        return None
    score = total_weighted / total_weight_available
    return score, total_weight_available, n_available


def build_chart_data(scored: pd.DataFrame) -> str:
    """
    Build the history-chart series in a single chronological pass, so the
    line is never torn open by a month that merely lacks ONE indicator.

    Each month is classified on its own:
      * REAL (solid): has a full 12-indicator vulnerability_score. If that
        score rode a forward-filled tourism value it is still real, just
        flagged provisional so the UI dashes it ("Avance Estimado").
      * ESTIMATED (dashed, lighter): no full-coverage score, but at least
        MIN_ESTIMATE_COMPONENTS indicators are present that month. Shows the
        renormalized partial estimate, tagged with how many indicators it
        used. This now covers BOTH deep history (before all 12 series begin)
        AND any later month where a single source lagged.
      * SKIPPED: fewer than MIN_ESTIMATE_COMPONENTS indicators present.

    The previous version estimated ONLY months strictly before the first
    real score, then dropped every later month without full coverage. A
    single missing indicator therefore punched a hole in the line: dop_usd
    absent in Ago 2019, imae_index absent across 2022, UNRATE absent in
    Oct 2025 each erased an otherwise-11-of-12 month. Estimates here stay
    display-only: never written to vulnerability_score, never fed to any
    other output, always labeled with their real coverage count.
    """
    scored = scored.sort_index()
    has_score_col = "vulnerability_score" in scored.columns
    has_prov_col = "is_provisional" in scored.columns
    full_n = len(VULNERABILITY_COMPONENTS)

    labels, values, colors, provisional, estimated, coverage_n, point_alpha = [], [], [], [], [], [], []

    # Confidence scaling for estimated points: a month with full available
    # weight renders close to solid opacity; a sparse month renders much
    # lighter, so visual weight tracks how much of the index was actually
    # available rather than asserting equal confidence everywhere. Floor
    # kept above 0 so even the thinnest months remain visible.
    MIN_ALPHA, MAX_ALPHA = 0.25, 0.85

    for idx in scored.index:
        row = scored.loc[idx]
        label = f"{MONTHS_ES[idx.month].capitalize()} {idx.year}"
        score_val = row["vulnerability_score"] if has_score_col else None

        # ── Full-coverage real point ──────────────────────────────────────
        if score_val is not None and pd.notna(score_val):
            v = round(float(score_val), 1)
            labels.append(label)
            values.append(v)
            if v >= HIGH_STRESS_THRESHOLD:
                colors.append("rgba(206,17,38,0.8)")
            elif v >= MODERATE_STRESS_THRESHOLD:
                colors.append("rgba(0,45,98,0.6)")
            else:
                colors.append("rgba(0,45,98,0.3)")
            provisional.append(bool(row["is_provisional"]) if has_prov_col else False)
            estimated.append(False)
            coverage_n.append(full_n)
            point_alpha.append(1.0)
            continue

        # ── Partial-coverage estimated point (display-only) ───────────────
        est = _renormalized_estimate(row)
        if est is None:
            continue  # fewer than MIN_ESTIMATE_COMPONENTS indicators -- skip
        score, weight_available, n_available = est
        v = round(score, 1)
        alpha = MIN_ALPHA + (MAX_ALPHA - MIN_ALPHA) * min(1.0, weight_available)
        labels.append(label)
        values.append(v)
        if v >= HIGH_STRESS_THRESHOLD:
            colors.append(f"rgba(206,17,38,{alpha:.2f})")
        elif v >= MODERATE_STRESS_THRESHOLD:
            colors.append(f"rgba(0,45,98,{alpha:.2f})")
        else:
            colors.append(f"rgba(0,45,98,{alpha*0.6:.2f})")
        provisional.append(False)
        estimated.append(True)
        coverage_n.append(n_available)
        point_alpha.append(round(alpha, 2))

    return json.dumps({
        "labels": labels,
        "values": values,
        "colors": colors,
        "provisional": provisional,
        "estimated": estimated,
        "coverageN": coverage_n,
        "pointAlpha": point_alpha,
    })


# ── Context Cards Builder ──────────────────────────────────────────────────────

def get_sparkline_data(df, col, n=24):
    if df is None or df.empty or col not in df.columns:
        return "[]"
    vals = df[col].dropna().tail(n).tolist()
    return json.dumps([round(v, 2) for v in vals])


def build_context_cards(results: dict) -> str:
    cards = []
    gas            = results.get("gas", pd.DataFrame())
    tourism_spend  = results.get("tourism_spend", pd.DataFrame())
    tourism_fiscal = results.get("tourism_fiscal", pd.DataFrame())
    debt           = results.get("debt_detail", pd.DataFrame())

    # 1. Combustibles
    if not gas.empty:
        recent_gas = gas.dropna(subset=["gas_premium_dop"]).tail(13)
        if not recent_gas.empty:
            val_prem   = recent_gas["gas_premium_dop"].iloc[-1]
            val_reg    = recent_gas["gas_regular_dop"].iloc[-1]
            spark_prem = get_sparkline_data(gas, "gas_premium_dop")
            spark_reg  = get_sparkline_data(gas, "gas_regular_dop")
            prem_delta = val_prem - recent_gas["gas_premium_dop"].iloc[-2] if len(recent_gas) >= 2 else 0
            reg_delta  = val_reg  - recent_gas["gas_regular_dop"].iloc[-2]  if len(recent_gas) >= 2 else 0
            prem_12m   = recent_gas["gas_premium_dop"].tail(12).mean()
            cards.append(f"""
            <div class="context-card interactive-card" data-group="context-group" onclick="toggleAccordion(this)">
                <div class="card-header">
                    <span class="card-label">Precios Combustibles (DOP)</span>
                    <span class="dropdown-arrow" aria-hidden="true">&#9660;</span>
                </div>
                <div class="context-item">
                    <div class="ci-info"><span class="ci-label">Gasolina Premium</span><span class="ci-value">{val_prem:.1f}</span></div>
                    <div class="ci-chart"><canvas class="sparkline" data-chart='{spark_prem}'></canvas></div>
                </div>
                <div class="context-item">
                    <div class="ci-info"><span class="ci-label">Gasolina Regular</span><span class="ci-value">{val_reg:.1f}</span></div>
                    <div class="ci-chart"><canvas class="sparkline" data-chart='{spark_reg}'></canvas></div>
                </div>
                <div class="accordion-content">
                    <div class="context-stats">
                        <div class="context-row"><span>Var. mes anterior (Premium):</span> <strong>{prem_delta:+.1f} DOP</strong></div>
                        <div class="context-row"><span>Var. mes anterior (Regular):</span> <strong>{reg_delta:+.1f} DOP</strong></div>
                        <div class="context-row"><span>Promedio 12 meses (Premium):</span> <strong>{prem_12m:.1f} DOP</strong></div>
                    </div>
                    <div class="card-desc context-desc">Precios de referencia fijados por el MICM. Impactan directamente los costos de transporte y logística, incidiendo transversalmente en los precios de la canasta básica y la inflación general.</div>
                </div>
            </div>""")

    # 2. Deuda Pública
    if not debt.empty:
        recent_debt = debt.dropna(subset=["debt_total_usd_mm"]).tail(6)
        if not recent_debt.empty:
            val_total   = recent_debt["debt_total_usd_mm"].iloc[-1]
            val_ext     = recent_debt["debt_external_usd_mm"].iloc[-1]
            val_int     = recent_debt["debt_internal_usd_mm"].iloc[-1]
            val_pct_gdp = recent_debt["debt_total_pct_gdp"].iloc[-1] * 100
            spark_total = get_sparkline_data(debt, "debt_total_usd_mm", n=20)
            spark_ext   = get_sparkline_data(debt, "debt_external_usd_mm", n=20)
            cards.append(f"""
            <div class="context-card interactive-card" data-group="context-group" onclick="toggleAccordion(this)">
                <div class="card-header">
                    <span class="card-label">Deuda Pública Consolidada</span>
                    <span class="dropdown-arrow" aria-hidden="true">&#9660;</span>
                </div>
                <div class="context-item">
                    <div class="ci-info"><span class="ci-label">Total (USD mm)</span><span class="ci-value">${val_total:,.0f}M</span></div>
                    <div class="ci-chart"><canvas class="sparkline" data-chart='{spark_total}'></canvas></div>
                </div>
                <div class="context-item">
                    <div class="ci-info"><span class="ci-label">Deuda Externa (USD mm)</span><span class="ci-value">${val_ext:,.0f}M</span></div>
                    <div class="ci-chart"><canvas class="sparkline" data-chart='{spark_ext}'></canvas></div>
                </div>
                <div class="accordion-content">
                    <div class="context-stats">
                        <div class="context-row"><span>Deuda Interna Neta:</span> <strong>${val_int:,.0f}M</strong></div>
                        <div class="context-row"><span>Como % del PIB:</span> <strong>{val_pct_gdp:.1f}%</strong></div>
                    </div>
                    <div class="card-desc context-desc">Deuda consolidada del sector público dominicano. La deuda externa representa el principal componente y genera exposición al riesgo cambiario. Fuente: BCRD (trimestral).</div>
                </div>
            </div>""")

    # 3. Turismo
    if not tourism_spend.empty or not tourism_fiscal.empty:
        items = []
        stats_items = []
        if not tourism_spend.empty:
            recent_spend = tourism_spend.dropna(subset=["tourism_daily_spend_usd"]).tail(13)
            if not recent_spend.empty:
                val_spend   = recent_spend["tourism_daily_spend_usd"].iloc[-1]
                spark_spend = get_sparkline_data(tourism_spend, "tourism_daily_spend_usd", n=12)
                spend_delta = val_spend - recent_spend["tourism_daily_spend_usd"].iloc[-2] if len(recent_spend) >= 2 else 0
                items.append(f"""<div class="context-item"><div class="ci-info"><span class="ci-label">Gasto Diario Promedio</span><span class="ci-value">${val_spend:.1f} USD</span></div><div class="ci-chart"><canvas class="sparkline" data-chart='{spark_spend}'></canvas></div></div>""")
                stats_items.append(f"""<div class="context-row"><span>Var. periodo anterior (Gasto USD):</span> <strong>{spend_delta:+.1f} USD</strong></div>""")
        if not tourism_fiscal.empty:
            recent_fisc = tourism_fiscal.dropna(subset=["tourism_fiscal_rdm"]).tail(13)
            if not recent_fisc.empty:
                val_fisc   = recent_fisc["tourism_fiscal_rdm"].iloc[-1]
                spark_fisc = get_sparkline_data(tourism_fiscal, "tourism_fiscal_rdm", n=24)
                fisc_12m   = recent_fisc["tourism_fiscal_rdm"].tail(12).mean()
                items.append(f"""<div class="context-item"><div class="ci-info"><span class="ci-label">Recaudación Fiscal</span><span class="ci-value">DOP {val_fisc:,.0f}M</span></div><div class="ci-chart"><canvas class="sparkline" data-chart='{spark_fisc}'></canvas></div></div>""")
                stats_items.append(f"""<div class="context-row"><span>Promedio 12 meses (Recaudación):</span> <strong>DOP {fisc_12m:,.0f}M</strong></div>""")
        if items:
            cards.append(f"""
            <div class="context-card interactive-card" data-group="context-group" onclick="toggleAccordion(this)">
                <div class="card-header">
                    <span class="card-label">Sector Turismo</span>
                    <span class="dropdown-arrow" aria-hidden="true">&#9660;</span>
                </div>
                {"".join(items)}
                <div class="accordion-content">
                    <div class="context-stats">{"".join(stats_items)}</div>
                    <div class="card-desc context-desc">El turismo es una de las principales fuentes de divisas de la República Dominicana. Su dinamismo estabiliza el tipo de cambio, aporta liquidez al sistema financiero nacional e impulsa industrias conectadas.</div>
                </div>
            </div>""")

    return "\n".join(cards)


# ── Indicator classification & cards ────────────────────────────────────────────

def count_indicator_statuses(scored: pd.DataFrame):
    """Count indicators in each status band by calling classify_indicator(),
    the project's single source of truth, so this can never disagree with the
    cards, the alerts, or the Excel sheets."""
    stress = watch = normal = 0
    for col in VULNERABILITY_COMPONENTS:
        zscore_col = f"{col}_zscore"
        if col not in scored.columns:
            continue
        recent = scored[[col, zscore_col]].dropna().tail(1)
        if recent.empty:
            continue
        value = recent[col].iloc[0]
        zscore = recent[zscore_col].iloc[0]
        mom = gas_mom_for(scored, recent.index[0]) if col == "gas_premium_dop" else None
        classification = classify_indicator(col, value, zscore, mom_delta=mom)
        if classification["is_stress"]:
            stress += 1
        elif classification["is_watch"]:
            watch += 1
        else:
            normal += 1
    return stress, watch, normal


def build_indicator_cards(scored: pd.DataFrame) -> str:
    cards = []
    for col, (weight, direction) in VULNERABILITY_COMPONENTS.items():
        zscore_col = f"{col}_zscore"
        if col not in scored.columns: continue
        recent = scored[[col, zscore_col]].dropna().tail(1)
        if recent.empty: continue
        value  = recent[col].iloc[0]
        zscore = recent[zscore_col].iloc[0]
        es_label, es_desc = INDICATOR_DESCRIPTIONS_ES.get(col, (INDICATOR_LABELS.get(col, col), ""))
        mom = gas_mom_for(scored, recent.index[0]) if col == "gas_premium_dop" else None
        classification = classify_indicator(col, value, zscore, mom_delta=mom)
        is_stress, is_watch = classification["is_stress"], classification["is_watch"]
        if is_stress:   status_label, status_class, data_status = "ALERTA",    "status-stress", "stress"
        elif is_watch:  status_label, status_class, data_status = "VIGILANCIA","status-watch",  "watch"
        else:           status_label, status_class, data_status = "NORMAL",    "status-normal", "normal"
        if col in ["remesas_usd_mm", "reserves_usd_mm"]: value_str = f"USD {value:,.0f}M"
        elif col == "dop_usd": value_str = f"{value:.2f}"
        elif col in ["ipc_yoy_pct","sb_morosidad_pct","sb_solvencia_pct","UNRATE"]: value_str = f"{value:.2f}%"
        elif col == "UMCSENT": value_str = f"{value:.1f}"
        else: value_str = f"{value:.2f}"
        bar_pct   = classification["contribution"] * 100
        bar_color = "var(--red)" if is_stress else ("var(--blue)" if is_watch else "var(--gray-400)")
        col_history = scored[col].dropna().tail(3)
        if len(col_history) >= 2:
            delta = col_history.iloc[-1] - col_history.iloc[-2]
            if direction == "positive": arrow, arrow_class = ("&#8593;","arrow-bad") if delta > 0 else ("&#8595;","arrow-good")
            else:                       arrow, arrow_class = ("&#8593;","arrow-good") if delta > 0 else ("&#8595;","arrow-bad")
        else:
            arrow, arrow_class = "&#8211;", ""
        cards.append(f"""
        <div class="indicator-card interactive-card {'card-stress' if is_stress else ''}" data-status="{data_status}" onclick="toggleAccordion(this)">
            <div class="card-header">
                <span class="card-label">{es_label}</span>
                <div class="card-header-meta">
                    <span class="status-badge {status_class}">{status_label}</span>
                    <span class="dropdown-arrow" aria-hidden="true">&#9660;</span>
                </div>
            </div>
            <div class="card-value">
                <span class="value-number">{value_str}</span>
                <span class="value-arrow {arrow_class}">{arrow}</span>
            </div>
            <div class="zscore-bar-container"><div class="zscore-bar" style="width:{bar_pct:.1f}%;background:{bar_color};"></div></div>
            <div class="accordion-content">
                <div class="zscore-label">Z-score: {zscore:+.2f} &nbsp;|&nbsp; Peso: {weight*100:.0f}%</div>
                <div class="card-desc">{es_desc}</div>
            </div>
        </div>""")
    return "\n".join(cards)


# ── Alert items ────────────────────────────────────────────────────────────────

def build_alert_items(alerts: pd.DataFrame) -> str:
    if alerts.empty:
        return '''<div class="no-alerts"><span class="no-alerts-icon">&#10003;</span>Ningún indicador supera el umbral de alerta esta semana.</div>'''
    items = []
    for _, alert in alerts.iterrows():
        col   = alert["indicator"]
        label = INDICATOR_DESCRIPTIONS_ES.get(col, (alert.get("label", col), ""))[0]
        is_stress, z, val = alert["is_stress"], alert["zscore"], alert["value"]
        direction_word = "por encima" if z > 0 else "por debajo"
        alert_class, alert_tag = ("alert-stress","ALERTA") if is_stress else ("alert-watch","VIGILANCIA")
        items.append(f"""
        <div class="alert-item {alert_class}">
            <div class="alert-tag">{alert_tag}</div>
            <div class="alert-content">
                <strong>{label}</strong>
                <span class="alert-text">{abs(z):.1f} desviaciones estándar {direction_word} de su promedio histórico (valor actual: {val:.2f})</span>
            </div>
        </div>""")
    return "\n".join(items)


# ── Full HTML ──────────────────────────────────────────────────────────────────

def build_html(results: dict) -> str:
    scored          = results.get("scored", pd.DataFrame())
    confirmed_score = results.get("current_score", 0) or 0
    confirmed_date  = results.get("score_date")
    alerts          = results.get("alerts", pd.DataFrame())

    # The hero shows the current in-progress calendar month (averaged from
    # this month's weekly pipeline runs) when one is available, falling
    # back to the last fully-confirmed month exactly as before this
    # feature existed if it isn't. See current_month_tracker.py /
    # build_vulnerability.estimate_current_month() for why this is
    # explicitly separate from the strict historical score.
    current_estimate = results.get("current_month_estimate")
    if current_estimate is not None:
        score          = current_estimate["averaged_score"]
        score_date     = current_estimate["date"]
        week_of_month  = current_estimate["week_of_month"]
        weeks_recorded = current_estimate["weeks_recorded"]
    else:
        score          = confirmed_score
        score_date     = confirmed_date
        week_of_month  = None
        weeks_recorded = 0

    # Trend: a genuine week-over-week comparison once this month has at
    # least two recorded weekly snapshots. On the first week of a new
    # month's estimate there is no prior week yet, so compare against the
    # last confirmed month instead -- and say so explicitly, rather than
    # mislabeling a vs-last-month comparison as "vs semana anterior".
    # Without an active estimate, fall back to the original month-over-
    # month comparison against confirmed history, unchanged.
    delta = None
    compare_label = "vs semana anterior"
    if current_estimate is not None:
        if weeks_recorded >= 2 and current_estimate.get("prior_week_score") is not None:
            delta = current_estimate["this_week_score"] - current_estimate["prior_week_score"]
        elif confirmed_date is not None:
            delta = current_estimate["this_week_score"] - confirmed_score
            compare_label = f"vs {MONTHS_ES[confirmed_date.month].capitalize()} confirmado"
    else:
        score_history = scored["vulnerability_score"].dropna().tail(2)
        if len(score_history) >= 2:
            delta = score - score_history.iloc[-2]

    if delta is None:
        trend_arrow, trend_class, trend_text = "", "trend-neutral", "Dato base"
    elif delta > 0.05:    trend_arrow, trend_class, trend_text = "&#8593;", "trend-bad",     f"+{delta:.1f} pts {compare_label}"
    elif delta < -0.05:   trend_arrow, trend_class, trend_text = "&#8595;", "trend-good",    f"{delta:.1f} pts {compare_label}"
    else:                 trend_arrow, trend_class, trend_text = "&#8211;","trend-neutral",  f"Sin cambios {compare_label}"

    is_provisional = False
    if current_estimate is None and score_date is not None and "is_provisional" in scored.columns and score_date in scored.index:
        is_provisional = bool(scored.loc[score_date, "is_provisional"])

    status_key   = "HIGH" if score >= HIGH_STRESS_THRESHOLD else ("MODERATE" if score >= MODERATE_STRESS_THRESHOLD else "LOW")
    status_label, status_desc = STATUS_TEXT_ES[status_key]
    score_color  = "#CE1126" if status_key == "HIGH" else "#002D62" if status_key == "MODERATE" else "#1A1A1A"
    date_str     = f"{MONTHS_ES[score_date.month].capitalize()} de {score_date.year}" if score_date else ""
    run_date     = datetime.now().strftime("%d/%m/%Y a las %H:%M")
    meter_pos    = max(0.0, min(100.0, float(score)))

    week_label_html = f" &middot; Semana {week_of_month}" if week_of_month else ""
    # Editorial hero meta-row: trend, current period (with provisional pill
    # when tourism is forward-filled), and -- only when the headline is a
    # current-month estimate -- the last fully confirmed month. Joined by
    # thin dividers.
    _meta_items = [
        f'<span class="editorial-meta-item editorial-meta-trend {trend_class}">{trend_arrow}&nbsp;{trend_text}</span>',
    ]
    _prov_pill = "<span class='provisional-pill'>Avance Estimado</span>" if is_provisional else ""
    _meta_items.append(f'<span class="editorial-meta-item">{date_str}{week_label_html}{_prov_pill}</span>')
    if current_estimate is not None and confirmed_date is not None:
        confirmed_date_str = f"{MONTHS_ES[confirmed_date.month].capitalize()} de {confirmed_date.year}"
        _meta_items.append(
            f'<span class="editorial-meta-item">Confirmado {confirmed_date_str} '
            f'&middot; {confirmed_score:.1f}/100</span>'
        )
    editorial_meta_html = '<span class="editorial-meta-divider"></span>'.join(_meta_items)

    # Disclosure notes below the score block. The tourism-provisional caveat
    # and the current-month estimate methodology line are preserved verbatim
    # from the prior hero so the "Avance Estimado" disclosure is never dropped.
    _notes = []
    if is_provisional:
        _notes.append(
            "<div class='editorial-estimate-note'>* Gasto turístico proyectado. "
            "Se actualizará al publicarse el dato oficial del BCRD.</div>"
        )
    if current_estimate is not None:
        _notes.append(
            '<div class="editorial-estimate-note">Estimación del mes en curso &mdash; '
            'promedio de las lecturas semanales registradas.</div>'
        )
    editorial_notes_html = "\n            ".join(_notes)

    briefing      = generate_briefing(results, scored)
    chart_data    = build_chart_data(scored)
    context_cards = build_context_cards(results)
    cards         = build_indicator_cards(scored)
    alert_html    = build_alert_items(alerts)

    stress_n, watch_n, normal_n = count_indicator_statuses(scored)
    total_n = stress_n + watch_n + normal_n

    alert_count  = len(alerts) if alerts is not None and not alerts.empty else 0

    _alert_class   = "interactive-alert" if stress_n > 0 else ""
    _alert_onclick = 'onclick="jumpFilter(\'stress\')"' if stress_n > 0 else ""
    _plural        = "es" if stress_n != 1 else ""
    _alert_inner   = (f'&#9888; {stress_n} indicador{_plural} en zona de alerta <span class="alert-arrow">&#8595;</span>'
                      if stress_n > 0 else '&#10003; Sin alertas activas')
    alert_box_html = f'''
    <div class="alert-count {_alert_class}" {_alert_onclick}>
        {_alert_inner}
    </div>'''

    context_section_html = ""
    if context_cards:
        context_section_html = f"""
        <section id="contexto-macro">
            <div class="container">
                <div class="section-head"><h2 class="section-label">Contexto Macroeconómico</h2><span class="section-rule"></span></div>
                <p class="section-intro">Indicadores de apoyo que enriquecen la lectura del índice sin formar parte de su cálculo. Toque cada tarjeta para ver el detalle.</p>
                <div class="context-grid">{context_cards}</div>
            </div>
        </section>"""

    context_nav = '<a href="#contexto-macro" class="nav-link">Contexto</a>' if context_section_html else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Informe semanal de vulnerabilidad económica de la República Dominicana — La Sociedad.">
    <meta name="theme-color" content="#002D62">
    <meta name="color-scheme" content="light"><link rel="icon" type="image/png" href="https://cdn.prod.website-files.com/66019da45405261eac2c08e8/660d5e71b70a59f15069d753_Favicon-berlinblue.png">
    <title>DR Economic Intelligence &#8212; La Sociedad</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        @font-face {{
            font-family: 'Haffer';
            src: url('fonts/Haffer-TRIAL-Regular.ttf') format('truetype');
            font-weight: 400;
            font-style: normal;
            font-display: swap;
        }}
        @font-face {{
            font-family: 'Haffer';
            src: url('fonts/Haffer-TRIAL-Bold.otf') format('opentype');
            font-weight: 700;
            font-style: normal;
            font-display: swap;
        }}
        @font-face {{
            font-family: 'Reckless';
            src: url('fonts/RecklessStandardXL-TRIAL-Regular.otf') format('opentype');
            font-weight: 400;
            font-style: normal;
            font-display: swap;
        }}
        @font-face {{
            font-family: 'Reckless';
            src: url('fonts/RecklessStandardM-TRIAL-Bold.otf') format('opentype');
            font-weight: 700;
            font-style: normal;
            font-display: swap;
        }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8/hammer.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        :root {{
            --blue: #002D62; --blue-deep: #013A7D; --red: #CE1126; --black: #0A0A0A; --white: #FFFFFF;
            --gray-50: #F9F9F9; --gray-100: #F0F0F0; --gray-200: #E0E0E0; --gray-300: #D2D2D2;
            --gray-400: #999999; --gray-600: #555555;
            --blue-tint: #EEF2F8; --blue-soft: #CDD9EA; --red-tint: #FDF0F2; --green: #2E7D32;
            --font-sans: 'Haffer', system-ui, sans-serif;
            --font-display: 'Reckless', Georgia, serif;
            --font-mono: 'IBM Plex Mono', monospace;
            --maxw: 1140px; --radius: 14px; --radius-sm: 9px;
            --border: 1px solid var(--gray-200);
            --shadow-sm: 0 1px 2px rgba(10,10,10,.04), 0 2px 6px rgba(10,10,10,.05);
            --shadow-md: 0 6px 18px rgba(10,10,10,.07), 0 2px 6px rgba(10,10,10,.05);
            --shadow-lg: 0 16px 40px rgba(10,10,10,.12);
            --ease: cubic-bezier(.4,0,.2,1);
            --header-h: 64px;
        }}
        html {{ font-size: 16px; scroll-behavior: smooth; }}
        body {{ font-family: var(--font-sans); background: var(--white); color: var(--black); line-height: 1.6; -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; overflow-x: hidden; }}
        img, svg, canvas {{ max-width: 100%; }}
        a {{ color: inherit; }}
        ::selection {{ background: rgba(0,45,98,.14); }}
        :focus-visible {{ outline: 2px solid var(--blue); outline-offset: 3px; border-radius: 4px; }}

        /* Top tricolor accent */
        .top-accent {{ height: 4px; background: linear-gradient(90deg, var(--blue) 0 50%, var(--red) 50% 100%); }}

        /* Custom scrollbar */
        ::-webkit-scrollbar {{ width: 12px; height: 12px; }}
        ::-webkit-scrollbar-track {{ background: var(--white); }}
        ::-webkit-scrollbar-thumb {{ background: var(--gray-200); border-radius: 8px; border: 3px solid var(--white); }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--gray-400); }}

        /* Motion + accordions */
        .fade-in-section {{ opacity: 0; transform: translateY(18px); transition: opacity .7s var(--ease), transform .7s var(--ease); }}
        .fade-in-section.is-visible {{ opacity: 1; transform: none; }}
        .accordion-content {{ max-height: 0; overflow: hidden; opacity: 0; transition: max-height .4s var(--ease), opacity .35s var(--ease); }}
        .accordion-content.open {{ opacity: 1; }}
        .dropdown-arrow {{ font-size: 10px; color: var(--gray-400); transition: transform .3s var(--ease); user-select: none; }}
        .interactive-card, .interactive-legend {{ cursor: pointer; -webkit-tap-highlight-color: transparent; }}
        .interactive-card.active .dropdown-arrow, .interactive-legend.active .dropdown-arrow {{ transform: rotate(180deg); }}

        /* Header */
        .site-header {{ position: sticky; top: 0; z-index: 50; background: rgba(255,255,255,.85); backdrop-filter: saturate(180%) blur(12px); -webkit-backdrop-filter: saturate(180%) blur(12px); border-bottom: var(--border); }}
        .header-inner {{ max-width: var(--maxw); margin: 0 auto; padding: 0 clamp(16px, 5vw, 40px); height: var(--header-h); display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
        .brand {{ display: inline-flex; align-items: center; gap: 10px; text-decoration: none; font-family: var(--font-mono); font-size: 13px; letter-spacing: .02em; color: var(--black); white-space: nowrap; }}
        .brand-mark {{ width: 16px; height: 16px; border-radius: 4px; background: linear-gradient(135deg, var(--blue) 0 50%, var(--red) 50% 100%); box-shadow: var(--shadow-sm); flex-shrink: 0; }}
        .brand-text strong {{ color: var(--blue); font-weight: 600; }}
        .header-nav {{ display: flex; gap: clamp(8px, 2.5vw, 40px); align-items: center; overflow-x: auto; scrollbar-width: none; position: relative; }}
        .header-nav::-webkit-scrollbar {{ display: none; }}
        .nav-cluster {{ display: flex; flex-direction: column; align-items: center; gap: 6px; position: relative; max-width: 100%; }}
        .nav-labels {{ display: flex; align-items: center; gap: clamp(6px, 2vw, 24px); position: relative; z-index: 5; max-width: 100%; overflow-x: auto; scrollbar-width: none; }}
        .nav-labels::-webkit-scrollbar {{ display: none; }}
        .nav-metro {{ width: 100%; height: 14px; overflow: visible; pointer-events: none; }}
        .nav-link {{ font-size: 14px; font-weight: 500; color: var(--gray-600); text-decoration: none; padding: 4px 14px; border-radius: 999px; white-space: nowrap; transition: color .2s var(--ease), background .25s var(--ease); position: relative; z-index: 10; background: transparent; text-shadow: 0 0 6px rgba(255,255,255,.35); }}
        .nav-link:hover {{ color: var(--blue); background: transparent; }}
        .nav-link.active {{ color: var(--white); background: transparent; }}
        .nav-link.active::before {{ content: ''; position: absolute; inset: 0; border-radius: 999px; background: var(--blue); z-index: -1; }}
        .header-inner--centered {{ justify-content: center; }}
        .nav-link--source {{ color: var(--gray-400); font-size: 13px; }}
        .nav-link--source:hover {{ color: var(--blue); background: var(--blue-tint); }}
        .nav-link--clima {{ font-weight: 600; position: relative; padding: 4px 16px; border-radius: 999px; background: transparent; border: 1px solid var(--gray-200); color: var(--gray-600); overflow: hidden; }}
        .nav-link--clima svg {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; fill: none; }}
        .nav-link--clima:hover {{ color: var(--black) !important; border-color: transparent; }}
        .nav-link--clima #climaRect {{ stroke: #0373fc; stroke-width: 2; stroke-linecap: round; }}
        .nav-link--clima.active {{ border-color: transparent; }}
        .nav-link--clima.active::before {{ background: #0373fc; }}
        .clima-teaser {{ display: flex; align-items: center; justify-content: space-between; gap: 32px; padding: 40px 48px; border: var(--border); border-radius: var(--radius); background: var(--white); box-shadow: var(--shadow-sm); text-decoration: none; color: inherit; transition: box-shadow .25s var(--ease), transform .25s var(--ease); }}
        .clima-teaser:hover {{ box-shadow: var(--shadow-lg); transform: translateY(-3px); outline: 2px solid #0373fc; }}
        .clima-teaser:hover .clima-arrow {{ background: #0373fc; }}
        .clima-teaser-left {{ flex: 1; }}
        .clima-teaser-tag {{ font-family: var(--font-mono); font-size: 11px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; background: #0373fc; -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 10px; }}
        .clima-teaser-title {{ font-family: var(--font-display); font-size: 26px; font-weight: 700; color: var(--black); margin-bottom: 10px; line-height: 1.2; }}
        .clima-teaser-desc {{ font-size: 15px; color: var(--gray-600); line-height: 1.7; max-width: 580px; }}
        .clima-teaser-meta {{ font-family: var(--font-mono); font-size: 11px; color: var(--gray-400); margin-top: 14px; }}
        .clima-arrow {{ width: 52px; height: 52px; border-radius: 50%; background: #0373fc; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: transform .25s var(--ease), box-shadow .25s var(--ease); }}
        .clima-arrow::after {{ content: ''; display: block; width: 12px; height: 12px; border-top: 2.5px solid #fff; border-right: 2.5px solid #fff; transform: rotate(45deg) translate(-2px, 2px); }}

        /* Layout */
        .container {{ max-width: var(--maxw); margin: 0 auto; padding: 0 clamp(16px, 5vw, 40px); }}
        main > section {{ padding: clamp(40px, 7vw, 72px) 0; border-bottom: var(--border); }}
        main > section:last-child {{ border-bottom: none; }}
        section[id] {{ scroll-margin-top: 16px; }}
        .section-head {{ display: flex; align-items: center; gap: 16px; margin-bottom: 18px; }}
        .section-label {{ font-family: var(--font-display); font-size: clamp(17px, 3.5vw, 20px); font-weight: 700; color: var(--black); letter-spacing: -.01em; position: relative; padding-left: 14px; }}
        .section-label::before {{ content: ''; position: absolute; left: 0; top: .14em; bottom: .14em; width: 4px; border-radius: 2px; background: var(--blue); }}
        .section-rule {{ flex: 1; height: 1px; background: linear-gradient(90deg, var(--gray-200), transparent); }}
        .section-intro {{ font-size: 15px; color: var(--gray-600); max-width: 760px; margin-bottom: 30px; line-height: 1.7; }}

        /* Hero */
        .hero {{ padding: 0; border-bottom: none; }}

        /* Video banner */
        .hero-banner {{ position: relative; width: 100%; overflow: hidden; background: #f0f0f0; border-bottom: var(--border); }}
        .hero-video {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; pointer-events: none; }}
        .hero-video-overlay {{ position: absolute; inset: 0; background: rgba(255,255,255,0.54); pointer-events: none; }}
        .hero-banner-inner {{ position: relative; z-index: 1; max-width: var(--maxw); margin: 0 auto; padding: clamp(20px, 3vw, 36px) clamp(16px, 5vw, 40px); display: flex; justify-content: center; }}

        /* Logo lockup inside banner */
        .hero-lockup {{ display: block; max-width: clamp(340px, 48vw, 560px); width: 100%; }}
        .hero-lockup-svg {{ display: block; width: 100%; height: auto; }}
        .hero-lockup-tagline {{ font-family: var(--font-display); line-height: 1.05; letter-spacing: -0.02em; margin-top: 3px; font-size: clamp(20px, 4.4vw, 34px); text-align: center; }}
        .hero-lockup-dr {{ color: var(--black); font-weight: 400; }}
        .hero-lockup-ei {{ color: var(--blue); font-weight: 700; }}

        /* Editorial hero content */
        .hero-editorial {{ padding: clamp(28px, 4vw, 44px) 0 clamp(40px, 7vw, 72px); border-bottom: var(--border); }}
        .editorial-topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; flex-wrap: wrap; }}
        .editorial-index-label {{ font-family: var(--font-mono); font-size: 11px; letter-spacing: .14em; color: var(--gray-600); text-transform: uppercase; }}
        .editorial-status-badge {{ display: inline-flex; align-items: center; gap: 8px; font-family: var(--font-mono); font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: {score_color}; padding: 6px 14px; border-radius: 999px; border: 1.5px solid {score_color}; white-space: nowrap; }}
        .editorial-status-badge::before {{ content: ''; width: 8px; height: 8px; border-radius: 50%; background: {score_color}; flex-shrink: 0; }}
        .editorial-score-row {{ display: flex; align-items: baseline; margin-bottom: 10px; }}
        .editorial-score-num {{ font-family: var(--font-mono); font-size: clamp(72px, 14vw, 116px); font-weight: 600; line-height: 1; color: {score_color}; letter-spacing: -5px; }}
        .editorial-score-denom {{ font-family: var(--font-mono); font-size: clamp(22px, 4.5vw, 36px); color: var(--gray-400); letter-spacing: -1px; margin-left: 8px; padding-bottom: 10px; }}
        .editorial-meta-row {{ display: flex; align-items: center; gap: 20px; flex-wrap: wrap; margin-bottom: 26px; }}
        .editorial-meta-item {{ display: inline-flex; align-items: center; gap: 7px; font-family: var(--font-mono); font-size: 12.5px; color: var(--gray-600); }}
        .editorial-meta-trend {{ font-weight: 600; }}
        .editorial-meta-trend.trend-good {{ color: var(--green); }}
        .editorial-meta-trend.trend-bad {{ color: var(--red); }}
        .editorial-meta-trend.trend-neutral {{ color: var(--gray-400); }}
        .editorial-meta-divider {{ width: 1px; height: 15px; background: var(--gray-200); flex-shrink: 0; }}
        .provisional-pill {{ display: inline-block; font-size: 10px; font-weight: 600; letter-spacing: .06em; padding: 2px 8px; border-radius: 999px; background: rgba(206,17,38,0.10); color: var(--red); border: 1px solid rgba(206,17,38,0.25); margin-left: 8px; vertical-align: middle; white-space: nowrap; }}
        .editorial-footer-bar {{ display: flex; align-items: center; gap: 20px; flex-wrap: wrap; padding-top: 20px; border-top: var(--border); margin-top: 6px; }}
        .editorial-status-desc {{ font-size: 14px; color: var(--gray-600); line-height: 1.6; flex: 1; min-width: 180px; }}
        .editorial-estimate-note {{ font-family: var(--font-mono); font-size: 10.5px; color: var(--gray-400); margin-top: 14px; }}

        /* Score meter */
        .score-meter {{ margin-top: 26px; }}
        .meter-track {{ position: relative; height: 12px; border-radius: 999px; background: linear-gradient(90deg, var(--blue-soft) 0 {MODERATE_STRESS_THRESHOLD:.1f}%, var(--blue) {MODERATE_STRESS_THRESHOLD:.1f}% {HIGH_STRESS_THRESHOLD:.1f}%, var(--red) {HIGH_STRESS_THRESHOLD:.1f}% 100%); box-shadow: inset 0 1px 2px rgba(10,10,10,.14); }}
        .meter-marker {{ position: absolute; top: 50%; width: 18px; height: 18px; transform: translate(-50%,-50%) rotate(45deg); background: {score_color}; border: 2px solid var(--white); box-shadow: var(--shadow-sm); }}
        .meter-scale {{ position: relative; height: 16px; margin-top: 9px; font-family: var(--font-mono); font-size: 10px; color: var(--gray-400); }}
        .meter-scale span {{ position: absolute; top: 0; transform: translateX(-50%); }}
        .meter-scale span:first-child {{ transform: none; }}
        .meter-scale span:last-child {{ transform: translateX(-100%); }}
        /* The moderate/high threshold ticks sit close together (4.4 pts apart on a
           0-100 scale); centering both on their position collides the labels, so
           point them away from each other instead. */
        .meter-scale span:nth-child(2) {{ transform: translateX(-100%); padding-right: 4px; }}
        .meter-scale span:nth-child(3) {{ transform: translateX(0); padding-left: 4px; }}
        .meter-caption {{ margin-top: 10px; display: flex; gap: 16px; flex-wrap: wrap; font-size: 11.5px; color: var(--gray-600); }}
        .zone-key {{ display: inline-flex; align-items: center; gap: 6px; }}
        .zone-swatch {{ width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }}

        /* Alert button */
.alert-count {{ display: inline-flex; align-items: center; gap: 8px; margin-top: 18px; padding: 10px 16px; border-radius: 999px; background: {'var(--red-tint)' if stress_n > 0 else 'var(--gray-100)'}; border: 1px solid {'var(--red)' if stress_n > 0 else 'var(--gray-200)'}; font-size: 13px; color: {'var(--red)' if stress_n > 0 else 'var(--gray-600)'}; font-family: var(--font-mono); align-self: flex-start; }}        .interactive-alert {{ cursor: pointer; transition: all .2s var(--ease); }}
        @keyframes alertPulse {{ 0%, 100% {{ background-color: var(--red-tint); border-color: var(--red); box-shadow: none; }} 50% {{ background-color: #ffd6d6; border-color: #ff0000; box-shadow: 0 0 14px rgba(206,17,38,0.55); }} }}
        .interactive-alert:hover {{ animation: alertPulse .9s ease-in-out infinite; }}
        .alert-arrow {{ margin-left: 6px; font-size: 12px; }}

        /* Summary chips */
        .summary-chips {{ display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }}
        .chip {{ display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: 999px; border: var(--border); background: var(--white); font-family: var(--font-mono); font-size: 12.5px; color: var(--black); cursor: pointer; transition: box-shadow .2s var(--ease), transform .2s var(--ease), border-color .2s var(--ease); }}
        .chip:hover {{ box-shadow: var(--shadow-sm); transform: translateY(-1px); border-color: var(--gray-300); }}
        .chip b {{ font-weight: 600; }}
        .chip-dot {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }}
        .chip-stress .chip-dot {{ background: var(--red); }}
        .chip-watch .chip-dot {{ background: var(--blue); }}
        .chip-normal .chip-dot {{ background: var(--gray-400); }}

        /* Briefing */
        .briefing-text {{ font-size: clamp(16px, 2.4vw, 19px); line-height: 1.85; color: var(--black); max-width: 860px; }}
        .briefing-text p {{ margin-bottom: 20px; }}
        .briefing-text p:last-child {{ margin-bottom: 0; color: var(--gray-600); font-size: 15px; line-height: 1.7; padding-top: 18px; border-top: var(--border); }}
        .briefing-text strong {{ color: var(--blue); font-weight: 600; }}

        /* Cards shared */
        .card-header {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; }}
        .card-label {{ font-size: 15px; font-weight: 600; color: var(--black); line-height: 1.3; }}
        .card-desc {{ font-size: 13px; color: var(--gray-600); line-height: 1.65; }}

        /* Context cards */
        .context-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); gap: 20px; }}
        .context-card {{ padding: 24px; border: var(--border); background: var(--white); border-radius: var(--radius); display: flex; flex-direction: column; box-shadow: var(--shadow-sm); transition: box-shadow .25s var(--ease), transform .25s var(--ease), border-color .25s var(--ease); }}
        .context-card:hover {{ box-shadow: var(--shadow-md); transform: translateY(-3px); border-color: var(--gray-300); }}
        .context-item {{ display: grid; grid-template-columns: 1fr 84px; gap: 16px; align-items: center; margin-top: 16px; padding-bottom: 14px; border-bottom: var(--border); }}
        .context-item:last-of-type {{ border-bottom: none; padding-bottom: 0; }}
        .ci-info {{ display: flex; flex-direction: column; }}
        .ci-label {{ font-size: 12.5px; color: var(--gray-600); margin-bottom: 4px; }}
        .ci-value {{ font-family: var(--font-mono); font-size: 18px; font-weight: 600; color: var(--black); }}
        .ci-chart {{ height: 36px; width: 100%; position: relative; }}
        .context-stats {{ margin-top: 16px; padding-top: 14px; border-top: var(--border); display: flex; flex-direction: column; gap: 7px; }}
        .context-row {{ display: flex; justify-content: space-between; gap: 12px; font-size: 13px; color: var(--gray-600); }}
        .context-row strong {{ color: var(--black); font-weight: 600; }}
        .context-desc {{ margin-top: 14px; }}

        /* Alerts */
        .alerts-list {{ display: flex; flex-direction: column; gap: 14px; }}
        .alert-item {{ display: grid; grid-template-columns: 110px 1fr; gap: 20px; align-items: start; padding: 20px 24px; border: var(--border); border-radius: var(--radius); background: var(--white); box-shadow: var(--shadow-sm); }}
        .alert-stress {{ border-left: 4px solid var(--red); background: var(--red-tint); }}
        .alert-watch  {{ border-left: 4px solid var(--blue); background: var(--blue-tint); }}
        .alert-tag {{ font-family: var(--font-mono); font-size: 11px; font-weight: 600; letter-spacing: 0.1em; padding-top: 2px; }}
        .alert-stress .alert-tag {{ color: var(--red); }} .alert-watch .alert-tag {{ color: var(--blue); }}
        .alert-content {{ display: flex; flex-direction: column; gap: 6px; }}
        .alert-content strong {{ font-size: 16px; font-weight: 600; }}
        .alert-text {{ font-size: 14px; color: var(--gray-600); line-height: 1.6; }}
        .no-alerts {{ display: flex; align-items: center; gap: 16px; padding: 22px 24px; background: var(--blue-tint); border: var(--border); border-left: 4px solid var(--green); border-radius: var(--radius); font-size: 15px; color: var(--gray-600); }}
        .no-alerts-icon {{ font-size: 20px; color: var(--green); }}

        /* Panel legend + filters */
        .legend-intro {{ font-size: 13px; font-weight: 600; color: var(--gray-600); letter-spacing: .02em; margin-bottom: 14px; }}
        .legend-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 290px), 1fr)); gap: 14px; margin-bottom: 36px; }}
        .legend-item {{ padding: 18px 20px; background: var(--gray-50); border: var(--border); border-radius: var(--radius-sm); transition: background .2s var(--ease); }}
        .legend-item:hover {{ background: var(--gray-100); }}
        .legend-title {{ font-size: 13.5px; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
        .legend-dot {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }}
        .legend-desc {{ font-size: 13px; color: var(--gray-600); line-height: 1.6; margin-top: 10px; }}
        .filter-bar {{ display: flex; gap: 10px; margin-bottom: 24px; flex-wrap: wrap; }}
        .filter-chip {{ font-family: var(--font-mono); font-size: 12px; font-weight: 600; letter-spacing: .04em; padding: 8px 16px; border: var(--border); border-radius: 999px; background: var(--white); color: var(--gray-600); cursor: pointer; transition: all .2s var(--ease); }}
        .filter-chip:hover {{ border-color: var(--blue); color: var(--blue); }}
        .filter-chip.active {{ background: var(--blue); border-color: var(--blue); color: var(--white); }}

        /* Indicator cards */
        .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); gap: 20px; }}
        .indicator-card {{ padding: 26px; border: var(--border); background: var(--white); border-radius: var(--radius); box-shadow: var(--shadow-sm); position: relative; overflow: hidden; transition: box-shadow .25s var(--ease), transform .25s var(--ease), border-color .25s var(--ease); max-width: 460px; }}
        .indicator-card::before {{ content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--gray-300); }}
        .indicator-card[data-status="watch"]::before {{ background: var(--blue); }}
        .indicator-card[data-status="stress"]::before {{ background: var(--red); }}
        .indicator-card:hover {{ box-shadow: var(--shadow-md); transform: translateY(-3px); border-color: var(--gray-300); }}
        .card-stress {{ border-color: var(--red); background: var(--red-tint); }}
        .card-stress:hover {{ background: #fae8eb; }}
        @keyframes redBlink {{ 0%, 100% {{ background-color: var(--red-tint); border-color: var(--red); }} 50% {{ background-color: #ffd6d6; border-color: #ff0000; box-shadow: 0 0 16px rgba(206,17,38,0.5); }} }}
        .blink-alert {{ animation: redBlink .6s ease-in-out 2; }}
        .indicator-card .card-header {{ align-items: flex-start; margin-bottom: 16px; }}
        .card-header-meta {{ display: flex; align-items: center; gap: 8px; }}
        .status-badge {{ font-family: var(--font-mono); font-size: 10px; font-weight: 600; letter-spacing: 0.08em; padding: 4px 9px; border-radius: 999px; white-space: nowrap; flex-shrink: 0; }}
        .status-stress {{ background: var(--red); color: var(--white); }}
        .status-watch  {{ background: var(--blue); color: var(--white); }}
        .status-normal {{ background: var(--gray-100); color: var(--gray-600); }}
        .card-value {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 16px; }}
        .value-number {{ font-family: var(--font-mono); font-size: 27px; font-weight: 600; color: var(--black); }}
        .value-arrow {{ font-size: 18px; }} .arrow-bad {{ color: var(--red); }} .arrow-good {{ color: var(--green); }}
        .zscore-bar-container {{ height: 5px; background: var(--gray-200); border-radius: 999px; margin-bottom: 8px; overflow: hidden; }}
        .zscore-bar {{ height: 100%; border-radius: 999px; transition: width .4s var(--ease); }}
        .zscore-label {{ font-family: var(--font-mono); font-size: 11px; color: var(--gray-400); margin-top: 14px; margin-bottom: 12px; }}

        /* Chart */
        .chart-card {{ border: var(--border); border-radius: var(--radius); padding: 24px; background: var(--white); box-shadow: var(--shadow-sm); }}
        .chart-controls {{ display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; }}
        .chart-btn {{ font-family: var(--font-mono); font-size: 11px; font-weight: 600; letter-spacing: 0.06em; padding: 7px 15px; border: var(--border); border-radius: 999px; background: var(--white); color: var(--gray-600); cursor: pointer; transition: all .15s var(--ease); }}
        .chart-btn:hover {{ border-color: var(--blue); color: var(--blue); }}
        .chart-btn.active {{ background: var(--blue); color: var(--white); border-color: var(--blue); }}
        .chart-container {{ position: relative; height: 380px; }}
        .chart-hint {{ font-size: 12px; color: var(--gray-400); font-family: var(--font-mono); margin-top: 12px; }}

        /* Footer */
        .site-footer {{ padding: 44px 0; background: var(--gray-50); border-top: var(--border); }}
        .footer-inner {{ max-width: var(--maxw); margin: 0 auto; padding: 0 clamp(16px, 5vw, 40px); display: flex; justify-content: space-between; align-items: flex-end; gap: 20px; flex-wrap: wrap; }}
        .footer-sources {{ font-size: 13px; color: var(--gray-600); line-height: 1.7; max-width: 640px; }}
        .footer-sources strong {{ font-weight: 600; color: var(--black); }}
        .footer-run {{ font-family: var(--font-mono); font-size: 11px; color: var(--gray-400); white-space: nowrap; }}
        .footer-run strong {{ font-weight: 600; color: var(--black); }}

        /* Back to top */
        .back-to-top {{ position: fixed; right: 24px; bottom: 24px; width: 46px; height: 46px; border-radius: 50%; border: none; background: var(--blue); color: var(--white); font-size: 20px; line-height: 1; cursor: pointer; box-shadow: var(--shadow-md); opacity: 0; visibility: hidden; transform: translateY(10px); transition: all .3s var(--ease); z-index: 40; }}
        .back-to-top.show {{ opacity: 1; visibility: visible; transform: none; }}
        .back-to-top:hover {{ background: var(--blue-deep); transform: translateY(-2px); box-shadow: var(--shadow-lg); }}

        /* Responsive */
        @media (max-width: 980px) {{
            .hero-lockup {{ max-width: 460px; }}
            .editorial-topbar {{ flex-direction: column; align-items: flex-start; gap: 10px; }}
        }}
        @media (max-width: 640px) {{
            .alert-item {{ grid-template-columns: 1fr; gap: 10px; }}
            .brand-text {{ display: none; }}
            .hero-lockup {{ max-width: 240px; }}
            .editorial-meta-row {{ gap: 10px; }}
            .editorial-meta-divider {{ display: none; }}
            .editorial-footer-bar {{ flex-direction: column; align-items: flex-start; gap: 14px; }}
            .footer-inner {{ flex-direction: column; align-items: flex-start; }}
            .nav-cluster {{ align-items: flex-start; }}
            .nav-labels {{ padding-bottom: 2px; }}
            .nav-metro {{ display: none; }}
            .nav-link {{ padding: 8px 14px; }}
            .filter-chip, .chart-btn {{ min-height: 40px; }}
            .clima-teaser {{ flex-direction: column; align-items: flex-start; padding: 28px 24px; gap: 20px; }}
            .clima-arrow {{ align-self: flex-end; }}
            .chart-hint {{ font-size: 11px; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            * {{ animation: none !important; transition: none !important; scroll-behavior: auto !important; }}
            .fade-in-section {{ opacity: 1; transform: none; }}
        }}
        @media print {{
            .site-header, .back-to-top, .chart-controls, .chart-hint, .filter-bar {{ display: none !important; }}
            .fade-in-section {{ opacity: 1 !important; transform: none !important; }}
            .accordion-content {{ max-height: none !important; opacity: 1 !important; overflow: visible !important; }}
            .panel, .context-card, .indicator-card, .alert-item, .chart-card {{ box-shadow: none !important; break-inside: avoid; }}
            main > section {{ padding: 24px 0; }}
            body {{ font-size: 12px; }}
        }}
    </style>
    <noscript><style>
        .fade-in-section {{ opacity: 1 !important; transform: none !important; }}
        .accordion-content {{ max-height: none !important; opacity: 1 !important; }}
        .dropdown-arrow {{ display: none; }}
    </style></noscript>
</head>
<body>

<div class="top-accent" id="top"></div>

<header class="site-header">
    <div class="header-inner header-inner--centered">
        <div class="nav-cluster" id="navCluster">
            <div class="nav-labels">
                <nav class="header-nav" id="mainNav" aria-label="Secciones del informe">
                    {context_nav}
                    <a href="#indicadores-seguimiento" class="nav-link">Indicadores</a>
                    <a href="#panel-indicadores" class="nav-link">Panel</a>
                    <a href="#historial-indice" class="nav-link">Historial</a>
                </nav>
                <a href="#clima-social-entry" class="nav-link nav-link--clima">
                    <svg aria-hidden="true" style="position:absolute;left:0;top:0;width:100%;height:100%;overflow:visible;pointer-events:none"><path id="climaRect" fill="none" stroke="#0373fc" stroke-width="2" stroke-linecap="round"/></svg>
                    Clima Social
                </a>
            </div>
            <svg class="nav-metro" id="navMetro" aria-hidden="true">
                <defs>
                    <linearGradient id="metroFill" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="600" y2="0">
                        <stop offset="0%" stop-color="#002D62"/>
                        <stop offset="50%" stop-color="#4A90D9"/>
                        <stop offset="78%" stop-color="#0373fc"/>
                        <stop offset="100%" stop-color="#0373fc"/>
                    </linearGradient>
                </defs>
                <line id="metroTrack" x1="0" y1="7" x2="100" y2="7" stroke="#E0E0E0" stroke-width="1.5" stroke-linecap="round"/>
                <line id="metroFillLine" x1="0" y1="7" x2="0" y2="7" stroke="url(#metroFill)" stroke-width="2" stroke-linecap="round"/>
                <g id="metroNodes"></g>
            </svg>
        </div>
    </div>
</header>

<main>

    <section class="hero">

        <div class="hero-banner">
            <video class="hero-video" autoplay muted loop playsinline>
                <source src="{HERO_VIDEO_SRC}" type="video/mp4">
            </video>
            <div class="hero-video-overlay"></div>
            <div class="hero-banner-inner">
                <div class="hero-lockup" role="img" aria-label="La Sociedad — DR Economic Intelligence">
                    <img src="{HERO_LOGO_SVG_SRC}" alt="La Sociedad" class="hero-lockup-svg" loading="eager">
                    <div class="hero-lockup-tagline" aria-hidden="true">
                        <span class="hero-lockup-dr">DR </span><span class="hero-lockup-ei">Economic Intelligence</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="container hero-editorial">

            <div class="editorial-topbar">
                <span class="editorial-index-label">Índice de Vulnerabilidad Económica</span>
                <span class="editorial-status-badge">{status_label}</span>
            </div>

            <div class="editorial-score-row">
                <span class="editorial-score-num">{score:.1f}</span>
                <span class="editorial-score-denom">/100</span>
            </div>

            <div class="editorial-meta-row">
                {editorial_meta_html}
            </div>

            <div class="score-meter" role="img" aria-label="Puntuación {score:.1f} de 100">
                <div class="meter-track"><div class="meter-marker" style="left:{meter_pos:.1f}%"></div></div>
                <div class="meter-scale"><span style="left:0">0</span><span style="left:{MODERATE_STRESS_THRESHOLD:.1f}%">{MODERATE_STRESS_THRESHOLD:.1f}</span><span style="left:{HIGH_STRESS_THRESHOLD:.1f}%">{HIGH_STRESS_THRESHOLD:.1f}</span><span style="left:100%">100</span></div>
                <div class="meter-caption">
                    <span class="zone-key"><span class="zone-swatch" style="background:var(--blue-soft)"></span>Normal</span>
                    <span class="zone-key"><span class="zone-swatch" style="background:var(--blue)"></span>Moderado ({MODERATE_STRESS_THRESHOLD:.1f}+)</span>
                    <span class="zone-key"><span class="zone-swatch" style="background:var(--red)"></span>Alerta ({HIGH_STRESS_THRESHOLD:.1f}+)</span>
                </div>
            </div>

            <div class="editorial-footer-bar">
                <span class="editorial-status-desc">{status_desc}</span>
                {alert_box_html}
                <div class="summary-chips" role="group" aria-label="Resumen de indicadores">
                    <button type="button" class="chip chip-stress" onclick="jumpFilter('stress')" aria-label="{stress_n} indicadores en alerta"><span class="chip-dot" aria-hidden="true"></span><b>{stress_n}</b>&nbsp;en alerta</button>
                    <button type="button" class="chip chip-watch" onclick="jumpFilter('watch')" aria-label="{watch_n} indicadores en vigilancia"><span class="chip-dot" aria-hidden="true"></span><b>{watch_n}</b>&nbsp;en vigilancia</button>
                    <button type="button" class="chip chip-normal" onclick="jumpFilter('normal')" aria-label="{normal_n} indicadores normales"><span class="chip-dot" aria-hidden="true"></span><b>{normal_n}</b>&nbsp;normales</button>
                </div>
            </div>

            {editorial_notes_html}
        </div>

    </section>

    <section>
        <div class="container">
            <div class="section-head"><h2 class="section-label">Análisis semanal</h2><span class="section-rule"></span></div>
            <div class="briefing-text"><p>{briefing}</p></div>
        </div>
    </section>

    {context_section_html}

    <section id="indicadores-seguimiento">
        <div class="container">
            <div class="section-head"><h2 class="section-label">Indicadores en seguimiento</h2><span class="section-rule"></span></div>
            <p class="section-intro">Indicadores que se desvían de forma notable de su promedio histórico y concentran la atención esta semana.</p>
            <div class="alerts-list">{alert_html}</div>
        </div>
    </section>

    <section id="panel-indicadores">
        <div class="container">
            <div class="section-head"><h2 class="section-label">Panel de indicadores</h2><span class="section-rule"></span></div>
            <div class="legend-intro">Cómo interpretar cada indicador</div>
            <div class="legend-grid">
                <div class="legend-item interactive-legend" data-group="legend-status" onclick="toggleAccordion(this)">
                    <div class="legend-title"><div class="legend-dot" style="background:var(--red)"></div>ALERTA <span class="dropdown-arrow" style="margin-left:auto;" aria-hidden="true">&#9660;</span></div>
                    <div class="accordion-content"><div class="legend-desc">El indicador supera 1.5 desviaciones estándar de su promedio histórico en dirección de estrés.</div></div>
                </div>
                <div class="legend-item interactive-legend" data-group="legend-status" onclick="toggleAccordion(this)">
                    <div class="legend-title"><div class="legend-dot" style="background:var(--blue)"></div>VIGILANCIA <span class="dropdown-arrow" style="margin-left:auto;" aria-hidden="true">&#9660;</span></div>
                    <div class="accordion-content"><div class="legend-desc">El indicador muestra desviación notable pero sin superar el umbral de alerta. Requiere seguimiento.</div></div>
                </div>
                <div class="legend-item interactive-legend" data-group="legend-status" onclick="toggleAccordion(this)">
                    <div class="legend-title"><div class="legend-dot" style="background:var(--gray-400)"></div>NORMAL <span class="dropdown-arrow" style="margin-left:auto;" aria-hidden="true">&#9660;</span></div>
                    <div class="accordion-content"><div class="legend-desc">El indicador se encuentra dentro de sus rangos históricos habituales. No representa riesgo inmediato.</div></div>
                </div>
                <div class="legend-item interactive-legend" data-group="legend-metrics" onclick="toggleAccordion(this)">
                    <div class="legend-title">Z-score <span class="dropdown-arrow" style="margin-left:auto;" aria-hidden="true">&#9660;</span></div>
                    <div class="accordion-content"><div class="legend-desc">Mide cuántas desviaciones estándar se aleja el valor actual de su promedio histórico.</div></div>
                </div>
                <div class="legend-item interactive-legend" data-group="legend-metrics" onclick="toggleAccordion(this)">
                    <div class="legend-title">Peso <span class="dropdown-arrow" style="margin-left:auto;" aria-hidden="true">&#9660;</span></div>
                    <div class="accordion-content"><div class="legend-desc">Contribución porcentual de cada indicador al índice total.</div></div>
                </div>
                <div class="legend-item interactive-legend" data-group="legend-metrics" onclick="toggleAccordion(this)">
                    <div class="legend-title">&#8593; &#8595; Tendencia <span class="dropdown-arrow" style="margin-left:auto;" aria-hidden="true">&#9660;</span></div>
                    <div class="accordion-content"><div class="legend-desc">Dirección del cambio respecto al mes anterior. Rojo si desfavorable, verde si favorable.</div></div>
                </div>
            </div>
            <div class="filter-bar" role="group" aria-label="Filtrar indicadores por estado">
                <button type="button" class="filter-chip active" data-filter="all" onclick="filterIndicators('all', this)">Todos ({total_n})</button>
                <button type="button" class="filter-chip" data-filter="stress" onclick="filterIndicators('stress', this)">Alerta ({stress_n})</button>
                <button type="button" class="filter-chip" data-filter="watch" onclick="filterIndicators('watch', this)">Vigilancia ({watch_n})</button>
                <button type="button" class="filter-chip" data-filter="normal" onclick="filterIndicators('normal', this)">Normal ({normal_n})</button>
            </div>
            <div class="cards-grid">{cards}</div>
        </div>
    </section>

    <section id="historial-indice">
        <div class="container">
            <div class="section-head"><h2 class="section-label">Historial completo del índice</h2><span class="section-rule"></span></div>
            <div class="chart-card">
                <div class="chart-controls">
                    <button class="chart-btn" data-range="12">12 meses</button>
                    <button class="chart-btn" data-range="24">24 meses</button>
                    <button class="chart-btn active" data-range="36">36 meses</button>
                    <button class="chart-btn" data-range="0">Todo</button>
                </div>
                <div class="chart-container"><canvas id="scoreChart"></canvas></div>
                <div class="chart-hint">Desplácese para hacer zoom · Arrastre para navegar · La línea roja marca el umbral de alerta ({HIGH_STRESS_THRESHOLD})</div>
            </div>
        </div>
    </section>

</main>

<section id="clima-social-entry" style="padding: 72px 0; border-top: var(--border);">
    <div class="container">
        <div class="section-head"><h2 class="section-label">Más de La Sociedad</h2><span class="section-rule"></span></div>
        <a href="clima-social.html" class="clima-teaser">
            <div class="clima-teaser-left">
                <div class="clima-teaser-tag">Informe · Ola 7 · Abril 2026</div>
                <div class="clima-teaser-title">Clima Social Dominicano</div>
                <div class="clima-teaser-desc">Un análisis del estado de ánimo, la economía cotidiana y la percepción ciudadana de la República Dominicana. Basado en 808 entrevistas realizadas en abril de 2026.</div>
                <div class="clima-teaser-meta">n=808 &nbsp;·&nbsp; Levantamiento abril 2026 &nbsp;·&nbsp; LS Consulting / La Sociedad</div>
            </div>
            <div class="clima-arrow"></div>
        </a>
    </div>
</section>

<footer class="site-footer">
    <div class="footer-inner">
        <div class="footer-sources">
            <strong>Fuentes:</strong> Banco Central de la República Dominicana (BCRD) · Superintendencia de Bancos (SB) · Reserva Federal de EE.UU. (FRED)<br>
        </div>
        <div class="footer-run"><a href="https://github.com/ianperaltahirujo/dr-economic-intelligence" target="_blank" rel="noopener" style="color:inherit;text-decoration:underline;"><strong>Ver código fuente &#8599;</strong></a></div>
    </div>
</footer>

<button id="backToTop" class="back-to-top" aria-label="Volver al inicio" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">&#8593;</button>

<script>
document.addEventListener("DOMContentLoaded", function() {{
    // Sparklines
    document.querySelectorAll('.sparkline').forEach(canvas => {{
        try {{
            const data = JSON.parse(canvas.getAttribute('data-chart'));
            if (!data || !data.length) return;
            new Chart(canvas.getContext('2d'), {{
                type: 'line',
                data: {{ labels: data.map((_, i) => i), datasets: [{{ data, borderColor: '#002D62', borderWidth: 2, tension: 0.35, pointRadius: 0, fill: false }}] }},
                options: {{ responsive: true, maintainAspectRatio: false, animation: false, plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }} }}, scales: {{ x: {{ display: false }}, y: {{ display: false }} }}, layout: {{ padding: 2 }}, elements: {{ line: {{ borderCapStyle: 'round' }} }} }}
            }});
        }} catch(e) {{ console.error("Sparkline error", e); }}
    }});

    // Keyboard support for expandable cards
    document.querySelectorAll('.interactive-card, .interactive-legend').forEach(el => {{
        el.setAttribute('role', 'button');
        el.setAttribute('tabindex', '0');
        el.setAttribute('aria-expanded', 'false');
        el.addEventListener('keydown', e => {{
            if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); el.click(); }}
        }});
    }});

    // Panel de indicadores: the 6 legend items under "Cómo interpretar cada
    // indicador" default open on load. Indicator cards themselves stay
    // closed by default, matching the original behavior. State is set
    // directly rather than via toggleAccordion(), since that function's
    // group-toggle behavior (legend items share data-group in sets of 3)
    // would flip-flop if called repeatedly across members of the same group.
    document.querySelectorAll('#panel-indicadores .interactive-legend').forEach(el => {{
        el.classList.add('active');
        el.setAttribute('aria-expanded', 'true');
        const content = el.querySelector('.accordion-content');
        if (content) {{ content.classList.add('open'); content.style.maxHeight = content.scrollHeight + 'px'; }}
    }});

    // Reveal sections on scroll
    const fadeObserver = new IntersectionObserver(entries => {{
        entries.forEach(e => {{ if (e.isIntersecting) e.target.classList.add('is-visible'); }});
    }}, {{ threshold: 0.12 }});
    document.querySelectorAll('main > section').forEach(sec => {{ sec.classList.add('fade-in-section'); fadeObserver.observe(sec); }});

    // Scroll-spy handled by the NAV METRO LINE block below (single source of truth for .active)

    // Back-to-top visibility
    const btt = document.getElementById('backToTop');
    if (btt) {{
        window.addEventListener('scroll', () => {{
            if (window.scrollY > 600) btt.classList.add('show'); else btt.classList.remove('show');
        }}, {{ passive: true }});
    }}
}});

function toggleAccordion(element) {{
    const group = element.getAttribute('data-group');
    const elementsToToggle = group
        ? Array.from(document.querySelectorAll(`[data-group="${{group}}"]`))
        : [element];
    const isOpening = !element.classList.contains('active');
    elementsToToggle.forEach(el => {{
        const content = el.querySelector('.accordion-content');
        if (isOpening) {{
            el.classList.add('active');
            el.setAttribute('aria-expanded', 'true');
            if (content) {{ content.classList.add('open'); content.style.maxHeight = content.scrollHeight + "px"; }}
        }} else {{
            el.classList.remove('active');
            el.setAttribute('aria-expanded', 'false');
            if (content) {{ content.classList.remove('open'); content.style.maxHeight = null; }}
        }}
    }});
}}

function filterIndicators(status, btn) {{
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    if (btn) {{ btn.classList.add('active'); }}
    else {{ const b = document.querySelector(`.filter-chip[data-filter="${{status}}"]`); if (b) b.classList.add('active'); }}
    document.querySelectorAll('.indicator-card').forEach(card => {{
        const match = (status === 'all') || (card.getAttribute('data-status') === status);
        card.style.display = match ? '' : 'none';
    }});
}}

function jumpFilter(status) {{
    filterIndicators(status);
    const panel = document.getElementById('panel-indicadores');
    if (panel) {{
        const targetY = panel.getBoundingClientRect().top + window.scrollY - 16;
        window.scrollTo({{ top: targetY, behavior: 'smooth' }});
    }}
    if (status === 'stress') {{
        setTimeout(() => {{
            document.querySelectorAll('.card-stress').forEach(card => {{
                card.classList.remove('blink-alert');
                void card.offsetWidth;
                card.classList.add('blink-alert');
            }});
        }}, 1000);
    }}
}}

// Main history chart
const chartData = {chart_data};

// Three-way split: confirmed (solid), provisional (dashed, Avance Estimado --
// full coverage but tourism was forward-filled), and estimated (dashed,
// Índice estimado -- renormalized partial-coverage display, anywhere in the
// series). A dashed point is drawn if it IS that type or sits next to one on
// EITHER side, so every dashed run joins the solid line at both ends and an
// estimated month wedged between two real months no longer leaves a hole.
// The old estimated bridge looked only one step back, which is what tore the
// line at single-indicator gaps like Ago 2019, all of 2022, and Oct 2025.
const _adjacent = (flags, i) => (i - 1 >= 0 && flags[i - 1]) || (i + 1 < flags.length && flags[i + 1]);
const confirmedValues = chartData.values.map((v, i) => (chartData.provisional[i] || chartData.estimated[i]) ? null : v);
const provisionalValues = chartData.values.map((v, i) => {{
    if (chartData.provisional[i]) return v;
    // bridge into adjacent provisional runs, but never claim an estimated point
    if (!chartData.estimated[i] && _adjacent(chartData.provisional, i)) return v;
    return null;
}});
const estimatedValues = chartData.values.map((v, i) => {{
    if (chartData.estimated[i]) return v;
    if (_adjacent(chartData.estimated, i)) return v;
    return null;
}});
// These mirror the currently-visible slice so the tooltip callback always
// reads the right element. applyRange keeps them in sync.
let activeEstimated = chartData.estimated;
let activeProvisional = chartData.provisional;
let activeCoverageN = chartData.coverageN;
// Point radius scaled by coverage confidence: thin-coverage months render
// as smaller points, alongside their already-lighter color, so visual
// weight tracks how much of the index was actually available that month.
const MIN_POINT_R = 1.5, MAX_POINT_R = 3;
const estimatedRadii = chartData.pointAlpha.map(a => MIN_POINT_R + (MAX_POINT_R - MIN_POINT_R) * a);

const ctx = document.getElementById('scoreChart').getContext('2d');
const scoreChart = new Chart(ctx, {{
    type: 'line',
    data: {{
        labels: chartData.labels,
        datasets: [
            {{
                label: 'Índice de Vulnerabilidad',
                data: confirmedValues,
                borderColor: '#002D62',
                backgroundColor: 'rgba(0,45,98,0.06)',
                borderWidth: 2,
                pointBackgroundColor: chartData.colors,
                pointBorderColor: chartData.colors,
                pointRadius: 3,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.3,
                spanGaps: false
            }},
            {{
                label: 'Avance Estimado',
                data: provisionalValues,
                borderColor: '#002D62',
                backgroundColor: 'transparent',
                borderWidth: 2,
                borderDash: [6, 4],
                pointBackgroundColor: 'rgba(0,45,98,0.4)',
                pointBorderColor: 'rgba(0,45,98,0.4)',
                pointRadius: 3,
                pointHoverRadius: 6,
                fill: false,
                tension: 0.3,
                spanGaps: false
            }},
            {{
                label: 'Índice Estimado (histórico)',
                data: estimatedValues,
                borderColor: '#002D62',
                backgroundColor: 'transparent',
                borderWidth: 2,
                borderDash: [3, 5],
                pointBackgroundColor: chartData.colors,
                pointBorderColor: chartData.colors,
                pointRadius: estimatedRadii,
                pointHoverRadius: 5,
                fill: false,
                tension: 0.3,
                spanGaps: false
            }}
        ]
    }},
    options: {{
        responsive: true, maintainAspectRatio: false,
        interaction: {{ intersect: false, mode: 'index' }},
        plugins: {{
            legend: {{ display: false }},
            tooltip: {{
                backgroundColor: '#0A0A0A', titleColor: '#fff', bodyColor: '#ccc', padding: 12, displayColors: false,
                callbacks: {{
                    label: c => {{
                        const v = c.parsed.y;
                        if (v === null) return null;
                        const isEstimated = activeEstimated[c.dataIndex];
                        const isProvisional = activeProvisional[c.dataIndex];
                        if (isEstimated) {{
                            const n = activeCoverageN[c.dataIndex];
                            return `Índice estimado: ${{v}} / 100 (${{n}} de 12 indicadores)`;
                        }}
                        if (isProvisional) return `Índice: ${{v}} / 100 (Avance Estimado)`;
                        return `Índice: ${{v}} / 100`;
                    }},
                    filter: item => item.parsed.y !== null
                }}
            }},
            zoom: {{ zoom: {{ wheel: {{ enabled: true }}, pinch: {{ enabled: true }}, mode: 'x' }}, pan: {{ enabled: true, mode: 'x', touch: false }} }}
        }},
        scales: {{
            x: {{ grid: {{ color: 'rgba(0,0,0,0.05)' }}, ticks: {{ font: {{ family: 'IBM Plex Mono', size: 11 }}, color: '#555555', maxTicksLimit: window.innerWidth < 640 ? 6 : 14, maxRotation: 45 }} }},
            y: {{ min: 0, max: 100, grid: {{ color: 'rgba(0,0,0,0.05)' }}, ticks: {{ font: {{ family: 'IBM Plex Mono', size: 11 }}, color: '#555555', stepSize: 25, callback: v => v + '/100' }} }}
        }}
    }}
}});

// Dashed alert-threshold line + label
const originalDraw = scoreChart.draw.bind(scoreChart);
scoreChart.draw = function() {{
    originalDraw();
    const y = scoreChart.scales.y.getPixelForValue({HIGH_STRESS_THRESHOLD});
    const c2 = scoreChart.ctx;
    c2.save(); c2.beginPath();
    c2.moveTo(scoreChart.scales.x.left, y); c2.lineTo(scoreChart.scales.x.right, y);
    c2.strokeStyle = 'rgba(206,17,38,0.4)'; c2.lineWidth = 1; c2.setLineDash([5,5]); c2.stroke();
    c2.setLineDash([]); c2.fillStyle = 'rgba(206,17,38,0.85)'; c2.font = '600 10px "IBM Plex Mono", monospace';
    c2.textAlign = 'right'; c2.fillText('Umbral de alerta ({HIGH_STRESS_THRESHOLD})', scoreChart.scales.x.right - 6, y - 6);
    c2.restore();
}};

function applyRange(months, btn) {{
    document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    if (scoreChart.resetZoom) scoreChart.resetZoom();
    const n = months || chartData.labels.length;
    const slicedLabels = chartData.labels.slice(-n);
    const slicedConfirmed = confirmedValues.slice(-n);
    const slicedProvisional = provisionalValues.slice(-n);
    const slicedEstimated = estimatedValues.slice(-n);
    const slicedColors = chartData.colors.slice(-n);
    const slicedRadii = estimatedRadii.slice(-n);
    // Keep tooltip lookup arrays aligned with the visible slice
    activeEstimated = chartData.estimated.slice(-n);
    activeProvisional = chartData.provisional.slice(-n);
    activeCoverageN = chartData.coverageN.slice(-n);
    scoreChart.data.labels = slicedLabels;
    scoreChart.data.datasets[0].data = slicedConfirmed;
    scoreChart.data.datasets[0].pointBackgroundColor = slicedColors;
    scoreChart.data.datasets[0].pointBorderColor = slicedColors;
    scoreChart.data.datasets[1].data = slicedProvisional;
    scoreChart.data.datasets[2].data = slicedEstimated;
    scoreChart.data.datasets[2].pointBackgroundColor = slicedColors;
    scoreChart.data.datasets[2].pointBorderColor = slicedColors;
    scoreChart.data.datasets[2].pointRadius = slicedRadii;
    scoreChart.update();
}}
document.querySelectorAll('.chart-btn').forEach(b => b.addEventListener('click', () => applyRange(parseInt(b.dataset.range, 10), b)));
(function() {{ const def = document.querySelector('.chart-btn[data-range="36"]'); applyRange(36, def); }})();

// Re-fit chart once the IBM Plex Mono webfont loads. Chart.js renders before the
// font is ready, measures axis-label widths with the fallback font, under-allocates,
// then clips the first character ("100/100" -> "00/100") when the wider font swaps in.
// Busting the cached label measurements and updating forces a correct re-measure.
if (document.fonts && document.fonts.ready) {{
    document.fonts.ready.then(function() {{
        Object.keys(scoreChart.scales).forEach(function(k) {{
            scoreChart.scales[k]._longestTextCache = {{}};
            scoreChart.scales[k]._labelSizes = null;
        }});
        scoreChart.update();
    }});
}}

// ── CLIMA BUTTON SVG PATH ──
(function() {{
    var btn = document.querySelector('.nav-link--clima');
    var path = document.getElementById('climaRect');
    if (!btn || !path) return;
    function sizePath() {{
        var w = btn.offsetWidth;
        var h = btn.offsetHeight;
        var r = 14; 
        
        // Draw open path matching the pill shape. Doesn't close (no Z), preventing dash wrapping.
        var d = 'M ' + (r+1) + ',1 ' +
                'H ' + (w-r-1) + ' ' +
                'A ' + r + ',' + r + ' 0 0 1 ' + (w-1) + ',' + (r+1) + ' ' +
                'V ' + (h-r-1) + ' ' +
                'A ' + r + ',' + r + ' 0 0 1 ' + (w-r-1) + ',' + (h-1) + ' ' +
                'H ' + (r+1) + ' ' +
                'A ' + r + ',' + r + ' 0 0 1 1,' + (h-r-1) + ' ' +
                'V ' + (r+1) + ' ' +
                'A ' + r + ',' + r + ' 0 0 1 ' + (r+1) + ',1';
        
        path.setAttribute('d', d);
        
        var length = path.getTotalLength();
        if (!length) length = 2 * (w + h);
        
        var dash = 80;
        var gap = length + 20;
        
        path.setAttribute('stroke-dasharray', dash + ' ' + gap);
        
        var offsetHidden = dash + 2;
        var offsetHover = -(length + 2);
        
        // Disable transition briefly to avoid sweep-in animation on load
        path.style.transition = 'none';
        path.style.strokeDashoffset = offsetHidden;
        
        // Force reflow
        path.getBoundingClientRect();
        
        // Restore transition
        path.style.transition = 'stroke-dashoffset .9s ease-in-out';
        
        btn.onmouseenter = function() {{
            path.style.strokeDashoffset = offsetHover;
        }};
        btn.onmouseleave = function() {{
            path.style.strokeDashoffset = offsetHidden;
        }};
    }}
    setTimeout(sizePath, 50);
    window.addEventListener('resize', sizePath);
}})();

// ── NAV METRO LINE ──
(function() {{
    var cluster = document.getElementById('navCluster');
    var svg = document.getElementById('navMetro');
    var track = document.getElementById('metroTrack');
    var fill = document.getElementById('metroFillLine');
    var grad = document.getElementById('metroFill');
    var nodeGroup = document.getElementById('metroNodes');
    if (!cluster || !svg || !track || !fill || !nodeGroup) return;

    var links = Array.from(cluster.querySelectorAll('.nav-link'));
    var sections = links.map(function(l) {{
        var id = (l.getAttribute('href') || '').slice(1);
        return id ? document.getElementById(id) : null;
    }});
    if (!links.length) return;

    var Y = 7, NODE_R = 3;
    var isClima = links.map(function(l) {{ return l.classList.contains('nav-link--clima'); }});
    var nodeEls = [];

    function docTop(el) {{ return el.getBoundingClientRect().top + window.pageYOffset; }}
    function centerOf(el) {{
        var c = cluster.getBoundingClientRect();
        var r = el.getBoundingClientRect();
        return r.left - c.left + r.width / 2;
    }}

    function buildNodes() {{
        nodeGroup.innerHTML = '';
        nodeEls = [];
        links.forEach(function() {{
            var nd = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            nd.setAttribute('cy', Y);
            nd.setAttribute('r', NODE_R);
            nd.setAttribute('fill', '#fff');
            nd.setAttribute('stroke', '#E0E0E0');
            nd.setAttribute('stroke-width', 1.5);
            nd.style.transition = 'fill .25s ease, stroke .25s ease, r .2s ease';
            nodeGroup.appendChild(nd);
            nodeEls.push(nd);
        }});
    }}

    function layout() {{
        var c = cluster.getBoundingClientRect();
        svg.setAttribute('viewBox', '0 0 ' + c.width + ' 14');
        var first = centerOf(links[0]);
        var last = centerOf(links[links.length - 1]);
        track.setAttribute('x1', first); track.setAttribute('x2', last);
        grad.setAttribute('x1', first); grad.setAttribute('x2', last);
        nodeEls.forEach(function(nd, i) {{ nd.setAttribute('cx', centerOf(links[i])); }});
    }}

    function update() {{
        if (!nodeEls.length) return;
        var scrollY = window.pageYOffset;
        var trig = window.innerHeight * 0.3;
        var n = sections.length;
        var activeIdx = 0;
        for (var i = 0; i < n; i++) {{
            if (sections[i] && (docTop(sections[i]) - trig) <= scrollY) activeIdx = i;
        }}
        var first = centerOf(links[0]);
        var last = centerOf(links[links.length - 1]);
        var targetX;
        if (activeIdx >= n - 1 || !sections[activeIdx + 1]) {{
            targetX = last;
        }} else {{
            var a = docTop(sections[activeIdx]) - trig;
            var b = docTop(sections[activeIdx + 1]) - trig;
            var p = Math.max(0, Math.min(1, (scrollY - a) / Math.max(1, b - a)));
            var fromX = centerOf(links[activeIdx]);
            var toX = centerOf(links[activeIdx + 1]);
            targetX = fromX + (toX - fromX) * p;
        }}
        fill.setAttribute('x1', first);
        fill.setAttribute('x2', targetX);
        links.forEach(function(link, i) {{
            link.classList.toggle('active', i === activeIdx);
            var nd = nodeEls[i];
            if (!nd) return;
            if (i < activeIdx) {{
                nd.setAttribute('fill', isClima[i] ? '#0373fc' : '#002D62');
                nd.setAttribute('stroke', isClima[i] ? '#0373fc' : '#002D62');
                nd.setAttribute('r', NODE_R);
            }} else if (i === activeIdx) {{
                nd.setAttribute('fill', isClima[i] ? '#0373fc' : '#4A90D9');
                nd.setAttribute('stroke', isClima[i] ? '#0373fc' : '#4A90D9');
                nd.setAttribute('r', NODE_R + 1.5);
            }} else {{
                nd.setAttribute('fill', '#fff');
                nd.setAttribute('stroke', '#E0E0E0');
                nd.setAttribute('r', NODE_R);
            }}
        }});
    }}

    function refresh() {{ buildNodes(); layout(); update(); }}
    setTimeout(refresh, 120);
    window.addEventListener('load', refresh);
    window.addEventListener('scroll', update, {{ passive: true }});
    window.addEventListener('resize', function() {{ layout(); update(); }}, {{ passive: true }});
}})();
</script>

</body>
</html>"""


# ── Writer ─────────────────────────────────────────────────────────────────────

def write_site(results: dict, output_path: str = "docs/index.html") -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    html = build_html(results)
    path.write_text(html, encoding="utf-8")
    size_kb = path.stat().st_size / 1024
    print(f"  Site written: {path} ({size_kb:.1f} KB)")
    return path


if __name__ == "__main__":
    from pipeline.build_vulnerability import run_vulnerability_pipeline
    print("Running pipeline...\n")
    results = run_vulnerability_pipeline()
    output  = write_site(results)
    print(f"\nOpen: {output.resolve()}")