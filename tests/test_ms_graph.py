"""
Tests for pipeline/ms_graph.py.

All Graph/Azure AD calls are mocked via unittest.mock -- no real network
access, no Azure credentials needed to run these. They verify request
shaping (URLs, headers, payloads), not actual Graph behavior.

Run with:
    pytest tests/test_ms_graph.py -v
"""

import base64
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import ms_graph


def _fake_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


class TestGetAccessToken:
    def test_posts_client_credentials_grant(self, monkeypatch):
        monkeypatch.setenv("AZURE_TENANT_ID", "tenant-123")
        monkeypatch.setenv("AZURE_CLIENT_ID", "client-456")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret-789")

        with patch("pipeline.ms_graph.requests.post") as mock_post:
            mock_post.return_value = _fake_response(
                200, {"access_token": "fake-token"}
            )
            token = ms_graph.get_access_token()

        assert token == "fake-token"
        url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
        assert url == "https://login.microsoftonline.com/tenant-123/oauth2/v2.0/token"
        assert kwargs["data"]["grant_type"] == "client_credentials"
        assert kwargs["data"]["client_id"] == "client-456"
        assert kwargs["data"]["client_secret"] == "secret-789"
        assert kwargs["data"]["scope"] == "https://graph.microsoft.com/.default"

    def test_raises_on_missing_env_vars(self, monkeypatch):
        monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
        monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
        monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)

        with pytest.raises(EnvironmentError):
            ms_graph.get_access_token()


class TestUploadToOnedrive:
    def test_direct_path_success(self, tmp_path):
        filepath = tmp_path / "vulnerability_report.xlsx"
        filepath.write_bytes(b"fake excel bytes")

        with patch("pipeline.ms_graph._graph_request") as mock_req:
            mock_req.return_value = _fake_response(201)
            result = ms_graph.upload_to_onedrive(
                filepath,
                owner_upn="work@lasociedad.com.do",
                folder_path="Economic Intelligence/Output",
                token="tok",
            )

        assert result is True
        method, url = mock_req.call_args[0][0], mock_req.call_args[0][1]
        assert method == "PUT"
        assert url == (
            "https://graph.microsoft.com/v1.0/users/work@lasociedad.com.do/"
            "drive/root:/Economic Intelligence/Output/"
            "vulnerability_report.xlsx:/content"
        )
        assert mock_req.call_args[1]["data"] == b"fake excel bytes"

    def test_failure_returns_false(self, tmp_path):
        filepath = tmp_path / "vulnerability_report.xlsx"
        filepath.write_bytes(b"fake excel bytes")

        with patch("pipeline.ms_graph._graph_request") as mock_req:
            mock_req.return_value = _fake_response(403, text="access denied")
            result = ms_graph.upload_to_onedrive(
                filepath,
                owner_upn="work@lasociedad.com.do",
                folder_path="Economic Intelligence/Output",
                token="tok",
            )

        assert result is False

    def test_missing_file_returns_false_without_request(self, tmp_path):
        filepath = tmp_path / "does_not_exist.xlsx"
        with patch("pipeline.ms_graph._graph_request") as mock_req:
            result = ms_graph.upload_to_onedrive(
                filepath, owner_upn="work@lasociedad.com.do", folder_path="Output",
                token="tok",
            )
        assert result is False
        mock_req.assert_not_called()


class TestSendSummaryEmail:
    def test_no_recipients_skips_without_request(self):
        with patch("pipeline.ms_graph._graph_request") as mock_req:
            result = ms_graph.send_summary_email(
                sender_upn="work@lasociedad.com.do",
                recipients=[],
                subject="subj",
                body_text="body",
                token="tok",
            )
        assert result is False
        mock_req.assert_not_called()

    def test_sends_payload_with_attachment(self, tmp_path):
        attachment = tmp_path / "report.xlsx"
        attachment.write_bytes(b"excel-content")

        with patch("pipeline.ms_graph._graph_request") as mock_req:
            mock_req.return_value = _fake_response(202)
            result = ms_graph.send_summary_email(
                sender_upn="work@lasociedad.com.do",
                recipients=["a@example.com", "b@example.com"],
                subject="Weekly Summary",
                body_text="Score: 42.0 / 100",
                attachment_path=attachment,
                token="tok",
            )

        assert result is True
        method, url = mock_req.call_args[0][0], mock_req.call_args[0][1]
        payload = mock_req.call_args[1]["json"]
        message = payload["message"]

        assert method == "POST"
        assert url == "https://graph.microsoft.com/v1.0/users/work@lasociedad.com.do/sendMail"
        assert [r["emailAddress"]["address"] for r in message["toRecipients"]] == [
            "a@example.com", "b@example.com",
        ]
        assert message["body"]["content"] == "Score: 42.0 / 100"
        attachment_payload = message["attachments"][0]
        assert attachment_payload["@odata.type"] == "#microsoft.graph.fileAttachment"
        assert base64.b64decode(attachment_payload["contentBytes"]) == b"excel-content"

    def test_sends_without_attachment_when_missing(self, tmp_path):
        missing = tmp_path / "missing.xlsx"
        with patch("pipeline.ms_graph._graph_request") as mock_req:
            mock_req.return_value = _fake_response(202)
            ms_graph.send_summary_email(
                sender_upn="work@lasociedad.com.do",
                recipients=["a@example.com"],
                subject="subj",
                body_text="body",
                attachment_path=missing,
                token="tok",
            )
        message = mock_req.call_args[1]["json"]["message"]
        assert "attachments" not in message


class TestGraphRequestRetry:
    def test_retries_on_5xx_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(ms_graph.time, "sleep", lambda s: None)

        responses = [
            _fake_response(500),
            _fake_response(500),
            _fake_response(200),
        ]
        with patch("pipeline.ms_graph.requests.request") as mock_request:
            mock_request.side_effect = responses
            resp = ms_graph._graph_request("GET", "https://example.test", "tok")

        assert resp.status_code == 200
        assert mock_request.call_count == 3

    def test_gives_up_after_max_retries(self, monkeypatch):
        monkeypatch.setattr(ms_graph.time, "sleep", lambda s: None)

        with patch("pipeline.ms_graph.requests.request") as mock_request:
            mock_request.return_value = _fake_response(500)
            resp = ms_graph._graph_request("GET", "https://example.test", "tok")

        assert resp.status_code == 500
        assert mock_request.call_count == ms_graph.MAX_RETRIES + 1
