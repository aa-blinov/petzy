"""Tests for web.configs — a pure config-loading/masking module.

get_config_json() isn't called from any route (it's a manual debug/
reference helper), but it's a small self-contained pure function worth
verifying directly: it must actually mask secrets rather than leak them
into whatever log or shell a maintainer pastes its output into.
"""

import json

import pytest


@pytest.mark.unit
def test_get_config_json_masks_secrets_present_in_env():
    from web.configs import get_config_json

    result = json.loads(get_config_json())

    assert result["admin"]["password_hash"] == "***MASKED***"
    assert result["mongodb"]["pass"] == "***MASKED***"
    # Both secret_key fields present in this test env are real (non-default)
    # values, so both must be masked too.
    assert result["flask"]["secret_key"] == "***MASKED***"
    assert result["jwt"]["secret_key"] == "***MASKED***"

    # Everything else survives untouched — this isn't a stub.
    assert "mongodb" in result and "host" in result["mongodb"]
