"""
Microsoft Graph API Client (app-only auth)
Uploads the Excel workbook to OneDrive and sends the weekly summary email.

OneDrive uploads target a folder owner_upn genuinely owns -- app-only auth
cannot resolve "shared with me" items (Graph returns 403 for that under
client-credentials auth, it's delegated-user-only). Visibility into a
shared team folder is handled outside this pipeline, by manually placing a
OneDrive shortcut to the owned output folder inside the shared one.

Authentication: OAuth2 client-credentials flow (no signed-in user).
    POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token
    grant_type=client_credentials, scope=https://graph.microsoft.com/.default
Base URL: https://graph.microsoft.com/v1.0
Required env vars (.env locally, GitHub Actions secrets in CI):
    AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET

The app registration holds application permissions Files.ReadWrite.All,
Sites.ReadWrite.All, User.Read.All, Send.Mail -- there is no delegated user
context anywhere in this module, every call targets a specific mailbox/drive
by UPN (e.g. /users/{upn}/drive, /users/{upn}/sendMail).

This module is a pure Graph client: it takes the target UPN(s), folder path,
and recipients as function parameters. It has no opinion about which mailbox
or folder a given pipeline run should use -- that's decided by the caller
(run_pipeline.py).

Usage:
    from pipeline.ms_graph import upload_to_onedrive, send_summary_email
"""

import base64
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Auth and base config ──────────────────────────────────────────────────────

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

# Maximum number of retries on transient 5xx errors before giving up.
MAX_RETRIES = 3


def get_access_token() -> str:
    """
    Acquire an app-only Graph access token via the OAuth2 client-credentials flow.

    Reads AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET from the
    environment. Raises EnvironmentError if any is missing/blank.

    Returns:
        The bearer token string (without the "Bearer " prefix).
    """
    tenant_id = os.getenv("AZURE_TENANT_ID", "")
    client_id = os.getenv("AZURE_CLIENT_ID", "")
    client_secret = os.getenv("AZURE_CLIENT_SECRET", "")

    missing = [
        name for name, val in [
            ("AZURE_TENANT_ID", tenant_id),
            ("AZURE_CLIENT_ID", client_id),
            ("AZURE_CLIENT_SECRET", client_secret),
        ] if not val
    ]
    if missing:
        raise EnvironmentError(
            f"Missing required env var(s) for Graph auth: {', '.join(missing)}. "
            "Add them to your .env file (or GitHub Actions secrets)."
        )

    token_url = TOKEN_URL_TEMPLATE.format(tenant=tenant_id)
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }
    response = requests.post(token_url, data=data, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


# ── Core HTTP helper ──────────────────────────────────────────────────────────

def _graph_request(method: str, url: str, token: str, **kwargs) -> requests.Response:
    """
    Thin wrapper around requests.{get,put,post} for Graph calls.

    Sets the Authorization header and retries transient 5xx errors up to
    MAX_RETRIES times with exponential backoff (2s, 4s, 8s), mirroring the
    retry convention in pipeline/ingest_sb.py's _fetch_paginated().
    """
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"

    attempt = 0
    while True:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        if response.status_code < 500:
            return response
        if attempt >= MAX_RETRIES:
            return response
        wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
        print(f"  {response.status_code} error on {method} {url} "
              f"(attempt {attempt + 1}/{MAX_RETRIES}), retrying in {wait}s...")
        time.sleep(wait)
        attempt += 1


# ── Feature 1: OneDrive upload ────────────────────────────────────────────────

def upload_to_onedrive(
    filepath: Path,
    owner_upn: str,
    folder_path: str,
    token: str | None = None,
) -> bool:
    """
    Upload `filepath` into owner_upn's OneDrive at folder_path via Graph.

    PUT /users/{owner_upn}/drive/root:/{folder_path}/{filename}:/content

    folder_path must be a folder owner_upn genuinely owns (not merely a
    "shared with me" reference) -- Graph auto-creates any missing folders
    in the path under the owner's own drive rather than 404ing, and
    app-only auth cannot enumerate /drive/sharedWithMe at all (Graph
    returns 403; that endpoint is delegated-user-only). A folder shared
    from someone else's OneDrive is visible to people via a shortcut/link,
    not addressable this way -- see the OneDrive integration note in
    CLAUDE.md/README.md for how this pipeline's output folder is exposed
    inside such a shared folder.

    Never raises -- returns False on failure so callers can treat this as
    best-effort.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"  OneDrive upload: file not found at {filepath}")
        return False

    try:
        if token is None:
            token = get_access_token()
    except Exception as e:
        print(f"  OneDrive upload: failed to acquire Graph token: {e}")
        return False

    folder_path = folder_path.strip("/")
    url = (
        f"{GRAPH_BASE_URL}/users/{owner_upn}/drive/root:/"
        f"{folder_path}/{filepath.name}:/content"
    )

    try:
        with open(filepath, "rb") as f:
            response = _graph_request("PUT", url, token, data=f.read())
    except Exception as e:
        print(f"  OneDrive upload: request failed: {e}")
        return False

    if response.status_code in (200, 201):
        print(f"  OneDrive upload: succeeded -- {folder_path}/{filepath.name}")
        return True

    print(f"  OneDrive upload: failed ({response.status_code}): {response.text[:300]}")
    return False


# ── Feature 2: Outlook email ──────────────────────────────────────────────────

def send_summary_email(
    sender_upn: str,
    recipients: list[str],
    subject: str,
    body_text: str,
    attachment_path: Path | None = None,
    token: str | None = None,
    content_type: str = "Text",
    sender_name: str | None = None,
) -> bool:
    """
    Send a summary email via Graph sendMail, app-only, from sender_upn's
    mailbox.

    content_type: "Text" or "HTML" -- passed straight through to Graph's
    message.body.contentType. Use "HTML" when body_text needs markup (e.g.
    an inline hyperlink).

    sender_name: optional friendly display name for the From field. Because
    we send as the mailbox itself (/users/{sender_upn}/sendMail), Graph
    honors a display-name override on the same address without SendAs --
    the inbox entry reads "<sender_name>" instead of the bare UPN. When
    None, the mailbox's own default display name is used.

    No-ops (returns False, logs) if recipients is empty -- a second guard
    beyond the caller's own check. Never raises.
    """
    if not recipients:
        print("  Summary email: no recipients provided, skipping.")
        return False

    try:
        if token is None:
            token = get_access_token()
    except Exception as e:
        print(f"  Summary email: failed to acquire Graph token: {e}")
        return False

    message = {
        "subject": subject,
        "body": {"contentType": content_type, "content": body_text},
        "toRecipients": [
            {"emailAddress": {"address": addr}} for addr in recipients
        ],
    }

    if sender_name:
        message["from"] = {
            "emailAddress": {"address": sender_upn, "name": sender_name}
        }

    if attachment_path is not None:
        attachment_path = Path(attachment_path)
        if attachment_path.exists():
            content_bytes = base64.b64encode(attachment_path.read_bytes()).decode("ascii")
            message["attachments"] = [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": attachment_path.name,
                "contentBytes": content_bytes,
            }]
        else:
            print(f"  Summary email: attachment not found at {attachment_path}, sending without it.")

    url = f"{GRAPH_BASE_URL}/users/{sender_upn}/sendMail"
    try:
        response = _graph_request(
            "POST", url, token,
            json={"message": message, "saveToSentItems": "false"},
        )
    except Exception as e:
        print(f"  Summary email: request failed: {e}")
        return False

    if response.status_code == 202:
        print(f"  Summary email: sent to {len(recipients)} recipient(s).")
        return True

    print(f"  Summary email: failed ({response.status_code}): {response.text[:300]}")
    return False
