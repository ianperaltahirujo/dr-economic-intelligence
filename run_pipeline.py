"""
DR Economic Intelligence Pipeline - Main Entry Point
Runs the full weekly pipeline in order:

    1. Download fresh BCRD Excel files from CDN
    2. Run vulnerability scoring (BCRD + SB API + FRED)
    3. Load context indicators (gas, tourism, debt)
    4. Write Excel workbook to data/output/
    5. Write HTML site to docs/index.html
    6. Write & upload the current month's projected-score Excel snapshot
       to OneDrive's "Weekly Reports" folder (new file every run), and the
       finalized Excel for the most recently confirmed month to "Monthly
       Reports" (only when new or changed since the last upload)
    7. Send weekly summary email via Outlook/Graph API, with the weekly
       snapshot attached

Usage:
    python run_pipeline.py                  # full run
    python run_pipeline.py --skip-download  # skip BCRD download (use cached files)
    python run_pipeline.py --local          # skip OneDrive upload + email (local outputs only)
    python run_pipeline.py --skip-download --local  # fast local run, no side effects
    python run_pipeline.py --dry-run        # score only, no Excel output
"""

import os
import sys
import argparse
import traceback
from datetime import datetime
from pathlib import Path

# -- Config ------------------------------------------------------------------

BCRD_DATA_DIR   = "data/raw"
OUTPUT_PATH     = "data/output/vulnerability_report.xlsx"
DASHBOARD_URL   = "https://ianperaltahirujo.github.io/dr-economic-intelligence"
EMAIL_SENDER_NAME = "Economic Intelligence · La Sociedad"

# Brand palette (mirrors docs/index.html :root) for the weekly summary email.
_EMAIL_NAVY      = "#002D62"
_EMAIL_RED       = "#CE1126"
_EMAIL_INK       = "#1A1A1A"
_EMAIL_MUTED     = "#555555"
_EMAIL_HAIRLINE  = "#E0E0E0"
_EMAIL_BLUE_TINT = "#EEF2F8"
_EMAIL_PAGE_BG   = "#F4F5F7"
_EMAIL_FONT_BODY = "Arial, 'Helvetica Neue', Helvetica, sans-serif"
_EMAIL_FONT_HEAD = "Georgia, 'Times New Roman', serif"
_EMAIL_FONT_MONO = "Consolas, 'Courier New', monospace"

# -- Helpers -----------------------------------------------------------------


def build_email_html(date_str: str, dashboard_url: str) -> str:
    """
    Branded, Outlook-safe HTML body for the weekly summary email.

    Table-based layout with inline styles only -- no flexbox/grid, web fonts,
    or background-image dependence -- so it survives Outlook's Word rendering
    engine. Mirrors the dashboard's navy/red brand palette.
    """
    intro = "Este es el reporte semanal de Inteligencia Económica de la República Dominicana"
    intro += f", correspondiente a {date_str}." if date_str else "."
    meta_line = date_str if date_str else "Reporte semanal"

    return f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background:{_EMAIL_PAGE_BG}; -webkit-text-size-adjust:100%;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{_EMAIL_PAGE_BG};">
    <tr>
      <td align="center" style="padding:24px 12px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
               style="width:600px; max-width:600px; background:#FFFFFF; border:1px solid {_EMAIL_HAIRLINE}; border-radius:8px; overflow:hidden;">

          <tr>
            <td style="padding:0; font-size:0; line-height:0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="50%" height="4" style="background:{_EMAIL_NAVY}; font-size:0; line-height:0;">&nbsp;</td>
                  <td width="50%" height="4" style="background:{_EMAIL_RED}; font-size:0; line-height:0;">&nbsp;</td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td style="padding:28px 36px 22px 36px;">
              <div style="font-family:{_EMAIL_FONT_HEAD}; font-size:26px; font-weight:bold; color:{_EMAIL_NAVY}; letter-spacing:-0.01em;">La Sociedad</div>
              <div style="font-family:{_EMAIL_FONT_MONO}; font-size:11px; letter-spacing:0.12em; color:{_EMAIL_MUTED}; text-transform:uppercase; margin-top:4px;">DR Economic Intelligence</div>
            </td>
          </tr>

          <tr>
            <td style="padding:0 36px 8px 36px;">
              <div style="font-family:{_EMAIL_FONT_MONO}; font-size:11px; letter-spacing:0.14em; color:{_EMAIL_RED}; text-transform:uppercase;">Reporte Semanal</div>
              <div style="font-family:{_EMAIL_FONT_HEAD}; font-size:21px; color:{_EMAIL_INK}; margin-top:6px;">Índice de Vulnerabilidad Económica</div>
              <div style="font-family:{_EMAIL_FONT_MONO}; font-size:12px; color:{_EMAIL_MUTED}; margin-top:6px;">{meta_line}</div>
            </td>
          </tr>

          <tr><td style="padding:18px 36px 0 36px;"><div style="border-top:1px solid {_EMAIL_HAIRLINE}; font-size:0; line-height:0;">&nbsp;</div></td></tr>

          <tr>
            <td style="padding:18px 36px 4px 36px; font-family:{_EMAIL_FONT_BODY}; font-size:15px; line-height:1.6; color:{_EMAIL_INK};">
              <p style="margin:0 0 16px 0;">{intro}</p>
              <p style="margin:0 0 24px 0; color:{_EMAIL_MUTED};">Consulte el tablero interactivo para ver el puntaje del índice, el estado de cada indicador y las alertas activas de esta semana.</p>
            </td>
          </tr>

          <tr>
            <td style="padding:0 36px 28px 36px;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="center" bgcolor="{_EMAIL_NAVY}" style="background:{_EMAIL_NAVY}; border-radius:6px;">
                    <a href="{dashboard_url}" target="_blank"
                       style="display:inline-block; padding:13px 28px; font-family:{_EMAIL_FONT_BODY}; font-size:14px; font-weight:bold; color:#FFFFFF; text-decoration:none; border-radius:6px;">
                      Ver el tablero completo &rarr;
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td style="padding:0 36px 30px 36px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="background:{_EMAIL_BLUE_TINT}; border:1px solid {_EMAIL_HAIRLINE}; border-radius:6px;">
                <tr>
                  <td style="padding:14px 18px; font-family:{_EMAIL_FONT_BODY}; font-size:13px; color:{_EMAIL_INK};">
                    <span style="font-family:{_EMAIL_FONT_MONO}; font-size:11px; font-weight:bold; color:{_EMAIL_NAVY}; letter-spacing:0.04em;">ONEDRIVE &nbsp;·&nbsp;</span>
                    Economic Intelligence / Output
                    <div style="font-family:{_EMAIL_FONT_BODY}; font-size:12px; color:{_EMAIL_MUTED}; margin-top:4px;">El reporte en Excel está disponible en la carpeta compartida de OneDrive.</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td style="padding:0; font-size:0; line-height:0;"><div style="border-top:1px solid {_EMAIL_HAIRLINE};">&nbsp;</div></td>
          </tr>
          <tr>
            <td style="padding:20px 36px 26px 36px; font-family:{_EMAIL_FONT_BODY}; font-size:11px; line-height:1.6; color:{_EMAIL_MUTED};">
              Informe generado automáticamente cada semana por el sistema de Inteligencia Económica de La Sociedad,
              a partir de fuentes oficiales: Banco Central de la República Dominicana (BCRD), Superintendencia de Bancos (SB)
              y la Reserva Federal de EE.UU. (FRED).
              <div style="margin-top:10px; color:#8A8A8A;">La Sociedad · Economic Intelligence</div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

def _section(title: str) -> None:
    width = 54
    print(f"\n{'='*width}")
    print(f"  {title}")
    print(f"{'='*width}")


def _step(n: int, total: int, label: str) -> None:
    print(f"\n[{n}/{total}] {label}")
    print(f"{'-'*40}")


# -- Pipeline steps ----------------------------------------------------------

def step_download_bcrd() -> bool:
    """Download fresh BCRD Excel files. Returns True on success."""
    from pipeline.download_bcrd_files import download_all
    results = download_all(Path(BCRD_DATA_DIR))
    if results["failed"]:
        print(f"\n  WARNING: {len(results['failed'])} file(s) failed to download.")
    """Download fresh BCRD Excel files and context files. Returns True on success."""
    from pipeline.download_bcrd_files import download_all as download_bcrd
    from pipeline.download_context_files import download_all as download_context

    results_bcrd = download_bcrd(Path(BCRD_DATA_DIR))
    if results_bcrd["failed"]:
        print(f"\n  WARNING: {len(results_bcrd['failed'])} BCRD file(s) failed to download.")
        print("  Pipeline will use cached versions for failed files.")

    print("\nDownloading context files...")
    results_ctx = download_context(Path(BCRD_DATA_DIR))
    if results_ctx["failed"]:
        print(f"\n  WARNING: {len(results_ctx['failed'])} context file(s) failed to download.")

    return True


def step_score(skip_download: bool = False) -> dict:
    """Run vulnerability scoring pipeline. Returns results dict."""
    from pipeline.build_vulnerability import run_vulnerability_pipeline
    return run_vulnerability_pipeline()


def step_load_context() -> dict:
    """Load context indicators (gas, tourism, debt). Returns context dict."""
    from pipeline.ingest_context import load_context_all
    return load_context_all()


def step_estimate_current_month(results: dict) -> dict:
    """
    Build the dashboard hero's current-in-progress-month estimate and fold
    it into `results` under 'current_month_estimate'. Display-only: it
    never touches vulnerability_scored.csv or the historical record, so a
    failure here should not affect the confirmed score the rest of the
    pipeline already computed.
    """
    from pipeline.build_vulnerability import estimate_current_month
    from pipeline.ingest_bcrd import load_exchange_rate_mtd
    from pipeline.current_month_tracker import (
        record_weekly_snapshot, average_score, week_of_month,
    )

    merged = results.get("merged")
    if merged is None or merged.empty:
        return results

    dop_usd_mtd = load_exchange_rate_mtd(f"{BCRD_DATA_DIR}/TASA_DOLAR_REFERENCIA_MC.xlsx")
    estimate = estimate_current_month(merged, overrides={"dop_usd": dop_usd_mtd})
    if estimate is None:
        return results

    now = datetime.now()
    snapshot_data = record_weekly_snapshot(estimate["score"], as_of=now)
    snapshots = snapshot_data["snapshots"]  # sorted by week, this run's entry last
    prior_week_score = snapshots[-2]["score"] if len(snapshots) >= 2 else None

    results["current_month_estimate"] = {
        "date": estimate["date"],
        "this_week_score": estimate["score"],
        "prior_week_score": prior_week_score,
        "averaged_score": average_score(snapshot_data),
        "week_of_month": week_of_month(now),
        "weeks_recorded": len(snapshots),
        "filled_components": estimate["filled_components"],
        "components_real": estimate["components_real"],
        "components_total": estimate["components_total"],
        "components": estimate["components"],
    }
    return results


def step_write_excel(results: dict) -> Path:
    """Write Excel workbook. Returns output path."""
    from pipeline.write_excel import write_workbook
    return write_workbook(results, path=OUTPUT_PATH)


def step_write_site(results: dict) -> Path:
    """Write HTML report to docs/index.html for GitHub Pages."""
    from pipeline.write_html import write_site
    return write_site(results)


def step_write_weekly_report(results: dict) -> Path | None:
    """
    Write the weekly OneDrive snapshot: the current in-progress month's
    projected score (same number shown on the website hero) as headline,
    to a dated filename so each week's run produces a new file in OneDrive's
    "Weekly Reports" folder rather than overwriting last week's.

    Returns None (no error) if no current-month estimate is available this
    run -- e.g. estimate_current_month() found no genuine signal yet.
    """
    from pipeline.write_excel import write_workbook

    estimate = results.get("current_month_estimate")
    if estimate is None:
        print("  No current-month estimate available -- skipping weekly report.")
        return None

    headline = {
        "date": estimate["date"],
        "score": estimate["averaged_score"],
        "filled_components": estimate["filled_components"],
        "components_real": estimate["components_real"],
        "components_total": estimate["components_total"],
        "components": estimate["components"],
    }

    run_date = datetime.now().strftime("%Y-%m-%d")
    path = f"data/output/vulnerability_report_weekly_{run_date}.xlsx"
    return write_workbook(results, path=path, headline=headline)


def step_write_monthly_report(results: dict) -> Path | None:
    """
    Write the finalized Monthly Report for the most recently confirmed
    month, only if it's new or its is_provisional status changed since the
    last time one was written (e.g. tourism_daily_spend_usd's real value
    finally arrived for that month, correcting the score). State is
    tracked in data/state/monthly_reports_state.json.

    Returns None (no error) if the current confirmed month's report is
    already up to date.
    """
    from pipeline.write_excel import write_workbook
    from pipeline.monthly_report_state import month_key, load_state, needs_upload, record_upload

    score_date = results.get("score_date")
    scored = results.get("scored")
    if score_date is None or scored is None:
        return None

    is_provisional = False
    if "is_provisional" in scored.columns and score_date in scored.index:
        is_provisional = bool(scored.loc[score_date, "is_provisional"])

    month = month_key(score_date)
    state = load_state()
    if not needs_upload(state, month, is_provisional):
        print(f"  Monthly report for {month} already up to date -- skipping.")
        return None

    path = f"data/output/vulnerability_report_{month}.xlsx"
    output_path = write_workbook(results, path=path)
    record_upload(state, month, is_provisional)
    print(f"  Monthly report for {month} written (is_provisional={is_provisional}).")
    return output_path


def step_upload_onedrive(filepath: Path, subfolder: str) -> bool:
    """
    Upload a workbook to OneDrive via Microsoft Graph API (app-only auth),
    into `subfolder` under the configured base folder (e.g. "Weekly
    Reports" or "Monthly Reports").
    Best-effort: failures are logged by the caller in main(), never fatal.
    """
    from pipeline.ms_graph import upload_to_onedrive

    owner_upn = os.getenv("ONEDRIVE_OWNER_UPN", "work@lasociedad.com.do")
    base_folder = os.getenv("ONEDRIVE_FOLDER_PATH", "Economic Intelligence/Output")
    folder_path = f"{base_folder}/{subfolder}"
    return upload_to_onedrive(filepath, owner_upn=owner_upn, folder_path=folder_path)


def step_send_email(results: dict, filepath: Path) -> bool:
    """
    Send weekly summary email via Outlook/Graph sendMail.
    Skips (returns False, no error) if EMAIL_RECIPIENTS is unset/empty.
    Best-effort: failures are logged by the caller in main(), never fatal.

    Body is a static Spanish HTML template (not the score/alerts detail --
    that lives on the dashboard, which the email links to). The Excel is
    available via OneDrive only; no attachment is sent.
    """
    from pipeline.ms_graph import send_summary_email
    from pipeline.write_html import MONTHS_ES

    recipients_raw = os.getenv("EMAIL_RECIPIENTS", "")
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    if not recipients:
        print("  EMAIL_RECIPIENTS not set -- skipping summary email.")
        return False

    sender_upn = os.getenv("EMAIL_SENDER_UPN", "work@lasociedad.com.do")
    estimate = results.get("current_month_estimate")
    score_date = estimate["date"] if estimate is not None else results.get("score_date")
    date_str = (
        f"{MONTHS_ES[score_date.month].capitalize()} de {score_date.year}"
        if score_date else ""
    )

    subject = "Reporte Semanal Economic Intelligence"
    if date_str:
        subject += f" -- {date_str}"

    body_html = build_email_html(
        date_str=date_str,
        dashboard_url=DASHBOARD_URL,
    )

    return send_summary_email(
        sender_upn=sender_upn,
        recipients=recipients,
        subject=subject,
        body_text=body_html,
        content_type="HTML",
        sender_name=EMAIL_SENDER_NAME,
    )


# -- Main --------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="DR Economic Intelligence Pipeline"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip BCRD file download and use cached files in data/raw/"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Skip OneDrive upload and summary email (write local outputs only)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run scoring only -- skip Excel output and upload"
    )
    args = parser.parse_args()

    run_start = datetime.now()

    if args.dry_run:
        total_steps = 2
    else:
        # score, context, excel, html (always) + download (unless skipped)
        # + onedrive & email (unless --local)
        total_steps = 4
        total_steps += 0 if args.skip_download else 1
        total_steps += 0 if args.local else 2

    _section("DR Economic Intelligence Pipeline")
    print(f"  Started: {run_start.strftime('%Y-%m-%d %H:%M:%S')}")
    if args.skip_download:
        print("  Mode: skip BCRD download")
    if args.local:
        print("  Mode: local only (no OneDrive upload or email)")
    if args.dry_run:
        print("  Mode: dry run (no Excel output)")

    step_n = 1

    # -- Step 1: Download BCRD files
    if not args.skip_download:
        _step(step_n, total_steps, "Downloading BCRD Excel files")
        step_n += 1
        try:
            step_download_bcrd()
        except Exception as e:
            print(f"\n  ERROR in BCRD download: {e}")
            print("  Continuing with cached files...")

    # -- Step 2: Score
    _step(step_n, total_steps, "Running vulnerability scoring")
    step_n += 1
    try:
        results = step_score(args.skip_download)
    except Exception as e:
        print(f"\n  FATAL ERROR in scoring: {e}")
        traceback.print_exc()
        return 1

    if args.dry_run:
        _section("Dry run complete -- no output written")
        _print_summary(results, run_start, output_path=None)
        return 0

    print("\nEstimating current month (display only)...")
    try:
        results = step_estimate_current_month(results)
    except Exception as e:
        print(f"\n  WARNING: Current-month estimate failed: {e}")
        traceback.print_exc()

    # -- Step 3: Load context indicators
    _step(step_n, total_steps, "Loading context indicators")
    step_n += 1
    try:
        context = step_load_context()
        results.update(context)
    except Exception as e:
        print(f"\n  WARNING: Context indicators failed: {e}")
        traceback.print_exc()

    # -- Step 4: Write Excel
    _step(step_n, total_steps, "Writing Excel workbook")
    step_n += 1
    output_path = None
    try:
        output_path = step_write_excel(results)
    except Exception as e:
        print(f"\n  FATAL ERROR writing Excel: {e}")
        traceback.print_exc()
        return 1

    # -- Step 5: Write HTML site
    _step(step_n, total_steps, "Generating website")
    step_n += 1
    try:
        site_path = step_write_site(results)
    except Exception as e:
        print(f"\n  FATAL ERROR writing site: {e}")
        traceback.print_exc()
        return 1

    weekly_path = None
    if not args.local:
        # -- Step 6: Write & upload weekly/monthly reports to OneDrive
        _step(step_n, total_steps, "Uploading reports to OneDrive")
        step_n += 1
        try:
            weekly_path = step_write_weekly_report(results)
            if weekly_path:
                step_upload_onedrive(weekly_path, subfolder="Weekly Reports")
        except Exception as e:
            print(f"\n  ERROR writing/uploading weekly report: {e}")

        try:
            monthly_path = step_write_monthly_report(results)
            if monthly_path:
                step_upload_onedrive(monthly_path, subfolder="Monthly Reports")
        except Exception as e:
            print(f"\n  ERROR writing/uploading monthly report: {e}")

        # -- Step 7: Send summary email
        _step(step_n, total_steps, "Sending summary email")
        try:
            step_send_email(results, weekly_path or output_path)
        except Exception as e:
            print(f"\n  ERROR sending summary email: {e}")

    # -- Summary
    _print_summary(results, run_start, output_path=output_path)
    return 0


def _print_summary(results: dict, run_start: datetime, output_path: Path = None) -> None:
    run_end = datetime.now()
    elapsed = (run_end - run_start).total_seconds()

    score      = results.get("current_score")
    score_date = results.get("score_date")
    alerts     = results.get("alerts")

    _section("Pipeline Complete")
    print(f"  Finished:  {run_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Elapsed:   {elapsed:.1f}s")

    if score is not None:
        from pipeline.build_vulnerability import (
            HIGH_STRESS_THRESHOLD,
            MODERATE_STRESS_THRESHOLD,
        )
        date_str = score_date.strftime("%B %Y") if score_date else "Unknown"
        print(f"\n  Score:     {score:.1f} / 100  ({date_str})")
        if score >= HIGH_STRESS_THRESHOLD:
            print(f"  Status:    HIGH STRESS")
        elif score >= MODERATE_STRESS_THRESHOLD:
            print(f"  Status:    MODERATE STRESS")
        else:
            print(f"  Status:    LOW STRESS")

    if alerts is not None and not alerts.empty:
        stress_count = int(alerts["is_stress"].sum())
        print(f"\n  Alerts:    {len(alerts)} flagged "
              f"({stress_count} stress, {len(alerts) - stress_count} notable)")
        for _, alert in alerts.iterrows():
            tag = "STRESS" if alert["is_stress"] else "WATCH"
            print(f"    [{tag}] {alert.get('label', alert['indicator'])}")
    else:
        print(f"\n  Alerts:    None")

    if output_path:
        print(f"\n  Output:    {Path(output_path).resolve()}")
    print(f"{'='*54}")


if __name__ == "__main__":
    sys.exit(main())