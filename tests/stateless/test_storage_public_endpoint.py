"""Links the browser uses are signed for the address the browser can reach, not the server's internal one.

On a local stand the storage is called «s3» inside the compose network, which the browser cannot see. Its links
must carry the published address instead, and the server keeps its own address for everything else. Without
S3_PUBLIC_ENDPOINT, both stay the same, as in production.
"""

import pytest

from web import storage


@pytest.fixture
def storage_env(monkeypatch):
    monkeypatch.setenv("S3_ENDPOINT", "http://s3:7070")
    monkeypatch.setenv("S3_BUCKET", "petzy-test")
    monkeypatch.setenv("S3_KEY_ID", "key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret")
    monkeypatch.setenv("S3_REGION", "us-east-1")


def test_upload_links_use_the_public_address_when_one_is_set(storage_env, monkeypatch):
    monkeypatch.setenv("S3_PUBLIC_ENDPOINT", "http://localhost:7070")
    url = storage.upload_url("users/a/scan.zip", "application/zip", 1000)
    assert url.startswith("http://localhost:7070/")


def test_without_a_public_address_the_links_are_the_servers_own(storage_env, monkeypatch):
    monkeypatch.delenv("S3_PUBLIC_ENDPOINT", raising=False)
    assert storage.upload_url("users/a/scan.zip", "application/zip", 1000).startswith("http://s3:7070/")


def test_download_links_use_the_public_address_too(storage_env, monkeypatch):
    monkeypatch.setenv("S3_PUBLIC_ENDPOINT", "http://localhost:7070")
    assert storage.download_url("users/a/scan.zip", 'attachment; filename="scan.zip"').startswith(
        "http://localhost:7070/"
    )
