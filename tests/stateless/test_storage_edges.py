"""The storage layer at its edges: a bucket that is not set up, a bucket with more objects than one
page, an error that is not «the file is not there» and a file that was never stored.

The rules here are the ones a person relies on without seeing them: nothing is lost when a page of
objects is read, an error that is not a missing file is not swallowed, and a file that is not there
is removed without an error.
"""

import pytest
from botocore.exceptions import ClientError


class _FakeClient:
    """A storage client that answers with what the test says it should."""

    def __init__(self, **answers):
        self.answers = answers
        self.calls = []

    def list_objects_v2(self, **kwargs):
        self.calls.append(("list_objects_v2", kwargs))
        pages = self.answers["pages"]
        return pages[len([c for c in self.calls if c[0] == "list_objects_v2"]) - 1]

    def list_object_versions(self, **kwargs):
        self.calls.append(("list_object_versions", kwargs))
        pages = self.answers["versions"]
        return pages[len([c for c in self.calls if c[0] == "list_object_versions"]) - 1]

    def delete_object(self, **kwargs):
        self.calls.append(("delete_object", kwargs))

    def delete_objects(self, **kwargs):
        self.calls.append(("delete_objects", kwargs))

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        raise self.answers["head_error"]


def _client_error(code):
    return ClientError({"Error": {"Code": code, "Message": code}}, "GetObject")


def test_without_the_storage_settings_the_client_says_what_is_missing(monkeypatch):
    from web import storage

    for name in ("S3_ENDPOINT", "S3_BUCKET", "S3_KEY_ID", "S3_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    storage.reset_client()

    with pytest.raises(storage.StorageNotConfigured):
        storage.put_bytes("users/a/photo.webp", b"x", "image/webp")

    storage.reset_client()


def test_an_error_that_is_not_a_missing_file_is_not_swallowed(monkeypatch):
    """A bucket that refuses the read must not look like an empty file."""
    from web import storage

    def refuse(key):
        raise _client_error("AccessDenied")

    monkeypatch.setattr(storage, "get_bytes", refuse)

    with pytest.raises(ClientError):
        storage.get_bytes_if_exists("users/a/photo.webp")


def test_the_size_of_a_file_that_cannot_be_read_is_not_swallowed(monkeypatch):
    from web import storage

    fake = _FakeClient(head_error=_client_error("AccessDenied"))
    monkeypatch.setattr(storage, "_client", lambda public=False: fake)

    with pytest.raises(ClientError):
        storage.object_size("users/a/photo.webp")


def test_a_missing_file_has_no_size(monkeypatch):
    from web import storage

    fake = _FakeClient(head_error=_client_error("404"))
    monkeypatch.setattr(storage, "_client", lambda public=False: fake)

    assert storage.object_size("users/a/photo.webp") is None


def test_every_page_of_objects_is_read(monkeypatch):
    """A bucket with more objects than one page is read whole, not up to the first page."""
    from web import storage

    fake = _FakeClient(
        pages=[
            {
                "Contents": [{"Key": "users/a/one.webp", "Size": 1, "LastModified": "then"}],
                "IsTruncated": True,
                "NextContinuationToken": "second-page",
            },
            {
                "Contents": [{"Key": "users/a/two.webp", "Size": 2, "LastModified": "later"}],
                "IsTruncated": False,
            },
        ]
    )
    monkeypatch.setattr(storage, "_client", lambda public=False: fake)

    found = storage.list_objects("users/a/")

    assert [obj["key"] for obj in found] == ["users/a/one.webp", "users/a/two.webp"]
    second_call = [call for call in fake.calls if call[0] == "list_objects_v2"][1]
    assert second_call[1]["ContinuationToken"] == "second-page"


def test_every_version_of_an_object_is_read(monkeypatch):
    from web import storage

    fake = _FakeClient(
        versions=[
            {
                "Versions": [{"Key": "users/a/one.webp", "VersionId": "v1"}],
                "IsTruncated": True,
                "NextKeyMarker": "users/a/one.webp",
                "NextVersionIdMarker": "v1",
            },
            {
                "Versions": [{"Key": "users/a/two.webp", "VersionId": "v2"}],
                "IsTruncated": False,
            },
        ]
    )
    monkeypatch.setattr(storage, "_client", lambda public=False: fake)

    assert storage.delete_prefix("users/a/") == 2
    second_call = [call for call in fake.calls if call[0] == "list_object_versions"][1]
    assert second_call[1]["KeyMarker"] == "users/a/one.webp"
    assert second_call[1]["VersionIdMarker"] == "v1"


def test_a_file_that_was_never_stored_is_removed_without_versions(monkeypatch):
    """A file that is not there has no versions to go through: it is removed as it is."""
    from web import storage

    fake = _FakeClient(versions=[{"Versions": [], "DeleteMarkers": [], "IsTruncated": False}])
    monkeypatch.setattr(storage, "_client", lambda public=False: fake)

    storage.delete_object("users/a/never-stored.webp")

    deleted = [call for call in fake.calls if call[0] == "delete_object"]
    assert deleted and deleted[0][1]["Key"] == "users/a/never-stored.webp"


def test_a_format_the_server_does_not_know_is_not_a_picture():
    from web import storage

    assert storage.matches_family(b"whatever", "unknown-format") is False
