"""A picture sent to the preview is refused when there is nothing to look at, when it is too big
and when it is not a picture at all.

The preview turns a phone's HEIC into something a browser can draw. It stores nothing, so every
refusal here is a refusal to work with the file, not a refusal to keep it: the person still has
the file on the phone and can send another one.
"""

import io

from web.documents import MAX_DOCUMENT_SIZE_BYTES


def _post(client, token, data=None, name="IMG_1.heic", ctype="image/heic"):
    payload = {} if data is None else {"file": (io.BytesIO(data), name, ctype)}
    return client.post(
        "/api/images/preview",
        data=payload,
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


def test_no_file_at_all_is_refused(client, mock_db, regular_user_token):
    response = _post(client, regular_user_token)

    assert response.status_code == 422
    assert response.get_json()["code"] == "document_file_required"


def test_a_file_without_a_name_is_refused(client, mock_db, regular_user_token):
    """An empty name is not a file: there is nothing to look at."""
    response = _post(client, regular_user_token, b"\xff\xd8\xff data", name="")

    assert response.status_code == 422
    assert response.get_json()["code"] == "document_file_required"


def test_a_file_bigger_than_the_limit_is_refused(client, mock_db, regular_user_token):
    response = _post(client, regular_user_token, b"\xff\xd8\xff" + b"0" * MAX_DOCUMENT_SIZE_BYTES, ctype="image/jpeg")

    assert response.status_code == 422
    assert response.get_json()["code"] == "document_file_too_large"


def test_a_file_that_cannot_be_read_as_a_picture_is_refused(client, mock_db, regular_user_token):
    """The first bytes say it is a picture, and it is not: the browser would show it broken."""
    response = _post(client, regular_user_token, b"\xff\xd8\xff" + b"0" * 100, ctype="image/jpeg")

    assert response.status_code == 422
    assert response.get_json()["code"] == "document_content_mismatch"
