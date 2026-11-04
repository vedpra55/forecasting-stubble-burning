"""Earth Engine authentication from a service account.

Credentials are read, in order, from:
  1. GEE_SERVICE_ACCOUNT_KEY  - the key JSON itself (cloud secret)
  2. GOOGLE_APPLICATION_CREDENTIALS - path to the key JSON
The project comes from GEE_PROJECT. Values may be set in a git-ignored .env file.
"""

from __future__ import annotations

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


def initialize() -> str:
    """Initialise Earth Engine; return the project ID. Raises GEEUnavailable."""
    import ee
    from google.oauth2 import service_account

    load_dotenv(REPO_ROOT / ".env")
    project = os.environ.get("GEE_PROJECT")
    if not project:
        raise GEEUnavailable("GEE_PROJECT is not set")

    key_json = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
    key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if key_json:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(key_json), scopes=SCOPES
        )
    elif key_path and os.path.exists(key_path):
        creds = service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)
    else:
        raise GEEUnavailable("No service-account key (GEE_SERVICE_ACCOUNT_KEY / "
                             "GOOGLE_APPLICATION_CREDENTIALS)")
    try:
        ee.Initialize(credentials=creds, project=project)
        ee.Number(1).getInfo()  # force a round trip so failures surface here
    except Exception as e:  # noqa: BLE001 - surface any auth/registration error uniformly
        raise GEEUnavailable(str(e)) from e
    return project
