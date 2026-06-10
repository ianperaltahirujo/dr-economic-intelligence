"""
DR Economic Vulnerability Pipeline - Excel Output Writer
Produces a professionally formatted Excel workbook from pipeline results.

Sheets:
    Dashboard   - Single-page summary: score, status, top indicators
    Indicators  - All 9 vulnerability components with z-scores and weights
    Alerts      - Plain-language flagged indicators for Claude briefings
    History     - Last 24 months of scores and raw indicator values
    Metadata    - Pipeline run info, data source freshness, missing indicators

Primary reader: Claude via Microsoft 365 MCP integration
Secondary reader: Human stakeholders at La Sociedad

Usage:
    from pipeline.write_excel import write_workbook
    write_workbook(results, path="data/output/vulnerability_report.xlsx")
"""

import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import (
    Alignment, Border, Font, GradientFill, PatternFill, Side
)
from openpyxl.utils import get_column_letter

# ── Color palette ─────────────────────────────────────────────────────────────
# Deep navy + white + accent colors. Professional, readable, not garish.

NAVY       = "0D1B2A"
WHITE      = "FFFFFF"
LIGHT_GRAY = "F5F6FA"
MID_GRAY   = "D1D5DB"
DARK_GRAY  = "6B7280"
ACCENT     = "2563EB"   # Blue
GREEN      = "16A34A"
AMBER      = "D97706"
RED        = "DC2626"
LIGHT_BLUE = "DBEAFE"

# ── Style helpers ──────────────────────────────────────────────────────────────

def _font(bold=False, size=11, color=NAVY, italic=False):
    return Font(name="Arial", bold=bold, size=size, color=color, italic=italic)

def _fill(color):
    return PatternFill("solid", fgColor=color)

def _border(style="thin"):
    s = Side(style=style, color=MID_GRAY)
    return Border(left=s, right=s, top=s, bottom=s)

def _bottom_border():
    s = Side(style="thin", color=MID_GRAY)
    return Border(bottom=s)

def _align(h="left", v="center", wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

def _set_col_width(ws, col_letter, width):
    ws.column_dimensions[col_letter].width = width

def _header_row(ws, row, values, bg=NAVY, fg=WHITE, bold=True, size=11):
    for col, val in enumerate(values, 1):
        cell = ws.cell(row=row, column=col, value=val)
        cell.font = _font(bold=bold, size=size, color=fg)
        cell.fill = _fill(bg)
        cell.alignment = _align("center")
        cell.border = _border()

def _score_color(score):
    """Return hex fill color based on vulnerability score."""
    if score is None or np.isnan(score):
        return MID_GRAY
    if score >= 65:
        return RED
    if score >= 50:
        return AMBER
    return GREEN

def _zscore_color(zscore, direction):
    """Return hex color based on z-score stress direction."""
    if zscore is None or np.isnan(zscore):
        return MID_GRAY
    is_stress = (
        (direction == "positive" and zscore > 1.5) or
        (direction == "negative" and zscore < -1.5)
    )
    if is_stress:
        return RED
    if abs(zscore) > 0.75:
        return AMBER
    return GREEN


# ── Sheet builders ─────────────────────────────────────────────────────────────

def _build_dashboard(wb: Workbook, results: dict) -> None:
    ws = wb.create_sheet("Dashboard")
    ws.sheet_view.showGridLines = False

    score      = results.get("current_score")
    score_date = results.get("score_date")
    alerts     = results.get("alerts", pd.DataFrame())
    scored     = results.get("scored", pd.DataFrame())

    # ── Title block ──
    ws.merge_cells("A1:H1")
    ws["A1"] = "DR Economic Vulnerability Report"
    ws["A1"].font = _font(bold=True, size=16, color=WHITE)
    ws["A1"].fill = _fill(NAVY)
    ws["A1"].alignment = _align("center")

    ws.merge_cells("A2:H2")
    run_ts = datetime.now().strftime("%B %d, %Y at %H:%M")
    ws["A2"] = f"Generated: {run_ts}"
    ws["A2"].font = _font(size=10, color=WHITE, italic=True)
    ws["A2"].fill = _fill(NAVY)
    ws["A2"].alignment = _align("center")

    ws.row_dimensions[1].height = 36
    ws.row_dimensions[2].height = 20

    # ── Score card ──
    ws.merge_cells("A4:D6")
    score_val = f"{score:.1f}" if score and not np.isnan(score) else "N/A"
    ws["A4"] = f"Vulnerability Score: {score_val} / 100"
    ws["A4"].font = _font(bold=True, size=20, color=WHITE)
    ws["A4"].fill = _fill(_score_color(score))
    ws["A4"].alignment = _align("center", "center")

    ws.merge_cells("E4:H6")
    if score is not None and not np.isnan(score):
        if score >= 65:
            status_text = "HIGH STRESS"
        elif score >= 50:
            status_text = "MODERATE STRESS"
        else:
            status_text = "LOW STRESS"
    else:
        status_text = "INSUFFICIENT DATA"

    date_str = score_date.strftime("%B %Y") if score_date else "Unknown"
    ws["E4"] = f"{status_text}\n{date_str}"
    ws["E4"].font = _font(bold=True, size=14, color=WHITE)
    ws["E4"].fill = _fill(_score_color(score))
    ws["E4"].alignment = _align("center", "center", wrap=True)

    for row in range(4, 7):
        ws.row_dimensions[row].height = 28

    # ── Indicators summary table ──
    ws["A8"] = "Key Indicators"
    ws["A8"].font = _font(bold=True, size=12, color=NAVY)

    headers = ["Indicator", "Current Value", "Z-Score", "Status", "Weight"]
    _header_row(ws, 9, headers)

    from pipeline.build_vulnerability import VULNERABILITY_COMPONENTS, INDICATOR_LABELS

    data_row = 10
    for col_name, (weight, direction) in VULNERABILITY_COMPONENTS.items():
        zscore_col = f"{col_name}_zscore"
        if scored.empty or col_name not in scored.columns:
            continue

        recent = scored[[col_name, zscore_col]].dropna().tail(1)
        if recent.empty:
            continue

        value  = recent[col_name].iloc[0]
        zscore = recent[zscore_col].iloc[0]
        label  = INDICATOR_LABELS.get(col_name, col_name)

        is_stress = (
            (direction == "positive" and zscore > 1.5) or
            (direction == "negative" and zscore < -1.5)
        )
        status = "STRESS" if is_stress else ("Watch" if abs(zscore) > 0.75 else "Normal")

        row_data = [
            label,
            round(value, 3),
            round(zscore, 2),
            status,
            f"{weight*100:.0f}%"
        ]

        fill_color = LIGHT_GRAY if data_row % 2 == 0 else WHITE
        for c, val in enumerate(row_data, 1):
            cell = ws.cell(row=data_row, column=c, value=val)
            cell.font = _font(size=10)
            cell.fill = _fill(fill_color)
            cell.alignment = _align("center" if c > 1 else "left")
            cell.border = _bottom_border()

        # Color-code the Status cell
        status_cell = ws.cell(row=data_row, column=4)
        color = _zscore_color(zscore, direction)
        status_cell.font = _font(bold=True, size=10, color=WHITE)
        status_cell.fill = _fill(color)

        data_row += 1

    # Column widths
    for col, width in zip("ABCDE", [38, 16, 12, 14, 10]):
        _set_col_width(ws, col, width)
    for col in "FGH":
        _set_col_width(ws, col, 12)


def _build_indicators(wb: Workbook, results: dict) -> None:
    ws = wb.create_sheet("Indicators")
    ws.sheet_view.showGridLines = False

    scored = results.get("scored", pd.DataFrame())
    if scored.empty:
        ws["A1"] = "No indicator data available."
        return

    from pipeline.build_vulnerability import VULNERABILITY_COMPONENTS, INDICATOR_LABELS

    ws.merge_cells("A1:I1")
    ws["A1"] = "Vulnerability Component Detail"
    ws["A1"].font = _font(bold=True, size=14, color=WHITE)
    ws["A1"].fill = _fill(NAVY)
    ws["A1"].alignment = _align("center")
    ws.row_dimensions[1].height = 30

    headers = [
        "Indicator", "Column Name", "Current Value", "Unit",
        "Z-Score", "Stress Direction", "Weight", "Contribution", "Status"
    ]
    _header_row(ws, 2, headers)

    # Units lookup
    units = {
        "remesas_usd_mm":   "USD mm",
        "ipc_yoy_pct":      "%",
        "dop_usd":          "DOP/USD",
        "reserves_usd_mm":  "USD mm",
        "imae_index":       "Index",
        "sb_morosidad_pct": "%",
        "sb_solvencia_pct": "%",
        "UNRATE":           "%",
        "UMCSENT":          "Index",
    }

    data_row = 3
    for col_name, (weight, direction) in VULNERABILITY_COMPONENTS.items():
        zscore_col = f"{col_name}_zscore"
        if col_name not in scored.columns:
            continue

        recent = scored[[col_name, zscore_col]].dropna().tail(1)
        if recent.empty:
            continue

        value  = recent[col_name].iloc[0]
        zscore = recent[zscore_col].iloc[0]
        label  = INDICATOR_LABELS.get(col_name, col_name)

        # Stress contribution (same logic as build_vulnerability.py)
        z_clipped = max(-3, min(3, zscore))
        raw_stress = (z_clipped + 3) / 6 * 100
        stress = (100 - raw_stress) if direction == "negative" else raw_stress
        contribution = round(stress * weight, 2)

        is_stress = (
            (direction == "positive" and zscore > 1.5) or
            (direction == "negative" and zscore < -1.5)
        )
        status = "STRESS" if is_stress else ("Watch" if abs(zscore) > 0.75 else "Normal")

        row_vals = [
            label, col_name, round(value, 4),
            units.get(col_name, ""),
            round(zscore, 3), direction,
            f"{weight*100:.0f}%", round(contribution, 2), status
        ]

        fill_color = LIGHT_GRAY if data_row % 2 == 0 else WHITE
        for c, val in enumerate(row_vals, 1):
            cell = ws.cell(row=data_row, column=c, value=val)
            cell.font = _font(size=10)
            cell.fill = _fill(fill_color)
            cell.alignment = _align("center" if c > 2 else "left")
            cell.border = _bottom_border()

        status_cell = ws.cell(row=data_row, column=9)
        color = _zscore_color(zscore, direction)
        status_cell.font = _font(bold=True, size=10, color=WHITE)
        status_cell.fill = _fill(color)

        data_row += 1

    for col, width in zip("ABCDEFGHI", [36, 22, 14, 10, 10, 18, 8, 14, 10]):
        _set_col_width(ws, col, width)


def _build_alerts(wb: Workbook, results: dict) -> None:
    ws = wb.create_sheet("Alerts")
    ws.sheet_view.showGridLines = False

    alerts = results.get("alerts", pd.DataFrame())

    ws.merge_cells("A1:F1")
    ws["A1"] = "Flagged Indicators — Plain Language Alerts"
    ws["A1"].font = _font(bold=True, size=14, color=WHITE)
    ws["A1"].fill = _fill(NAVY)
    ws["A1"].alignment = _align("center")
    ws.row_dimensions[1].height = 30

    if alerts.empty:
        ws["A3"] = "No indicators flagged above the alert threshold (|z| > 1.5)."
        ws["A3"].font = _font(size=11, color=DARK_GRAY, italic=True)
        ws["A3"].alignment = _align("left")
        return

    headers = ["Indicator", "Current Value", "Z-Score", "Stress?", "Alert Text"]
    _header_row(ws, 2, headers)

    for i, (_, row) in enumerate(alerts.iterrows(), 3):
        fill_color = LIGHT_GRAY if i % 2 == 0 else WHITE
        row_vals = [
            row.get("label", row.get("indicator", "")),
            round(row.get("value", 0), 4),
            round(row.get("zscore", 0), 3),
            "YES" if row.get("is_stress") else "NO",
            row.get("alert_text", ""),
        ]
        for c, val in enumerate(row_vals, 1):
            cell = ws.cell(row=i, column=c, value=val)
            cell.font = _font(size=10)
            cell.fill = _fill(fill_color)
            cell.alignment = _align("left", wrap=True)
            cell.border = _bottom_border()
            if c == 4:
                cell.font = _font(
                    bold=True, size=10,
                    color=RED if row.get("is_stress") else DARK_GRAY
                )
        ws.row_dimensions[i].height = 40

    for col, width in zip("ABCDE", [36, 14, 10, 10, 80]):
        _set_col_width(ws, col, width)


def _build_history(wb: Workbook, results: dict) -> None:
    ws = wb.create_sheet("History")
    ws.sheet_view.showGridLines = False

    scored = results.get("scored", pd.DataFrame())
    if scored.empty:
        ws["A1"] = "No history data available."
        return

    from pipeline.build_vulnerability import VULNERABILITY_COMPONENTS

    # Last 24 months with valid scores
    history_cols = (
        ["vulnerability_score"] +
        [c for c in VULNERABILITY_COMPONENTS if c in scored.columns]
    )
    history = scored[history_cols].dropna(subset=["vulnerability_score"]).tail(24)

    ws.merge_cells(f"A1:{get_column_letter(len(history_cols))}1")
    ws["A1"] = "24-Month History"
    ws["A1"].font = _font(bold=True, size=14, color=WHITE)
    ws["A1"].fill = _fill(NAVY)
    ws["A1"].alignment = _align("center")
    ws.row_dimensions[1].height = 30

    header_vals = ["Date", "Vulnerability Score"] + list(VULNERABILITY_COMPONENTS.keys())
    _header_row(ws, 2, header_vals)

    for i, (date, row) in enumerate(history.iterrows(), 3):
        fill_color = LIGHT_GRAY if i % 2 == 0 else WHITE
        row_vals = [date.strftime("%Y-%m")] + [
            round(row.get(c, np.nan), 3) if pd.notna(row.get(c)) else ""
            for c in history_cols
        ]
        for c, val in enumerate(row_vals, 1):
            cell = ws.cell(row=i, column=c, value=val)
            cell.font = _font(size=10)
            cell.fill = _fill(fill_color)
            cell.alignment = _align("center")
            cell.border = _bottom_border()

        # Color-code the score cell
        score_cell = ws.cell(row=i, column=2)
        score_val = row.get("vulnerability_score")
        if pd.notna(score_val):
            score_cell.font = _font(bold=True, size=10, color=WHITE)
            score_cell.fill = _fill(_score_color(score_val))

    _set_col_width(ws, "A", 12)
    _set_col_width(ws, "B", 20)
    for col_idx in range(3, len(history_cols) + 2):
        _set_col_width(ws, get_column_letter(col_idx), 16)


def _build_metadata(wb: Workbook, results: dict) -> None:
    ws = wb.create_sheet("Metadata")
    ws.sheet_view.showGridLines = False

    scored  = results.get("scored", pd.DataFrame())
    merged  = results.get("merged", pd.DataFrame())

    ws.merge_cells("A1:C1")
    ws["A1"] = "Pipeline Metadata"
    ws["A1"].font = _font(bold=True, size=14, color=WHITE)
    ws["A1"].fill = _fill(NAVY)
    ws["A1"].alignment = _align("center")
    ws.row_dimensions[1].height = 30

    _header_row(ws, 2, ["Field", "Value", "Notes"], bg=ACCENT)

    meta_rows = [
        ("Report Generated",    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Pipeline run timestamp"),
        ("Score Date",          results.get("score_date", pd.NaT),            "Most recent scored month"),
        ("Vulnerability Score", results.get("current_score", "N/A"),          "0=no stress, 100=max stress"),
        ("Z-Score Window",      "36 months",                                   "Rolling baseline for z-scores"),
        ("Alert Threshold",     "|z| > 1.5",                                   "Standard deviations from mean"),
        ("High Stress Threshold","65 / 100",                                   "Score above this = HIGH STRESS"),
        ("", "", ""),
        ("DATA SOURCES", "", ""),
    ]

    # Data freshness per source
    from pipeline.build_vulnerability import VULNERABILITY_COMPONENTS
    source_map = {
        "BCRD (Excel files)": [c for c in ["remesas_usd_mm", "ipc_yoy_pct", "dop_usd",
                                            "reserves_usd_mm", "imae_index"] if c in scored.columns],
        "SB API":             [c for c in ["sb_morosidad_pct", "sb_solvencia_pct"] if c in scored.columns],
        "FRED API":           [c for c in ["UNRATE", "UMCSENT"] if c in scored.columns],
    }

    for source, cols in source_map.items():
        if cols:
            latest = scored[cols].dropna(how="all").index.max()
            latest_str = latest.strftime("%Y-%m") if pd.notna(latest) else "Unknown"
            meta_rows.append((source, f"Latest data: {latest_str}", f"Indicators: {', '.join(cols)}"))
        else:
            meta_rows.append((source, "NOT LOADED", "No indicators available from this source"))

    meta_rows += [
        ("", "", ""),
        ("MISSING INDICATORS", "", ""),
    ]

    missing = [c for c in VULNERABILITY_COMPONENTS if c not in scored.columns]
    if missing:
        for col in missing:
            meta_rows.append((col, "MISSING", "Not loaded — check data source"))
    else:
        meta_rows.append(("None", "All 9 components loaded", ""))

    for i, (field, value, notes) in enumerate(meta_rows, 3):
        fill = LIGHT_GRAY if i % 2 == 0 else WHITE
        if str(field).isupper() and field:
            fill = LIGHT_BLUE

        for c, val in enumerate([field, str(value) if value != "" else "", notes], 1):
            cell = ws.cell(row=i, column=c, value=val)
            cell.font = _font(bold=(str(field).isupper() and bool(field)), size=10)
            cell.fill = _fill(fill)
            cell.alignment = _align("left", wrap=True)
            cell.border = _bottom_border()

        ws.row_dimensions[i].height = 18

    for col, width in zip("ABC", [28, 28, 55]):
        _set_col_width(ws, col, width)


# ── Main writer ────────────────────────────────────────────────────────────────

def write_workbook(
    results: dict,
    path: str = "data/output/vulnerability_report.xlsx",
) -> Path:
    """
    Write the full vulnerability workbook from pipeline results.

    Args:
        results: Dict returned by build_vulnerability.run_vulnerability_pipeline()
        path:    Output file path. Parent directories are created if missing.

    Returns:
        Path object of the written file.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    print("Writing Excel workbook...")
    _build_dashboard(wb, results)
    print("  [OK] Dashboard")
    _build_indicators(wb, results)
    print("  [OK] Indicators")
    _build_alerts(wb, results)
    print("  [OK] Alerts")
    _build_history(wb, results)
    print("  [OK] History")
    _build_metadata(wb, results)
    print("  [OK] Metadata")

    wb.save(output_path)
    print(f"\nWorkbook saved: {output_path}")
    return output_path


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from .build_vulnerability import run_vulnerability_pipeline

    print("Running vulnerability pipeline...\n")
    results = run_vulnerability_pipeline()

    output = write_workbook(results)
    print(f"\nDone. Open: {output.resolve()}")