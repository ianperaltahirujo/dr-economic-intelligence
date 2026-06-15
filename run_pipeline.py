"""
DR Economic Intelligence Pipeline - Main Entry Point
Runs the full weekly pipeline in order:

    1. Download fresh BCRD Excel files from CDN
    2. Run vulnerability scoring (BCRD + SB API + FRED)
    3. Load context indicators (gas, tourism, debt)
    4. Write Excel workbook to data/output/
    5. Write HTML site to docs/index.html
    6. (Future) Upload to SharePoint via Microsoft Graph API

Usage:
    python run_pipeline.py                  # full run
    python run_pipeline.py --skip-download  # skip BCRD download (use cached files)
    python run_pipeline.py --dry-run        # score only, no Excel output
"""

import sys
import argparse
import traceback
from datetime import datetime
from pathlib import Path

# -- Config ------------------------------------------------------------------

BCRD_DATA_DIR   = "data/raw"
OUTPUT_PATH     = "data/output/vulnerability_report.xlsx"

# -- Helpers -----------------------------------------------------------------

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


def step_write_excel(results: dict) -> Path:
    """Write Excel workbook. Returns output path."""
    from pipeline.write_excel import write_workbook
    return write_workbook(results, path=OUTPUT_PATH)


def step_write_site(results: dict) -> Path:
    """Write HTML report to docs/index.html for GitHub Pages."""
    from pipeline.write_html import write_site
    return write_site(results)


def step_upload_sharepoint(filepath: Path) -> bool:
    """
    Upload workbook to SharePoint via Microsoft Graph API.
    NOT YET IMPLEMENTED -- requires Azure AD app credentials.

    To enable:
    1. Add to .env:
           AZURE_TENANT_ID=...
           AZURE_CLIENT_ID=...
           AZURE_CLIENT_SECRET=...
           SHAREPOINT_DRIVE_ID=...
           SHAREPOINT_FOLDER_PATH=...
    2. Implement the upload logic below using the msal + requests libraries.
    3. Remove the early return.
    """
    print("  SharePoint upload: not yet configured.")
    print("  Add Azure AD credentials to .env to enable automatic upload.")
    print(f"  Local file available at: {filepath.resolve()}")
    return False


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
        "--dry-run",
        action="store_true",
        help="Run scoring only -- skip Excel output and upload"
    )
    args = parser.parse_args()

    run_start = datetime.now()

    if args.dry_run:
        total_steps = 2
    elif args.skip_download:
        total_steps = 5
    else:
        total_steps = 6

    _section("DR Economic Intelligence Pipeline")
    print(f"  Started: {run_start.strftime('%Y-%m-%d %H:%M:%S')}")
    if args.skip_download:
        print("  Mode: skip BCRD download")
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
        print(f"\n  ERROR writing site: {e}")
        traceback.print_exc()

    # -- Step 6: Upload to SharePoint
    _step(step_n, total_steps, "Uploading to SharePoint")
    try:
        step_upload_sharepoint(output_path)
    except Exception as e:
        print(f"\n  ERROR in SharePoint upload: {e}")

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
        date_str = score_date.strftime("%B %Y") if score_date else "Unknown"
        print(f"\n  Score:     {score:.1f} / 100  ({date_str})")
        if score >= 65:
            print(f"  Status:    HIGH STRESS")
        elif score >= 50:
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