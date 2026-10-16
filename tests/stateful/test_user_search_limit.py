"""Searching for people to share a pet with is limited per signed-in user, not per address."""

SEARCH = "/api/users/search?q=te"  # two letters: the shortest query that searches at all


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_thirty_searches_a_minute_then_429(client, auth_headers):
    for attempt in range(1, 31):
        response = client.get(SEARCH, headers=auth_headers)
        assert response.status_code == 200, f"search {attempt} refused"

    refused = client.get(SEARCH, headers=auth_headers)

    assert refused.status_code == 429
    assert refused.get_json()["code"] == "rate_limit_exceeded"
    assert refused.headers["Retry-After"] == "60"


def test_the_limit_belongs_to_the_person_not_to_the_address(client, auth_headers, regular_user, regular_user_token):
    for _ in range(30):
        client.get(SEARCH, headers=auth_headers)
    assert client.get(SEARCH, headers=auth_headers).status_code == 429

    # The test client sends every request from one address: another person's searches still go through.
    assert client.get(SEARCH, headers=_bearer(regular_user_token)).status_code == 200
