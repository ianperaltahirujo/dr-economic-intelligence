"""
DR Economic Intelligence - Weekly HTML Report Generator
Produces a professional Spanish-language website from pipeline results.
Output: docs/index.html (served by GitHub Pages)

Design: Dominican flag palette (white/black + DR blue #002D62 / DR red #CE1126)
Typography: IBM Plex Sans + IBM Plex Mono
Audience: La Sociedad management (non-technical)
Language: Spanish throughout
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.build_vulnerability import (
    VULNERABILITY_COMPONENTS,
    INDICATOR_LABELS,
    HIGH_STRESS_THRESHOLD,
)

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
    """
    Generate a plain-language Spanish briefing based on current data.
    Template-based: selects sentences based on indicator values and z-scores.
    """
    score      = results.get("current_score", 0)
    score_date = results.get("score_date")
    alerts     = results.get("alerts", pd.DataFrame())

    if score_date:
        date_str = f"{MONTHS_ES[score_date.month]} de {score_date.year}"
    else:
        date_str = "el período más reciente"

    paragraphs = []

    # ── Opening paragraph: overall status ──
    if score >= HIGH_STRESS_THRESHOLD:
        opening = (
            f"El Índice de Vulnerabilidad Económica de la República Dominicana registró "
            f"<strong>{score:.1f} puntos</strong> en {date_str}, superando el umbral de alerta de "
            f"{HIGH_STRESS_THRESHOLD} puntos. Este nivel refleja presiones simultáneas en múltiples "
            f"frentes que merecen atención prioritaria."
        )
    elif score >= 50:
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

    # ── Second paragraph: main drivers ──
    drivers = []
    if not alerts.empty:
        stress_alerts = alerts[alerts["is_stress"] == True]
        for _, alert in stress_alerts.iterrows():
            col   = alert["indicator"]
            label = INDICATOR_DESCRIPTIONS_ES.get(col, (alert.get("label", col), ""))[0]
            z     = alert["zscore"]
            val   = alert["value"]
            _, direction = VULNERABILITY_COMPONENTS.get(col, (0, "positive"))

            if col == "ipc_yoy_pct":
                drivers.append(
                    f"la inflación interanual se mantiene en <strong>{val:.1f}%</strong>, "
                    f"por encima del promedio de los últimos cinco años"
                )
            elif col == "dop_usd":
                drivers.append(
                    f"el tipo de cambio alcanzó <strong>{val:.2f} DOP/USD</strong>, "
                    f"reflejando presión depreciatoria sobre el peso dominicano"
                )
            elif col == "remesas_usd_mm":
                drivers.append(
                    f"las remesas familiares totalizaron <strong>USD {val:.0f} millones</strong>, "
                    f"por debajo de su tendencia reciente"
                )
            elif col == "sb_morosidad_pct":
                drivers.append(
                    f"la morosidad bancaria se ubicó en <strong>{val:.2f}%</strong>, "
                    f"señalando deterioro en la calidad de la cartera de crédito"
                )
            elif col == "UNRATE":
                drivers.append(
                    f"el desempleo en EE.UU. subió a <strong>{val:.1f}%</strong>, "
                    f"lo que podría reducir el flujo de remesas hacia el país"
                )
            elif col == "UMCSENT":
                drivers.append(
                    f"la confianza del consumidor estadounidense cayó a <strong>{val:.1f} puntos</strong>, "
                    f"anticipando posible reducción en el turismo hacia la región"
                )
            elif col == "reserves_usd_mm":
                drivers.append(
                    f"las reservas internacionales se situaron en "
                    f"<strong>USD {val:,.0f} millones</strong>, por debajo de niveles óptimos"
                )

    if drivers:
        driver_text = "Los principales factores que explican este resultado son: " + \
                      "; ".join(drivers) + "."
        paragraphs.append(driver_text)
    else:
        paragraphs.append(
            "No se identificaron indicadores fuera de sus rangos históricos normales durante este período. "
            "La economía dominicana muestra resiliencia ante el entorno internacional."
        )

    # ── Third paragraph: context and forward look ──
    recent = scored[list(VULNERABILITY_COMPONENTS.keys())].dropna(how="all").tail(1)
    if not recent.empty:
        context_parts = []

        remesas_col = "remesas_usd_mm"
        if remesas_col in recent.columns and pd.notna(recent[remesas_col].iloc[0]):
            remesas_val = recent[remesas_col].iloc[0]
            context_parts.append(
                f"las remesas se mantienen en USD {remesas_val:.0f} millones mensuales"
            )

        morosidad_col = "sb_morosidad_pct"
        if morosidad_col in recent.columns and pd.notna(recent[morosidad_col].iloc[0]):
            mor_val = recent[morosidad_col].iloc[0]
            if mor_val < 2.5:
                context_parts.append(
                    f"la morosidad bancaria permanece contenida en {mor_val:.2f}%"
                )

        solvencia_col = "sb_solvencia_pct"
        if solvencia_col in recent.columns and pd.notna(recent[solvencia_col].iloc[0]):
            sol_val = recent[solvencia_col].iloc[0]
            if sol_val > 15:
                context_parts.append(
                    f"el sistema bancario mantiene sólidos niveles de capitalización ({sol_val:.1f}%)"
                )

        if context_parts:
            context_sentence = "Entre los factores de estabilidad destacan que " + \
                               " y ".join(context_parts) + "."
            paragraphs.append(context_sentence)

    # ── Closing ──
    paragraphs.append(
        "Este informe es generado automáticamente cada semana por el sistema de inteligencia "
        "económica de La Sociedad a partir de fuentes oficiales: Banco Central de la República "
        "Dominicana (BCRD), Superintendencia de Bancos (SB) y la Reserva Federal de EE.UU. (FRED)."
    )

    return "</p><p>".join(f"{p}" for p in paragraphs)


# ── Chart data builder ─────────────────────────────────────────────────────────

def build_chart_data(scored: pd.DataFrame) -> str:
    """Build Chart.js dataset from full vulnerability score history."""
    history = scored[["vulnerability_score"]].dropna()

    labels = [f"{MONTHS_ES[d.month].capitalize()} {d.year}" for d in history.index]
    values = [round(v, 1) for v in history["vulnerability_score"].tolist()]
    colors = []
    for v in values:
        if v >= HIGH_STRESS_THRESHOLD:
            colors.append("rgba(206,17,38,0.8)")
        elif v >= 50:
            colors.append("rgba(0,45,98,0.6)")
        else:
            colors.append("rgba(0,45,98,0.3)")

    return json.dumps({
        "labels": labels,
        "values": values,
        "colors": colors,
    })


# ── Indicator cards ────────────────────────────────────────────────────────────

def build_indicator_cards(scored: pd.DataFrame) -> str:
    """Build HTML for the 9 indicator cards."""
    cards = []

    for col, (weight, direction) in VULNERABILITY_COMPONENTS.items():
        zscore_col = f"{col}_zscore"
        if col not in scored.columns:
            continue

        recent = scored[[col, zscore_col]].dropna().tail(1)
        if recent.empty:
            continue

        value  = recent[col].iloc[0]
        zscore = recent[zscore_col].iloc[0]

        es_label, es_desc = INDICATOR_DESCRIPTIONS_ES.get(
            col, (INDICATOR_LABELS.get(col, col), "")
        )

        # Stress status
        is_stress = (
            (direction == "positive" and zscore > 1.5) or
            (direction == "negative" and zscore < -1.5)
        )
        is_watch = abs(zscore) > 0.75 and not is_stress

        if is_stress:
            status_label = "ALERTA"
            status_class = "status-stress"
        elif is_watch:
            status_label = "VIGILANCIA"
            status_class = "status-watch"
        else:
            status_label = "NORMAL"
            status_class = "status-normal"

        # Format value
        if col in ["remesas_usd_mm", "reserves_usd_mm"]:
            value_str = f"USD {value:,.0f}M"
        elif col in ["ipc_yoy_pct", "dop_usd", "sb_morosidad_pct",
                     "sb_solvencia_pct", "UNRATE"]:
            value_str = f"{value:.2f}%"if col != "dop_usd" else f"{value:.2f}"
        elif col == "UMCSENT":
            value_str = f"{value:.1f}"
        else:
            value_str = f"{value:.2f}"

        # Z-score bar: -3 to +3 mapped to 0-100%
        bar_pct   = max(0, min(100, (zscore + 3) / 6 * 100))
        bar_color = "#CE1126" if is_stress else ("#002D62" if is_watch else "#666")

        # Trend arrow
        col_history = scored[col].dropna().tail(3)
        if len(col_history) >= 2:
            delta = col_history.iloc[-1] - col_history.iloc[-2]
            if direction == "positive":
                arrow = "↑" if delta > 0 else "↓"
                arrow_class = "arrow-bad" if delta > 0 else "arrow-good"
            else:
                arrow = "↑" if delta > 0 else "↓"
                arrow_class = "arrow-good" if delta > 0 else "arrow-bad"
        else:
            arrow = "–"
            arrow_class = ""

        card = f"""
        <div class="indicator-card interactive-card {'card-stress' if is_stress else ''}" onclick="toggleAccordion(this)">
            <div class="card-header">
                <span class="card-label">{es_label}</span>
                <div style="display:flex; align-items:center; gap:8px;">
                    <span class="status-badge {status_class}">{status_label}</span>
                    <span class="dropdown-arrow">▼</span>
                </div>
            </div>
            <div class="card-value">
                <span class="value-number">{value_str}</span>
                <span class="value-arrow {arrow_class}">{arrow}</span>
            </div>
            <div class="zscore-bar-container">
                <div class="zscore-bar" style="width:{bar_pct:.1f}%; background:{bar_color};"></div>
            </div>
            <div class="accordion-content">
                <div class="zscore-label" style="margin-top:14px;">Z-score: {zscore:+.2f} &nbsp;|&nbsp; Peso: {weight*100:.0f}%</div>
                <div class="card-desc" style="border-top:none; padding-top:0;">{es_desc}</div>
            </div>
        </div>"""
        cards.append(card)

    return "\n".join(cards)


# ── Alert items ────────────────────────────────────────────────────────────────

def build_alert_items(alerts: pd.DataFrame) -> str:
    """Build HTML for alert panel."""
    if alerts.empty:
        return """
        <div class="no-alerts">
            <span class="no-alerts-icon">✓</span>
            Ningún indicador supera el umbral de alerta esta semana.
        </div>"""

    items = []
    for _, alert in alerts.iterrows():
        col   = alert["indicator"]
        label = INDICATOR_DESCRIPTIONS_ES.get(col, (alert.get("label", col), ""))[0]
        is_stress = alert["is_stress"]
        z     = alert["zscore"]
        val   = alert["value"]

        direction_word = "por encima" if z > 0 else "por debajo"
        alert_class    = "alert-stress" if is_stress else "alert-watch"
        alert_tag      = "ALERTA" if is_stress else "VIGILANCIA"

        items.append(f"""
        <div class="alert-item {alert_class}">
            <div class="alert-tag">{alert_tag}</div>
            <div class="alert-content">
                <strong>{label}</strong>
                <span class="alert-text">
                    {abs(z):.1f} desviaciones estándar {direction_word} de su promedio histórico
                    (valor actual: {val:.2f})
                </span>
            </div>
        </div>""")

    return "\n".join(items)


# ── Full HTML ──────────────────────────────────────────────────────────────────

def build_html(results: dict) -> str:
    scored     = results.get("scored", pd.DataFrame())
    score      = results.get("current_score", 0) or 0
    score_date = results.get("score_date")
    alerts     = results.get("alerts", pd.DataFrame())

    if score >= HIGH_STRESS_THRESHOLD:
        status_key = "HIGH"
    elif score >= 50:
        status_key = "MODERATE"
    else:
        status_key = "LOW"

    status_label, status_desc = STATUS_TEXT_ES[status_key]
    score_color = "#CE1126" if status_key == "HIGH" else \
                  "#002D62" if status_key == "MODERATE" else "#1A1A1A"

    date_str = ""
    if score_date:
        date_str = (f"{MONTHS_ES[score_date.month].capitalize()} "
                    f"de {score_date.year}")

    run_date  = datetime.now().strftime("%d/%m/%Y a las %H:%M")
    briefing  = generate_briefing(results, scored)
    chart_data = build_chart_data(scored)
    cards     = build_indicator_cards(scored)
    alert_html = build_alert_items(alerts)

    alert_count = len(alerts) if alerts is not None and not alerts.empty else 0
    stress_count = int(alerts["is_stress"].sum()) if alert_count > 0 else 0

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DR Economic Intelligence — La Sociedad</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8/hammer.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
    <style>
        /* ── Reset & base ── */
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        :root {{
            --blue:       #002D62;
            --red:        #CE1126;
            --black:      #0A0A0A;
            --white:      #FFFFFF;
            --gray-50:    #F9F9F9;
            --gray-100:   #F0F0F0;
            --gray-200:   #E0E0E0;
            --gray-400:   #999999;
            --gray-600:   #555555;
            --blue-tint:  #EEF2F8;
            --red-tint:   #FDF0F2;
            --font-sans:  'IBM Plex Sans', system-ui, sans-serif;
            --font-mono:  'IBM Plex Mono', monospace;
        }}

        html {{ font-size: 16px; }}
        body {{
            font-family: var(--font-sans);
            background: var(--white);
            color: var(--black);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}

        /* ── Scroll Animations ── */
        .fade-in-section {{
            opacity: 0;
            transform: translateY(20px);
            transition: opacity 0.8s ease-out, transform 0.8s ease-out;
            will-change: opacity, visibility;
        }}
        .fade-in-section.is-visible {{
            opacity: 1;
            transform: none;
        }}

        /* ── Accordion / Dropdown Components ── */
        .accordion-content {{
            max-height: 0;
            overflow: hidden;
            opacity: 0;
            transition: max-height 0.4s ease, opacity 0.4s ease;
        }}
        .accordion-content.open {{
            opacity: 1;
        }}
        .dropdown-arrow {{
            font-size: 10px;
            color: var(--gray-400);
            transition: transform 0.3s ease;
            user-select: none;
        }}
        .interactive-card, .interactive-legend {{
            cursor: pointer;
            transition: background 0.2s ease, transform 0.1s ease;
            -webkit-tap-highlight-color: transparent;
        }}
        .interactive-card:hover, .interactive-legend:hover {{
            background: var(--gray-50);
        }}
        .interactive-card.active .dropdown-arrow, .interactive-legend.active .dropdown-arrow {{
            transform: rotate(180deg);
        }}

        /* ── Top stripe ── */
        .top-stripe {{
            height: 4px;
            background: linear-gradient(90deg, var(--blue) 0%, var(--blue) 50%, var(--red) 50%, var(--red) 100%);
        }}

        /* ── Header ── */
        .site-header {{
            border-bottom: 1px solid var(--gray-200);
            padding: 24px 0;
        }}
        .header-inner {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 0 40px;
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 16px;
            flex-wrap: wrap;
        }}
        .header-brand {{
            font-family: var(--font-mono);
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--blue);
        }}
        .header-meta {{
            font-size: 12px;
            color: var(--gray-400);
            font-family: var(--font-mono);
        }}

        /* ── Layout ── */
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 0 40px;
        }}

        section {{ padding: 64px 0; border-bottom: 1px solid var(--gray-200); }}
        section:last-child {{ border-bottom: none; }}

        .section-label {{
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--gray-400);
            margin-bottom: 32px;
        }}

        /* ── Page title ── */
        .page-title {{
            font-size: 42px;
            font-weight: 300;
            letter-spacing: -0.5px;
            color: var(--black);
            line-height: 1.15;
            margin-bottom: 48px;
        }}
        .page-title strong {{
            font-weight: 600;
            color: var(--blue);
        }}

        /* ── Score hero ── */
        .score-hero {{
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 56px;
            align-items: start;
        }}
        .score-number-block {{
            border-left: 4px solid {score_color};
            padding-left: 28px;
        }}
        .score-number {{
            font-family: var(--font-mono);
            font-size: 96px;
            font-weight: 600;
            line-height: 1;
            color: {score_color};
            letter-spacing: -2px;
        }}
        .score-denom {{
            font-family: var(--font-mono);
            font-size: 20px;
            color: var(--gray-400);
        }}
        .score-date {{
            font-size: 14px;
            color: var(--gray-400);
            margin-top: 10px;
            font-family: var(--font-mono);
        }}
        .score-status {{ margin-top: 0; }}
        .status-title {{
            font-size: 32px;
            font-weight: 600;
            color: {score_color};
            margin-bottom: 12px;
            line-height: 1.2;
        }}
        .status-desc {{
            font-size: 17px;
            color: var(--gray-600);
            max-width: 520px;
            line-height: 1.7;
        }}
        .alert-count {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-top: 20px;
            padding: 8px 16px;
            background: {'var(--red-tint)' if stress_count > 0 else 'var(--gray-100)'};
            border: 1px solid {'var(--red)' if stress_count > 0 else 'var(--gray-200)'};
            font-size: 14px;
            color: {'var(--red)' if stress_count > 0 else 'var(--gray-600)'};
            font-family: var(--font-mono);
        }}

        /* ── Briefing ── */
        .briefing-text {{
            font-size: 17px;
            line-height: 1.85;
            color: var(--black);
            max-width: 780px;
        }}
        .briefing-text p {{
            margin-bottom: 20px;
        }}
        .briefing-text p:last-child {{
            margin-bottom: 0;
            color: var(--gray-600);
            font-size: 14px;
            line-height: 1.7;
        }}

        /* ── Alerts ── */
        .alerts-list {{ display: flex; flex-direction: column; gap: 16px; }}
        .alert-item {{
            display: grid;
            grid-template-columns: 100px 1fr;
            gap: 20px;
            align-items: start;
            padding: 20px 24px;
            border: 1px solid var(--gray-200);
        }}
        .alert-stress {{ border-left: 3px solid var(--red); background: var(--red-tint); }}
        .alert-watch  {{ border-left: 3px solid var(--blue); background: var(--blue-tint); }}
        .alert-tag {{
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.1em;
            padding-top: 2px;
        }}
        .alert-stress .alert-tag {{ color: var(--red); }}
        .alert-watch  .alert-tag {{ color: var(--blue); }}
        .alert-content {{ display: flex; flex-direction: column; gap: 6px; }}
        .alert-content strong {{ font-size: 16px; font-weight: 600; }}
        .alert-text {{ font-size: 14px; color: var(--gray-600); line-height: 1.6; }}
        .no-alerts {{
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 24px;
            background: var(--gray-50);
            border: 1px solid var(--gray-200);
            font-size: 15px;
            color: var(--gray-600);
        }}
        .no-alerts-icon {{ font-size: 20px; color: #2E7D32; }}

        /* ── Indicator cards ── */
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }}
        .indicator-card {{
            padding: 28px;
            border: 1px solid var(--gray-200);
            background: var(--white);
        }}
        .card-stress {{ border-color: var(--red); background: var(--red-tint); }}
        .card-stress:hover {{ background: #fae8eb; }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 10px;
            margin-bottom: 16px;
        }}
        .card-label {{
            font-size: 15px;
            font-weight: 600;
            color: var(--black);
            line-height: 1.3;
        }}
        .status-badge {{
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.1em;
            padding: 4px 8px;
            white-space: nowrap;
            flex-shrink: 0;
        }}
        .status-stress {{ background: var(--red);  color: var(--white); }}
        .status-watch  {{ background: var(--blue); color: var(--white); }}
        .status-normal {{ background: var(--gray-100); color: var(--gray-600); }}
        .card-value {{
            display: flex;
            align-items: baseline;
            gap: 10px;
            margin-bottom: 16px;
        }}
        .value-number {{
            font-family: var(--font-mono);
            font-size: 28px;
            font-weight: 600;
            color: var(--black);
        }}
        .value-arrow {{ font-size: 18px; }}
        .arrow-bad  {{ color: var(--red); }}
        .arrow-good {{ color: #2E7D32; }}
        .zscore-bar-container {{
            height: 4px;
            background: var(--gray-200);
            margin-bottom: 8px;
        }}
        .zscore-bar {{ height: 100%; transition: width 0.3s; }}
        .zscore-label {{
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--gray-400);
            margin-bottom: 14px;
        }}
        .card-desc {{
            font-size: 13px;
            color: var(--gray-600);
            line-height: 1.6;
        }}

        /* ── Legend ── */
        .legend-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-bottom: 40px;
        }}
        .legend-item {{
            padding: 20px;
            background: var(--gray-50);
            border: 1px solid var(--gray-200);
        }}
        .legend-title {{
            font-size: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-dot {{
            width: 9px;
            height: 9px;
            border-radius: 50%;
            flex-shrink: 0;
        }}
        .legend-desc {{ font-size: 13px; color: var(--gray-600); line-height: 1.6; margin-top: 12px; }}

        /* ── Chart ── */
        .chart-container {{ position: relative; height: 360px; }}
        .chart-controls {{
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }}
        .chart-btn {{
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.08em;
            padding: 6px 14px;
            border: 1px solid var(--gray-200);
            background: var(--white);
            color: var(--black);
            cursor: pointer;
            transition: background 0.15s;
        }}
        .chart-btn:hover {{ background: var(--gray-100); }}
        .chart-btn.active {{ background: var(--blue); color: var(--white); border-color: var(--blue); }}
        .chart-hint {{
            font-size: 12px;
            color: var(--gray-400);
            font-family: var(--font-mono);
            margin-top: 10px;
        }}

        /* ── Footer ── */
        .site-footer {{
            padding: 40px 0;
            background: var(--gray-50);
            border-top: 1px solid var(--gray-200);
        }}
        .footer-inner {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 0 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            flex-wrap: wrap;
        }}
        .footer-sources {{
            font-size: 13px;
            color: var(--black);
            line-height: 1.7;
        }}
        .footer-sources strong {{ color: var(--black); font-weight: 600; }}
        .footer-run {{ font-family: var(--font-mono); font-size: 11px; color: var(--black); }}

        /* ── Responsive ── */
        @media (max-width: 900px) {{
            .score-hero {{ grid-template-columns: 1fr; gap: 32px; }}
            .score-number {{ font-size: 72px; }}
            .cards-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .legend-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .page-title {{ font-size: 32px; }}
        }}
        @media (max-width: 600px) {{
            .container {{ padding: 0 20px; }}
            .header-inner {{ padding: 0 20px; }}
            .cards-grid {{ grid-template-columns: 1fr; }}
            .legend-grid {{ grid-template-columns: 1fr; }}
            .score-number {{ font-size: 56px; }}
            .alert-item {{ grid-template-columns: 1fr; }}
            .page-title {{ font-size: 26px; }}
        }}
    </style>
</head>
<body>

<div class="top-stripe"></div>

<header class="site-header">
    <div class="header-inner">
        <div class="header-brand">La Sociedad — DR Economic Intelligence</div>
        <div class="header-meta">Actualizado: {run_date}</div>
    </div>
</header>

<main>

    <section>
        <div class="container">
            <div class="section-label">Índice de Vulnerabilidad Económica</div>
            <div class="page-title">DR <strong>Economic Intelligence</strong><br>Monitor Semanal</div>
            <div class="score-hero">
                <div class="score-number-block">
                    <div class="score-number">{score:.0f}<span class="score-denom">/100</span></div>
                    <div class="score-date">{date_str}</div>
                </div>
                <div class="score-status">
                    <div class="status-title">{status_label}</div>
                    <div class="status-desc">{status_desc}</div>
                    <div class="alert-count">
                        {f'⚠ {stress_count} indicador{"es" if stress_count != 1 else ""} en zona de alerta' if stress_count > 0 else '✓ Sin alertas activas'}
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section>
        <div class="container">
            <div class="section-label">Análisis semanal</div>
            <div class="briefing-text">
                <p>{briefing}</p>
            </div>
        </div>
    </section>

    <section>
        <div class="container">
            <div class="section-label">Indicadores en seguimiento</div>
            <div class="alerts-list">
                {alert_html}
            </div>
        </div>
    </section>

    <section>
        <div class="container">
            <div class="section-label">Panel de indicadores</div>

            <div class="legend-grid">
                <div class="legend-item interactive-legend" onclick="toggleAccordion(this)">
                    <div class="legend-title">
                        <div class="legend-dot" style="background:var(--red)"></div>
                        ALERTA <span class="dropdown-arrow" style="margin-left: auto;">▼</span>
                    </div>
                    <div class="accordion-content">
                        <div class="legend-desc">El indicador supera 1.5 desviaciones estándar de su promedio histórico en dirección de estrés.</div>
                    </div>
                </div>
                <div class="legend-item interactive-legend" onclick="toggleAccordion(this)">
                    <div class="legend-title">
                        <div class="legend-dot" style="background:var(--blue)"></div>
                        VIGILANCIA <span class="dropdown-arrow" style="margin-left: auto;">▼</span>
                    </div>
                    <div class="accordion-content">
                        <div class="legend-desc">El indicador muestra desviación notable pero sin superar el umbral de alerta. Requiere seguimiento.</div>
                    </div>
                </div>
                <div class="legend-item interactive-legend" onclick="toggleAccordion(this)">
                    <div class="legend-title">
                        <div class="legend-dot" style="background:var(--gray-400)"></div>
                        NORMAL <span class="dropdown-arrow" style="margin-left: auto;">▼</span>
                    </div>
                    <div class="accordion-content">
                        <div class="legend-desc">El indicador se encuentra dentro de sus rangos históricos habituales. No representa riesgo inmediato.</div>
                    </div>
                </div>
                <div class="legend-item interactive-legend" onclick="toggleAccordion(this)">
                    <div class="legend-title">Z-score <span class="dropdown-arrow" style="margin-left: auto;">▼</span></div>
                    <div class="accordion-content">
                        <div class="legend-desc">Mide cuántas desviaciones estándar se aleja el valor actual de su promedio histórico. Valores extremos (+3 o -3) indican condiciones inusuales.</div>
                    </div>
                </div>
                <div class="legend-item interactive-legend" onclick="toggleAccordion(this)">
                    <div class="legend-title">Peso <span class="dropdown-arrow" style="margin-left: auto;">▼</span></div>
                    <div class="accordion-content">
                        <div class="legend-desc">Contribución porcentual de cada indicador al índice total. Indicadores más relevantes para la economía dominicana reciben mayor peso.</div>
                    </div>
                </div>
                <div class="legend-item interactive-legend" onclick="toggleAccordion(this)">
                    <div class="legend-title">↑ ↓ Tendencia <span class="dropdown-arrow" style="margin-left: auto;">▼</span></div>
                    <div class="accordion-content">
                        <div class="legend-desc">Dirección del cambio respecto al mes anterior. En rojo si el movimiento es desfavorable; en verde si es favorable.</div>
                    </div>
                </div>
            </div>

            <div class="cards-grid">
                {cards}
            </div>
        </div>
    </section>

    <section>
        <div class="container">
            <div class="section-label">Historial completo del índice</div>
            <div class="chart-controls">
                <button class="chart-btn" onclick="setRange(12)">12 meses</button>
                <button class="chart-btn" onclick="setRange(24)">24 meses</button>
                <button class="chart-btn" onclick="setRange(36)">36 meses</button>
                <button class="chart-btn active" onclick="setRange(0)">Todo</button>
                <button class="chart-btn" onclick="resetZoom()">Restablecer zoom</button>
            </div>
            <div class="chart-container">
                <canvas id="scoreChart"></canvas>
            </div>
            <div class="chart-hint">Desplácese para hacer zoom · Arrastre para navegar</div>
        </div>
    </section>

</main>

<footer class="site-footer">
    <div class="footer-inner">
        <div class="footer-sources">
            <strong>Fuentes:</strong> Banco Central de la República Dominicana (BCRD) ·
            Superintendencia de Bancos (SB) · Reserva Federal de EE.UU. (FRED)<br>
            El índice combina 9 indicadores macroeconómicos y financieros ponderados por su relevancia
            para la economía dominicana. Metodología disponible en el repositorio del proyecto.
        </div>
        <div class="footer-run">Generado: {run_date}</div>
    </div>
</footer>

<script>
// --- UI Interaction Logic ---
function toggleAccordion(element) {{
    element.classList.toggle('active');
    const content = element.querySelector('.accordion-content');
    if (content.classList.contains('open')) {{
        content.classList.remove('open');
        content.style.maxHeight = null;
    }} else {{
        content.classList.add('open');
        content.style.maxHeight = content.scrollHeight + "px";
    }}
}}

// --- Scroll Animations Logic ---
document.addEventListener("DOMContentLoaded", function() {{
    const observer = new IntersectionObserver((entries) => {{
        entries.forEach(entry => {{
            if (entry.isIntersecting) {{
                entry.target.classList.add('is-visible');
            }}
        }});
    }}, {{ threshold: 0.15 }});

    document.querySelectorAll('section').forEach(sec => {{
        sec.classList.add('fade-in-section');
        observer.observe(sec);
    }});
}});

// --- Chart Logic ---
const chartData = {chart_data};

const ctx = document.getElementById('scoreChart').getContext('2d');
const scoreChart = new Chart(ctx, {{
    type: 'line',
    data: {{
        labels: chartData.labels,
        datasets: [{{
            label: 'Índice de Vulnerabilidad',
            data: chartData.values,
            borderColor: '#002D62',
            backgroundColor: 'rgba(0,45,98,0.06)',
            borderWidth: 2,
            pointBackgroundColor: chartData.colors,
            pointBorderColor: chartData.colors,
            pointRadius: 3,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.3,
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{ display: false }},
            tooltip: {{
                backgroundColor: '#0A0A0A',
                titleColor: '#FFFFFF',
                bodyColor: '#CCCCCC',
                padding: 12,
                callbacks: {{
                    label: ctx => `Índice: ${{ctx.parsed.y}} / 100`
                }}
            }},
            zoom: {{
                zoom: {{
                    wheel: {{ enabled: true }},
                    pinch: {{ enabled: true }},
                    mode: 'x',
                }},
                pan: {{
                    enabled: true,
                    mode: 'x',
                }},
            }}
        }},
        scales: {{
            x: {{
                grid: {{ color: 'rgba(0,0,0,0.05)' }},
                ticks: {{
                    font: {{ family: 'IBM Plex Mono', size: 11 }},
                    color: '#0A0A0A',
                    maxTicksLimit: 18,
                    maxRotation: 45,
                }}
            }},
            y: {{
                min: 0, max: 100,
                grid: {{ color: 'rgba(0,0,0,0.05)' }},
                ticks: {{
                    font: {{ family: 'IBM Plex Mono', size: 11 }},
                    color: '#0A0A0A',
                    callback: val => val + '/100'
                }},
            }}
        }},
    }}
}});

// Draw threshold line manually after render
const originalDraw = scoreChart.draw.bind(scoreChart);
scoreChart.draw = function() {{
    originalDraw();
    const chart = scoreChart;
    const ctx2 = chart.ctx;
    const yScale = chart.scales.y;
    const xScale = chart.scales.x;
    const y = yScale.getPixelForValue({HIGH_STRESS_THRESHOLD});
    ctx2.save();
    ctx2.beginPath();
    ctx2.moveTo(xScale.left, y);
    ctx2.lineTo(xScale.right, y);
    ctx2.strokeStyle = 'rgba(206,17,38,0.35)';
    ctx2.lineWidth = 1;
    ctx2.setLineDash([5, 5]);
    ctx2.stroke();
    ctx2.restore();
}};

function setRange(months) {{
    document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    scoreChart.resetZoom();
    if (months === 0) {{
        scoreChart.data.labels = chartData.labels;
        scoreChart.data.datasets[0].data = chartData.values;
        scoreChart.data.datasets[0].pointBackgroundColor = chartData.colors;
        scoreChart.data.datasets[0].pointBorderColor = chartData.colors;
    }} else {{
        const n = months;
        scoreChart.data.labels = chartData.labels.slice(-n);
        scoreChart.data.datasets[0].data = chartData.values.slice(-n);
        scoreChart.data.datasets[0].pointBackgroundColor = chartData.colors.slice(-n);
        scoreChart.data.datasets[0].pointBorderColor = chartData.colors.slice(-n);
    }}
    scoreChart.update();
}}

function resetZoom() {{
    scoreChart.resetZoom();
}}
</script>

</body>
</html>"""


# ── Writer ─────────────────────────────────────────────────────────────────────

def write_site(results: dict, output_path: str = "docs/index.html") -> Path:
    """
    Write the HTML report to docs/index.html for GitHub Pages.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    html = build_html(results)
    path.write_text(html, encoding="utf-8")

    size_kb = path.stat().st_size / 1024
    print(f"  Site written: {path} ({size_kb:.1f} KB)")
    return path


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from pipeline.build_vulnerability import run_vulnerability_pipeline

    print("Running pipeline...\n")
    results = run_vulnerability_pipeline()
    output  = write_site(results)
    print(f"\nOpen: {output.resolve()}")