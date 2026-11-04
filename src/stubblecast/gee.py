"""Earth Engine authentication from a service account.

Credentials are read, in order, from:
  1. GEE_SERVICE_ACCOUNT_KEY  - the key JSON itself, raw or base64-encoded (cloud secret)
  2. GOOGLE_APPLICATION_CREDENTIALS - path to the key JSON
The project comes from GEE_PROJECT. Values may be set in a git-ignored .env file.
"""

from __future__ import annotations

import base64
import binascii
import json
import os

from dotenv import load_dotenv

from stubblecast.config import REPO_ROOT

SCOPES = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/cloud-platform",
]


class GEEUnavailable(RuntimeError):
    """Raised when Earth Engine credentials are missing or rejected."""


def parse_key(value: str) -> dict:
    """Parse a service-account key given as raw JSON or base64-encoded JSON.

    Cloud secret stores often hold multi-line JSON base64-encoded, so accept both.
    """
    text = value.strip()
    if not text.startswith("{"):
        try:
            text = base64.b64decode(text, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as e:
            raise GEEUnavailable("GEE_SERVICE_ACCOUNT_KEY is neither JSON nor base64 JSON") from e
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise GEEUnavailable("GEE_SERVICE_ACCOUNT_KEY does not contain valid JSON") from e


def initialize() -> str:
    """Initialise Earth Engine; return the project ID. Raises GEEUnavailable."""
    import ee
    from google.oauth2 import service_account

    load_dotenv(REPO_ROOT / ".env")
    key_json = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
    key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if key_json:
        info = parse_key(key_json)
    elif key_path and os.path.exists(key_path):
        with open(key_path) as f:
            info = json.load(f)
    else:
        raise GEEUnavailable("No service-account key (GEE_SERVICE_ACCOUNT_KEY / "
                             "GOOGLE_APPLICATION_CREDENTIALS)")
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    # Project: explicit GEE_PROJECT wins; otherwise the key's own project.
    project = os.environ.get("GEE_PROJECT") or info.get("project_id")
    if not project:
        raise GEEUnavailable("GEE_PROJECT is not set and the key has no project_id")
    try:
        ee.Initialize(credentials=creds, project=project)
        ee.Number(1).getInfo()  # force a round trip so failures surface here
    except Exception as e:  # noqa: BLE001 - surface any auth/registration error uniformly
        raise GEEUnavailable(str(e)) from e
    return project
