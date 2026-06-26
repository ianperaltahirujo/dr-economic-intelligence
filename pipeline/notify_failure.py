"""Called by GitHub Actions on workflow failure to send an alert email."""
import os
import sys

from pipeline.ms_graph import send_summary_email


def main() -> None:
    recipients = [r.strip() for r in os.getenv("EMAIL_RECIPIENTS", "").split(",") if r.strip()]
    if not recipients:
        print("EMAIL_RECIPIENTS not set — failure notification skipped.")
        return

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
