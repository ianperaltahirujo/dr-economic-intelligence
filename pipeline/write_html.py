"""
DR Economic Intelligence - Weekly HTML Report Generator
Produces a professional Spanish-language website from pipeline results.
Output: docs/index.html (served by GitHub Pages)

Design: Dominican flag palette (white/black + DR blue #002D62 / DR red #CE1126)
Typography: Haffer (body/UI) + Reckless (display)
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
    classify_indicator
)

# ── Hero logo ────────────────────────────────────────────────
HERO_LOGO_SRC = "hero_logo.png"

# ── Classification thresholds (z-score magnitudes) ──────────────────────────────
# Shared by the indicator cards and the summary counts so the panel and the
# at-a-glance chips can never disagree.
STRESS_Z_THRESHOLD = 1.5
WATCH_Z_THRESHOLD = 0.75
MODERATE_SCORE_THRESHOLD = 50  # score at/above this = moderate stress band

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
        "Valores por encima del 7% indican presión inflacionaria significativa."
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
    "sb_tasa_activa_pct": (
        "Tasa de Interés Activa",
        "Tasa de interés promedio ponderada cobrada por los bancos en préstamos. "
        "Un aumento encarece el crédito, frena el consumo y aumenta la carga financiera de hogares y empresas."
    ),
    "gas_premium_dop": (
        "Precio Gasolina Premium",
        "Precio oficial por galón fijado por el MICM. Las alzas reflejan choques petroleros externos y se traducen en mayores costos logísticos e inflación generalizada."
    ),
    "tourism_daily_spend_usd": (
        "Gasto Turístico Diario",
        "Gasto promedio diario (en USD) de visitantes extranjeros. Una caída señala debilidad en la principal industria exportadora y menor entrada de divisas a la economía."
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
    elif score >= MODERATE_SCORE_THRESHOLD:
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
                drivers.append(f"la inflación interanual se mantiene en <strong>{val:.1f}%</strong>")
            elif col == "dop_usd":
                drivers.append(f"el tipo de cambio alcanzó <strong>{val:.2f} DOP/USD</strong>")
            elif col == "remesas_usd_mm":
                drivers.append(f"las remesas cayeron a <strong>USD {val:.0f}M</strong>")
            elif col == "sb_morosidad_pct":
                drivers.append(f"la morosidad bancaria subió a <strong>{val:.2f}%</strong>")
            elif col == "UNRATE":
                drivers.append(f"el desempleo en EE.UU. subió a <strong>{val:.1f}%</strong>")
            elif col == "gas_premium_dop":
                drivers.append(f"la gasolina premium alcanzó <strong>DOP {val:.1f}</strong>")
            elif col == "sb_tasa_activa_pct":
                drivers.append(f"la tasa activa promedia <strong>{val:.2f}%</strong>")

    if drivers:
        paragraphs.append("Los principales factores que explican este resultado son: " + "; ".join(drivers) + ".")
    else:
        paragraphs.append("No se identificaron indicadores fuera de sus rangos históricos normales durante este período. La economía dominicana muestra resiliencia ante el entorno internacional.")

    if score_date and score_date in scored.index:
        recent = scored.loc[[score_date]]
        context_parts = []
        if "remesas_usd_mm" in recent.columns and pd.notna(recent["remesas_usd_mm"].iloc[0]):
            context_parts.append(f"las remesas se mantienen en USD {recent['remesas_usd_mm'].iloc[0]:.0f} millones mensuales")
        if "sb_morosidad_pct" in recent.columns and pd.notna(recent["sb_morosidad_pct"].iloc[0]):
            mor_val = recent["sb_morosidad_pct"].iloc[0]
            if mor_val < 2.5:
                context_parts.append(f"la morosidad bancaria permanece contenida en {mor_val:.2f}%")
        if context_parts:
            paragraphs.append("Entre los factores de estabilidad destacan que " + " y ".join(context_parts) + ".")

    paragraphs.append("Este informe es generado automáticamente cada semana por el sistema de inteligencia económica de La Sociedad.")

    return "</p><p>".join(f"{p}" for p in paragraphs)


# ── Chart data builder ─────────────────────────────────────────────────────────

def build_chart_data(scored: pd.DataFrame) -> str:
    history = scored[["vulnerability_score"]].dropna()
    labels = [f"{MONTHS_ES[d.month].capitalize()} {d.year}" for d in history.index]
    values = [round(v, 1) for v in history["vulnerability_score"].tolist()]
    colors = []
    for v in values:
        if v >= HIGH_STRESS_THRESHOLD:
            colors.append("rgba(206,17,38,0.8)")
        elif v >= MODERATE_SCORE_THRESHOLD:
            colors.append("rgba(0,45,98,0.6)")
        else:
            colors.append("rgba(0,45,98,0.3)")
    return json.dumps({"labels": labels, "values": values, "colors": colors})


# ── Context Cards Builder ──────────────────────────────────────────────────────

def get_sparkline_data(df, col, n=24):
    if df is None or df.empty or col not in df.columns:
        return "[]"
    vals = df[col].dropna().tail(n).tolist()
    return json.dumps([round(v, 2) for v in vals])


def build_context_cards(results: dict) -> str:
    cards = []
    tourism_fiscal = results.get("tourism_fiscal", pd.DataFrame())
    debt           = results.get("debt_detail", pd.DataFrame())

    # 1. Deuda Pública
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
                </div>
            </div>""")

    # 2. Turismo
    if not tourism_fiscal.empty:
        recent_fisc = tourism_fiscal.dropna(subset=["tourism_fiscal_rdm"]).tail(13)
        if not recent_fisc.empty:
            val_fisc   = recent_fisc["tourism_fiscal_rdm"].iloc[-1]
            spark_fisc = get_sparkline_data(tourism_fiscal, "tourism_fiscal_rdm", n=24)
            fisc_12m   = recent_fisc["tourism_fiscal_rdm"].tail(12).mean()
            cards.append(f"""
            <div class="context-card interactive-card" data-group="context-group" onclick="toggleAccordion(this)">
                <div class="card-header">
                    <span class="card-label">Sector Turismo (Fiscal)</span>
                    <span class="dropdown-arrow" aria-hidden="true">&#9660;</span>
                </div>
                <div class="context-item"><div class="ci-info"><span class="ci-label">Recaudación Fiscal</span><span class="ci-value">DOP {val_fisc:,.0f}M</span></div><div class="ci-chart"><canvas class="sparkline" data-chart='{spark_fisc}'></canvas></div></div>
                <div class="accordion-content">
                    <div class="context-stats">
                        <div class="context-row"><span>Promedio 12 meses:</span> <strong>DOP {fisc_12m:,.0f}M</strong></div>
                    </div>
                </div>
            </div>""")

    return "\n".join(cards)


# ── Indicator classification & cards ────────────────────────────────────────────

def count_indicator_statuses(scored: pd.DataFrame):
    """Count indicators in each status band using the same rules as the cards."""
    stress = watch = normal = 0
    for col, (weight, direction) in VULNERABILITY_COMPONENTS.items():
        zscore_col = f"{col}_zscore"
        if col not in scored.columns:
            continue
        recent = scored[[col, zscore_col]].dropna().tail(1)
        if recent.empty:
            continue
        zscore = recent[zscore_col].iloc[0]
        is_stress = ((direction == "positive" and zscore > STRESS_Z_THRESHOLD) or
                     (direction == "negative" and zscore < -STRESS_Z_THRESHOLD))
        is_watch = abs(zscore) > WATCH_Z_THRESHOLD and not is_stress
        if is_stress:
            stress += 1
        elif is_watch:
            watch += 1
        else:
            normal += 1
    return stress, watch, normal


def build_indicator_cards(scored: pd.DataFrame, score_date) -> str:
    cards = []
    if score_date not in scored.index: return ""
    row = scored.loc[score_date]
    for col, (weight, direction) in VULNERABILITY_COMPONENTS.items():
        z_col = f"{col}_zscore"
        if col not in row or z_col not in row or pd.isna(row[col]): continue
        val, z = row[col], row[z_col]
        classification = classify_indicator(col, val, z)
        es_label, es_desc = INDICATOR_DESCRIPTIONS_ES.get(col, (INDICATOR_LABELS.get(col, col), ""))
        
        if classification["is_stress"]: status_label, status_class, data_status = "ALERTA", "status-stress", "stress"
        elif classification["is_watch"]: status_label, status_class, data_status = "VIGILANCIA", "status-watch", "watch"
        else: status_label, status_class, data_status = "NORMAL", "status-normal", "normal"
        
        if col in ["remesas_usd_mm", "reserves_usd_mm"]: value_str = f"USD {val:,.0f}M"
        elif col in ["ipc_yoy_pct", "sb_morosidad_pct", "sb_solvencia_pct", "UNRATE", "sb_tasa_activa_pct"]: value_str = f"{val:.2f}%"
        elif col == "gas_premium_dop": value_str = f"DOP {val:.1f}"
        elif col == "tourism_daily_spend_usd": value_str = f"USD {val:.1f}"
        else: value_str = f"{val:.2f}"
        
        bar_pct = classification["contribution"] * 100
        bar_color = "var(--red)" if classification["is_stress"] else ("var(--blue)" if classification["is_watch"] else "var(--gray-400)")
        
        prev_idx = scored.index[scored.index < score_date]
        delta = val - scored.loc[prev_idx[-1], col] if not prev_idx.empty else 0
        if delta == 0: arrow, arrow_class = "&#8211;", ""
        elif direction == "positive": arrow, arrow_class = ("&#8593;","arrow-bad") if delta > 0 else ("&#8595;","arrow-good")
        else: arrow, arrow_class = ("&#8593;","arrow-good") if delta > 0 else ("&#8595;","arrow-bad")
        
        cards.append(f"""
        <div class="indicator-card interactive-card {'card-stress' if classification['is_stress'] else ''}" data-status="{data_status}" onclick="toggleAccordion(this)">
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
                <div class="zscore-label">Z-score: {z:+.2f} &nbsp;|&nbsp; Peso: {weight*100:.0f}%</div>
                <div class="card-desc" style="border-top:none;padding-top:0;">{es_desc}</div>
            </div>
        </div>""")
    return "\n".join(cards)


# ── Alert items ────────────────────────────────────────────────────────────────

def build_alert_items(alerts: pd.DataFrame) -> str:
    if alerts.empty: return '''<div class="no-alerts"><span class="no-alerts-icon">&#10003;</span>Ningún indicador supera el umbral de alerta esta semana.</div>'''
    return "\n".join([f"""<div class="alert-item {"alert-stress" if a['is_stress'] else "alert-watch"}"><div class="alert-tag">{"ALERTA" if a['is_stress'] else "VIGILANCIA"}</div><div class="alert-content"><strong>{INDICATOR_DESCRIPTIONS_ES.get(a['indicator'], (a['label'],))[0]}</strong><span class="alert-text">{a['alert_text']}</span></div></div>""" for _, a in alerts.iterrows()])


# ── Full HTML ──────────────────────────────────────────────────────────────────

def build_html(results: dict) -> str:
    scored     = results.get("scored", pd.DataFrame())
    score      = results.get("current_score", 0) or 0
    score_date = results.get("score_date")
    alerts     = results.get("alerts", pd.DataFrame())

    score_history = scored["vulnerability_score"].dropna().tail(2)
    if len(score_history) >= 2:
        delta = score - score_history.iloc[-2]
        if delta > 0.05:    trend_arrow, trend_class, trend_text = "&#8593;", "trend-bad",     f"+{delta:.1f} pts vs mes anterior"
        elif delta < -0.05: trend_arrow, trend_class, trend_text = "&#8595;", "trend-good",    f"{delta:.1f} pts vs mes anterior"
        else:               trend_arrow, trend_class, trend_text = "&#8211;","trend-neutral",  "Sin cambios vs mes anterior"
    else:
        trend_arrow, trend_class, trend_text = "", "trend-neutral", "Dato base"

    status_key   = "HIGH" if score >= HIGH_STRESS_THRESHOLD else ("MODERATE" if score >= MODERATE_SCORE_THRESHOLD else "LOW")
    status_label, status_desc = STATUS_TEXT_ES[status_key]
    score_color  = "#CE1126" if status_key == "HIGH" else "#002D62" if status_key == "MODERATE" else "#1A1A1A"
    date_str     = f"{MONTHS_ES[score_date.month].capitalize()} de {score_date.year}" if score_date else ""
    run_date     = datetime.now().strftime("%d/%m/%Y a las %H:%M")
    meter_pos    = max(0.0, min(100.0, float(score)))

    briefing      = generate_briefing(results, scored)
    chart_data    = build_chart_data(scored)
    context_cards = build_context_cards(results)
    cards         = build_indicator_cards(scored, score_date)
    alert_html    = build_alert_items(alerts)

    stress_n, watch_n, normal_n = count_indicator_statuses(scored)
    total_n = stress_n + watch_n + normal_n
    n_total = len(VULNERABILITY_COMPONENTS)

    alert_count  = len(alerts) if alerts is not None and not alerts.empty else 0
    stress_count = int(alerts["is_stress"].sum()) if alert_count > 0 else 0

    alert_box_html = f'''
    <div class="alert-count {'interactive-alert' if stress_count > 0 else ''}" {f'onclick="scrollToAlerts()"' if stress_count > 0 else ''}>
        {f'&#9888; {stress_count} indicador{"es" if stress_count != 1 else ""} en zona de alerta <span class="alert-arrow">&#8595;</span>' if stress_count > 0 else '&#10003; Sin alertas activas'}
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
    <style>
        @font-face {{
            font-family: 'Haffer';
            src: url('fonts/Haffer-Regular.ttf') format('truetype');
            font-weight: 100 900;
            font-style: normal;
            font-display: swap;
        }}
        @font-face {{
            font-family: 'Reckless';
            src: url('fonts/Reckless-Regular.otf') format('opentype');
            font-weight: 100 900;
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
            --maxw: 1140px; --radius: 14px; --radius-sm: 9px;
            --border: 1px solid var(--gray-200);
            --shadow-sm: 0 1px 2px rgba(10,10,10,.04), 0 2px 6px rgba(10,10,10,.05);
            --shadow-md: 0 6px 18px rgba(10,10,10,.07), 0 2px 6px rgba(10,10,10,.05);
            --shadow-lg: 0 16px 40px rgba(10,10,10,.12);
            --ease: cubic-bezier(.4,0,.2,1);
            --header-h: 64px;
        }}
        html {{ font-size: 16px; scroll-behavior: smooth; }}
        body {{ font-family: var(--font-sans); background: var(--white); color: var(--black); line-height: 1.6; -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }}
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
        .header-inner {{ max-width: var(--maxw); margin: 0 auto; padding: 0 40px; height: var(--header-h); display: flex; align-items: center; justify-content: space-between; gap: 24px; }}
        .brand {{ display: inline-flex; align-items: center; gap: 10px; text-decoration: none; font-family: var(--font-sans); font-size: 13px; letter-spacing: .02em; color: var(--black); white-space: nowrap; }}
        .brand-mark {{ width: 16px; height: 16px; border-radius: 4px; background: linear-gradient(135deg, var(--blue) 0 50%, var(--red) 50% 100%); box-shadow: var(--shadow-sm); flex-shrink: 0; }}
        .brand-text strong {{ color: var(--blue); font-weight: 600; }}
        .header-nav {{ display: flex; gap: 6px; align-items: center; overflow-x: auto; scrollbar-width: none; }}
        .header-nav::-webkit-scrollbar {{ display: none; }}
        .nav-link {{ font-size: 14px; font-weight: 500; color: var(--gray-600); text-decoration: none; padding: 8px 14px; border-radius: 999px; white-space: nowrap; transition: color .2s var(--ease), background .2s var(--ease); }}
        .nav-link:hover {{ color: var(--blue); background: var(--blue-tint); }}
        .nav-link.active {{ color: var(--white); background: var(--blue); }}

        /* Layout */
        .container {{ max-width: var(--maxw); margin: 0 auto; padding: 0 40px; }}
        main > section {{ padding: 72px 0; border-bottom: var(--border); }}
        main > section:last-child {{ border-bottom: none; }}
        section[id] {{ scroll-margin-top: 16px; }}
        .hero {{ padding-top: 48px; }}
        .section-head {{ display: flex; align-items: center; gap: 16px; margin-bottom: 18px; }}
        .section-label {{ font-size: 20px; font-weight: 700; font-family: var(--font-display); color: var(--black); letter-spacing: -.01em; position: relative; padding-left: 14px; }}
        .section-label::before {{ content: ''; position: absolute; left: 0; top: .14em; bottom: .14em; width: 4px; border-radius: 2px; background: var(--blue); }}
        .section-rule {{ flex: 1; height: 1px; background: linear-gradient(90deg, var(--gray-200), transparent); }}
        .section-intro {{ font-size: 15px; color: var(--gray-600); max-width: 760px; margin-bottom: 30px; line-height: 1.7; }}

        /* Hero */
        .hero-logo {{ max-width: 520px; width: 100%; height: auto; margin-bottom: 44px; display: block; }}
        .score-hero {{ display: grid; grid-template-columns: 1.05fr 1fr; gap: 24px; align-items: stretch; }}
        .panel {{ background: var(--white); border: var(--border); border-radius: var(--radius); padding: 30px 32px; box-shadow: var(--shadow-sm); }}
        .score-panel {{ border-top: 3px solid {score_color}; }}
        .score-label {{ font-family: var(--font-sans); font-size: 11px; letter-spacing: .1em; color: var(--gray-600); text-transform: uppercase; margin-bottom: 12px; }}
        .score-number {{ font-family: var(--font-display); font-size: 84px; font-weight: 600; line-height: 1; color: {score_color}; letter-spacing: -3px; display: flex; align-items: baseline; flex-wrap: wrap; }}
        .score-denom {{ font-family: var(--font-display); font-size: 20px; color: var(--gray-400); margin-left: 6px; letter-spacing: 0; }}
        .score-main-arrow {{ font-size: 40px; margin-left: 14px; letter-spacing: 0; }}
        .trend-bad {{ color: var(--red); }} .trend-good {{ color: var(--green); }} .trend-neutral {{ color: var(--gray-400); }}
        .score-trend-text {{ font-size: 14px; font-weight: 600; margin-top: 14px; }}
        .score-date {{ font-size: 13px; color: var(--gray-400); margin-top: 4px; font-family: var(--font-sans); }}

        /* Score meter */
        .score-meter {{ margin-top: 26px; }}
        .meter-track {{ position: relative; height: 12px; border-radius: 999px; background: linear-gradient(90deg, var(--blue-soft) 0 50%, var(--blue) 50% 65%, var(--red) 65% 100%); box-shadow: inset 0 1px 2px rgba(10,10,10,.14); }}
        .meter-marker {{ position: absolute; top: 50%; width: 18px; height: 18px; transform: translate(-50%,-50%) rotate(45deg); background: {score_color}; border: 2px solid var(--white); box-shadow: var(--shadow-sm); }}
        .meter-scale {{ position: relative; height: 16px; margin-top: 9px; font-family: var(--font-sans); font-size: 10px; color: var(--gray-400); }}
        .meter-scale span {{ position: absolute; top: 0; transform: translateX(-50%); }}
        .meter-scale span:first-child {{ transform: none; }}
        .meter-scale span:last-child {{ transform: translateX(-100%); }}
        .meter-caption {{ margin-top: 10px; display: flex; gap: 16px; flex-wrap: wrap; font-size: 11.5px; color: var(--gray-600); }}
        .zone-key {{ display: inline-flex; align-items: center; gap: 6px; }}
        .zone-swatch {{ width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }}

        /* Status panel */
        .status-panel {{ display: flex; flex-direction: column; }}
        .status-title {{ font-family: var(--font-display); font-size: 12px; letter-spacing: .1em; color: {score_color}; text-transform: uppercase; margin-bottom: 12px; display: inline-flex; align-items: center; gap: 10px; }}
        .status-title::before {{ content: ''; width: 9px; height: 9px; border-radius: 50%; background: {score_color}; box-shadow: 0 0 0 4px {score_color}1f; }}
        .status-desc {{ font-size: 16px; color: var(--gray-600); max-width: 520px; line-height: 1.7; }}

        /* Alert button */
        .alert-count {{ display: inline-flex; align-items: center; gap: 8px; margin-top: 18px; padding: 10px 16px; border-radius: 999px; background: {'var(--red-tint)' if stress_count > 0 else 'var(--gray-100)'}; border: 1px solid {'var(--red)' if stress_count > 0 else 'var(--gray-200)'}; font-size: 13px; color: {'var(--red)' if stress_count > 0 else 'var(--gray-600)'}; font-family: var(--font-sans); align-self: flex-start; }}
        .interactive-alert {{ cursor: pointer; transition: all .2s var(--ease); }}
        @keyframes alertPulse {{ 0%, 100% {{ background-color: var(--red-tint); border-color: var(--red); box-shadow: none; }} 50% {{ background-color: #ffd6d6; border-color: #ff0000; box-shadow: 0 0 14px rgba(206,17,38,0.55); }} }}
        .interactive-alert:hover {{ animation: alertPulse .9s ease-in-out infinite; }}
        .alert-arrow {{ margin-left: 6px; font-size: 12px; }}

        /* Summary chips */
        .summary-chips {{ display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }}
        .chip {{ display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: 999px; border: var(--border); background: var(--white); font-family: var(--font-sans); font-size: 12.5px; color: var(--black); cursor: pointer; transition: box-shadow .2s var(--ease), transform .2s var(--ease), border-color .2s var(--ease); }}
        .chip:hover {{ box-shadow: var(--shadow-sm); transform: translateY(-1px); border-color: var(--gray-300); }}
        .chip b {{ font-weight: 600; }}
        .chip-dot {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }}
        .chip-stress .chip-dot {{ background: var(--red); }}
        .chip-watch .chip-dot {{ background: var(--blue); }}
        .chip-normal .chip-dot {{ background: var(--gray-400); }}

        /* Briefing */
        .briefing-text {{ font-size: 19px; line-height: 1.85; color: var(--black); max-width: 860px; }}
        .briefing-text p {{ margin-bottom: 20px; }}
        .briefing-text p:last-child {{ margin-bottom: 0; color: var(--gray-600); font-size: 15px; line-height: 1.7; padding-top: 18px; border-top: var(--border); }}
        .briefing-text strong {{ color: var(--blue); font-weight: 600; }}

        /* Cards shared */
        .card-header {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; }}
        .card-label {{ font-size: 15px; font-weight: 600; color: var(--black); line-height: 1.3; }}
        .card-desc {{ font-size: 13px; color: var(--gray-600); line-height: 1.65; }}

        /* Context cards */
        .context-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }}
        .context-card {{ padding: 24px; border: var(--border); background: var(--white); border-radius: var(--radius); display: flex; flex-direction: column; box-shadow: var(--shadow-sm); transition: box-shadow .25s var(--ease), transform .25s var(--ease), border-color .25s var(--ease); }}
        .context-card:hover {{ box-shadow: var(--shadow-md); transform: translateY(-3px); border-color: var(--gray-300); }}
        .context-item {{ display: grid; grid-template-columns: 1fr 84px; gap: 16px; align-items: center; margin-top: 16px; padding-bottom: 14px; border-bottom: var(--border); }}
        .context-item:last-of-type {{ border-bottom: none; padding-bottom: 0; }}
        .ci-info {{ display: flex; flex-direction: column; }}
        .ci-label {{ font-size: 12.5px; color: var(--gray-600); margin-bottom: 4px; }}
        .ci-value {{ font-family: var(--font-sans); font-size: 18px; font-weight: 600; color: var(--black); }}
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
        .alert-tag {{ font-family: var(--font-sans); font-size: 11px; font-weight: 600; letter-spacing: 0.1em; padding-top: 2px; }}
        .alert-stress .alert-tag {{ color: var(--red); }} .alert-watch .alert-tag {{ color: var(--blue); }}
        .alert-content {{ display: flex; flex-direction: column; gap: 6px; }}
        .alert-content strong {{ font-size: 16px; font-weight: 600; }}
        .alert-text {{ font-size: 14px; color: var(--gray-600); line-height: 1.6; }}
        .no-alerts {{ display: flex; align-items: center; gap: 16px; padding: 22px 24px; background: var(--blue-tint); border: var(--border); border-left: 4px solid var(--green); border-radius: var(--radius); font-size: 15px; color: var(--gray-600); }}
        .no-alerts-icon {{ font-size: 20px; color: var(--green); }}

        /* Panel legend + filters */
        .legend-intro {{ font-size: 13px; font-weight: 600; color: var(--gray-600); letter-spacing: .02em; margin-bottom: 14px; }}
        .legend-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 36px; }}
        .legend-item {{ padding: 18px 20px; background: var(--gray-50); border: var(--border); border-radius: var(--radius-sm); transition: background .2s var(--ease); }}
        .legend-item:hover {{ background: var(--gray-100); }}
        .legend-title {{ font-size: 13.5px; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
        .legend-dot {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }}
        .legend-desc {{ font-size: 13px; color: var(--gray-600); line-height: 1.6; margin-top: 10px; }}
        .filter-bar {{ display: flex; gap: 10px; margin-bottom: 24px; flex-wrap: wrap; }}
        .filter-chip {{ font-family: var(--font-sans); font-size: 12px; font-weight: 600; letter-spacing: .04em; padding: 8px 16px; border: var(--border); border-radius: 999px; background: var(--white); color: var(--gray-600); cursor: pointer; transition: all .2s var(--ease); }}
        .filter-chip:hover {{ border-color: var(--blue); color: var(--blue); }}
        .filter-chip.active {{ background: var(--blue); border-color: var(--blue); color: var(--white); }}

        /* Indicator cards */
        .cards-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }}
        .indicator-card {{ padding: 26px; border: var(--border); background: var(--white); border-radius: var(--radius); box-shadow: var(--shadow-sm); position: relative; overflow: hidden; transition: box-shadow .25s var(--ease), transform .25s var(--ease), border-color .25s var(--ease); }}
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
        .status-badge {{ font-family: var(--font-sans); font-size: 10px; font-weight: 600; letter-spacing: 0.08em; padding: 4px 9px; border-radius: 999px; white-space: nowrap; flex-shrink: 0; }}
        .status-stress {{ background: var(--red); color: var(--white); }}
        .status-watch  {{ background: var(--blue); color: var(--white); }}
        .status-normal {{ background: var(--gray-100); color: var(--gray-600); }}
        .card-value {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 16px; }}
        .value-number {{ font-family: var(--font-sans); font-size: 27px; font-weight: 600; color: var(--black); }}
        .value-arrow {{ font-size: 18px; }} .arrow-bad {{ color: var(--red); }} .arrow-good {{ color: var(--green); }}
        .zscore-bar-container {{ height: 5px; background: var(--gray-200); border-radius: 999px; margin-bottom: 8px; overflow: hidden; }}
        .zscore-bar {{ height: 100%; border-radius: 999px; transition: width .4s var(--ease); }}
        .zscore-label {{ font-family: var(--font-sans); font-size: 11px; color: var(--gray-400); margin-top: 14px; margin-bottom: 12px; }}

        /* Chart */
        .chart-card {{ border: var(--border); border-radius: var(--radius); padding: 24px; background: var(--white); box-shadow: var(--shadow-sm); }}
        .chart-controls {{ display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; }}
        .chart-btn {{ font-family: var(--font-sans); font-size: 11px; font-weight: 600; letter-spacing: 0.06em; padding: 7px 15px; border: var(--border); border-radius: 999px; background: var(--white); color: var(--gray-600); cursor: pointer; transition: all .15s var(--ease); }}
        .chart-btn:hover {{ border-color: var(--blue); color: var(--blue); }}
        .chart-btn.active {{ background: var(--blue); color: var(--white); border-color: var(--blue); }}
        .chart-container {{ position: relative; height: 380px; }}
        .chart-hint {{ font-size: 12px; color: var(--gray-400); font-family: var(--font-sans); margin-top: 12px; }}

        /* Footer */
        .site-footer {{ padding: 44px 0; background: var(--gray-50); border-top: var(--border); }}
        .footer-inner {{ max-width: var(--maxw); margin: 0 auto; padding: 0 40px; display: flex; justify-content: space-between; align-items: flex-end; gap: 20px; flex-wrap: wrap; }}
        .footer-sources {{ font-size: 13px; color: var(--gray-600); line-height: 1.7; max-width: 640px; }}
        .footer-sources strong {{ font-weight: 600; color: var(--black); }}
        .footer-run {{ font-family: var(--font-sans); font-size: 11px; color: var(--gray-400); white-space: nowrap; }}

        /* Back to top */
        .back-to-top {{ position: fixed; right: 24px; bottom: 24px; width: 46px; height: 46px; border-radius: 50%; border: none; background: var(--blue); color: var(--white); font-size: 20px; line-height: 1; cursor: pointer; box-shadow: var(--shadow-md); opacity: 0; visibility: hidden; transform: translateY(10px); transition: all .3s var(--ease); z-index: 40; }}
        .back-to-top.show {{ opacity: 1; visibility: visible; transform: none; }}
        .back-to-top:hover {{ background: var(--blue-deep); transform: translateY(-2px); box-shadow: var(--shadow-lg); }}

        /* Responsive */
        @media (max-width: 980px) {{
            .score-hero {{ grid-template-columns: 1fr; gap: 20px; }}
            .cards-grid, .context-grid, .legend-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .score-number {{ font-size: 68px; }}
            .hero-logo {{ max-width: 400px; }}
        }}
        @media (max-width: 640px) {{
            .container, .header-inner, .footer-inner {{ padding-left: 20px; padding-right: 20px; }}
            main > section {{ padding: 48px 0; }}
            .cards-grid, .context-grid, .legend-grid {{ grid-template-columns: 1fr; }}
            .alert-item {{ grid-template-columns: 1fr; gap: 10px; }}
            .score-number {{ font-size: 56px; }}
            .brand-text {{ display: none; }}
            .hero-logo {{ max-width: 240px; }}
            .panel {{ padding: 24px; }}
            .briefing-text {{ font-size: 16px; }}
            .footer-inner {{ flex-direction: column; align-items: flex-start; }}
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
    <div class="header-inner">
        <a href="#top" class="brand" aria-label="Inicio">
            <span class="brand-mark" aria-hidden="true"></span>
            <span class="brand-text">Inteligencia Económica<strong> RD</strong></span>
        </a>
        <nav class="header-nav" aria-label="Secciones del informe">
            {context_nav}
            <a href="#indicadores-seguimiento" class="nav-link">Indicadores</a>
            <a href="#panel-indicadores" class="nav-link">Panel</a>
            <a href="#historial-indice" class="nav-link">Historial</a>
        </nav>
    </div>
</header>

<main>

    <section class="hero">
        <div class="container">
            <img src="{HERO_LOGO_SRC}" alt="La Sociedad — DR Economic Intelligence" class="hero-logo">
            <div class="score-hero">
                <div class="panel score-panel">
                    <div class="score-label">Índice de Vulnerabilidad Económica ({n_total}/{n_total} indicadores)</div>
                    <div class="score-number">
                        {score:.1f}<span class="score-denom">/100</span>
                        <span class="score-main-arrow {trend_class}">{trend_arrow}</span>
                    </div>
                    <div class="score-trend-text {trend_class}">{trend_text}</div>
                    <div class="score-date">{date_str}</div>
                    <div class="score-meter" role="img" aria-label="Puntuación {score:.1f} de 100">
                        <div class="meter-track"><div class="meter-marker" style="left:{meter_pos:.1f}%"></div></div>
                        <div class="meter-scale"><span style="left:0">0</span><span style="left:50%">50</span><span style="left:65%">65</span><span style="left:100%">100</span></div>
                        <div class="meter-caption">
                            <span class="zone-key"><span class="zone-swatch" style="background:var(--blue-soft)"></span>Normal</span>
                            <span class="zone-key"><span class="zone-swatch" style="background:var(--blue)"></span>Moderado (50+)</span>
                            <span class="zone-key"><span class="zone-swatch" style="background:var(--red)"></span>Alerta (65+)</span>
                        </div>
                    </div>
                </div>
                <div class="panel status-panel">
                    <div class="status-title">{status_label}</div>
                    <div class="status-desc">{status_desc}</div>
                    {alert_box_html}
                    <div class="summary-chips" role="group" aria-label="Resumen de indicadores">
                        <button type="button" class="chip chip-stress" onclick="jumpFilter('stress')" aria-label="{stress_n} indicadores en alerta"><span class="chip-dot" aria-hidden="true"></span><b>{stress_n}</b>&nbsp;en alerta</button>
                        <button type="button" class="chip chip-watch" onclick="jumpFilter('watch')" aria-label="{watch_n} indicadores en vigilancia"><span class="chip-dot" aria-hidden="true"></span><b>{watch_n}</b>&nbsp;en vigilancia</button>
                        <button type="button" class="chip chip-normal" onclick="jumpFilter('normal')" aria-label="{normal_n} indicadores normales"><span class="chip-dot" aria-hidden="true"></span><b>{normal_n}</b>&nbsp;normales</button>
                    </div>
                </div>
            </div>
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
                    <button class="chart-btn" data-range="36">36 meses</button>
                    <button class="chart-btn active" data-range="0">Todo</button>
                </div>
                <div class="chart-container"><canvas id="scoreChart"></canvas></div>
                <div class="chart-hint">Desplácese para hacer zoom · Arrastre para navegar · La línea roja marca el umbral de alerta ({HIGH_STRESS_THRESHOLD})</div>
            </div>
        </div>
    </section>

</main>

<footer class="site-footer">
    <div class="footer-inner">
        <div class="footer-sources">
            <strong>Fuentes:</strong> Banco Central de la República Dominicana (BCRD) · Superintendencia de Bancos (SB) · Reserva Federal de EE.UU. (FRED)<br>
            El índice combina 9 indicadores macroeconómicos y financieros ponderados por su relevancia para la economía dominicana.
        </div>
        <div class="footer-run">Actualizado: {run_date}</div>
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

    // Reveal sections on scroll
    const fadeObserver = new IntersectionObserver(entries => {{
        entries.forEach(e => {{ if (e.isIntersecting) e.target.classList.add('is-visible'); }});
    }}, {{ threshold: 0.12 }});
    document.querySelectorAll('main > section').forEach(sec => {{ sec.classList.add('fade-in-section'); fadeObserver.observe(sec); }});

    // Scroll-spy: highlight the nav link of the section in view
    const navLinks = document.querySelectorAll('.header-nav .nav-link');
    const spyMap = {{}};
    navLinks.forEach(l => {{ const id = (l.getAttribute('href') || '').slice(1); if (id) spyMap[id] = l; }});
    const spyObserver = new IntersectionObserver(entries => {{
        entries.forEach(e => {{
            if (e.isIntersecting && spyMap[e.target.id]) {{
                navLinks.forEach(l => l.classList.remove('active'));
                spyMap[e.target.id].classList.add('active');
            }}
        }});
    }}, {{ rootMargin: '-45% 0px -50% 0px', threshold: 0 }});
    Object.keys(spyMap).forEach(id => {{ const s = document.getElementById(id); if (s) spyObserver.observe(s); }});

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

function scrollToAlerts() {{
    const target = document.getElementById('panel-indicadores');
    if (target) {{
        window.scrollTo({{ top: target.getBoundingClientRect().top + window.scrollY - 80, behavior: 'smooth' }});
        setTimeout(() => {{
            document.querySelectorAll('.card-stress').forEach(card => {{
                card.classList.remove('blink-alert'); void card.offsetWidth; card.classList.add('blink-alert');
            }});
        }}, 500);
    }}
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
const ctx = document.getElementById('scoreChart').getContext('2d');
const scoreChart = new Chart(ctx, {{
    type: 'line',
    data: {{ labels: chartData.labels, datasets: [{{ label: 'Índice de Vulnerabilidad', data: chartData.values, borderColor: '#002D62', backgroundColor: 'rgba(0,45,98,0.06)', borderWidth: 2, pointBackgroundColor: chartData.colors, pointBorderColor: chartData.colors, pointRadius: 3, pointHoverRadius: 6, fill: true, tension: 0.3 }}] }},
    options: {{
        responsive: true, maintainAspectRatio: false,
        interaction: {{ intersect: false, mode: 'index' }},
        plugins: {{
            legend: {{ display: false }},
            tooltip: {{ backgroundColor: '#0A0A0A', titleColor: '#fff', bodyColor: '#ccc', padding: 12, displayColors: false, callbacks: {{ label: c => `Índice: ${{c.parsed.y}} / 100` }} }},
            zoom: {{ zoom: {{ wheel: {{ enabled: true }}, pinch: {{ enabled: true }}, mode: 'x' }}, pan: {{ enabled: true, mode: 'x' }} }}
        }},
        scales: {{
            x: {{ grid: {{ color: 'rgba(0,0,0,0.05)' }}, ticks: {{ font: {{ family: 'Haffer', size: 11 }}, color: '#555555', maxTicksLimit: 14, maxRotation: 45 }} }},
            y: {{ min: 0, max: 100, grid: {{ color: 'rgba(0,0,0,0.05)' }}, ticks: {{ font: {{ family: 'Haffer', size: 11 }}, color: '#555555', stepSize: 25, callback: v => v + '/100' }} }}
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
    c2.setLineDash([]); c2.fillStyle = 'rgba(206,17,38,0.85)'; c2.font = '600 10px "Haffer", sans-serif';
    c2.textAlign = 'right'; c2.fillText('Umbral de alerta ({HIGH_STRESS_THRESHOLD})', scoreChart.scales.x.right - 6, y - 6);
    c2.restore();
}};

function applyRange(months, btn) {{
    document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    if (scoreChart.resetZoom) scoreChart.resetZoom();
    const n = months || chartData.labels.length;
    scoreChart.data.labels = chartData.labels.slice(-n);
    scoreChart.data.datasets[0].data = chartData.values.slice(-n);
    scoreChart.data.datasets[0].pointBackgroundColor = chartData.colors.slice(-n);
    scoreChart.data.datasets[0].pointBorderColor = chartData.colors.slice(-n);
    scoreChart.update();
}}
document.querySelectorAll('.chart-btn').forEach(b => b.addEventListener('click', () => applyRange(parseInt(b.dataset.range, 10), b)));
(function() {{ const def = document.querySelector('.chart-btn[data-range="0"]'); applyRange(0, def); }})();
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