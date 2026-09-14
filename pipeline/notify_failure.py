"""Called by GitHub Actions on workflow failure to send an alert email.

Failure alerts always go to FAILURE_NOTIFICATION_RECIPIENT only, independent
of EMAIL_RECIPIENTS (the weekly summary's distribution list) -- an internal
diagnostic email should not fan out to the same people who get the normal
report.
"""
import os
import sys

from pipeline.ms_graph import send_summary_email

FAILURE_NOTIFICATION_RECIPIENT = "iep5058@psu.edu"


def main() -> None:
    recipients = [FAILURE_NOTIFICATION_RECIPIENT]

    run_url = os.getenv(
        "GH_RUN_URL",
        "https://github.com/ianperaltahirujo/dr-economic-intelligence/actions",
    )
    ok = send_summary_email(
        sender_upn=os.getenv("EMAIL_SENDER_UPN", "work@lasociedad.com.do"),
        recipients=recipients,
        subject="[ALERTA] Pipeline DR Economic Intelligence falló",
        body_text=(
            "El pipeline semanal falló y no actualizó el dashboard.\n\n"
            f"Revisar la ejecución en GitHub Actions:\n{run_url}"
        ),
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
