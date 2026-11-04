import base64
import json

import pytest

from stubblecast.gee import GEEUnavailable, parse_key

KEY = {"type": "service_account", "project_id": "p", "client_email": "a@b"}


def test_parse_raw_json():
    assert parse_key(json.dumps(KEY)) == KEY


def test_parse_base64_json():
    enc = base64.b64encode(json.dumps(KEY).encode()).decode()
    assert parse_key(f"  {enc}\n") == KEY


def test_parse_garbage_raises():
    with pytest.raises(GEEUnavailable):
        parse_key("not a key!")
