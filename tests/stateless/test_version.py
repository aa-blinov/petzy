"""Which build is answering, and what it says when it cannot tell.

An answer that is wrong is worse than one that is missing: a person deciding
whether a bug is theirs or ours reads this before reading the report.
"""

import pytest


class TestTheVersionAnswer:
    def test_a_deploy_names_its_commit(self, client, monkeypatch):
        monkeypatch.setenv("PETZY_BUILD_SHA", "D38DF68CF0A3B5AA2E177799D759DC5C45C2C3DD")
        body = client.get("/api/version").get_json()
        assert body == {"commit": "d38df68cf0a3b5aa2e177799d759dc5c45c2c3dd", "short": "d38df68", "known": True}

    def test_a_run_without_a_deploy_says_so_rather_than_guessing(self, client, monkeypatch):
        monkeypatch.delenv("PETZY_BUILD_SHA", raising=False)
        body = client.get("/api/version").get_json()
        assert body == {"commit": "", "short": "", "known": False}, "a made-up commit is worse than none"

    @pytest.mark.parametrize("value", ["not-a-commit", "", "   ", "abc", "../../etc/passwd", "12 34 56"])
    def test_anything_that_is_not_a_commit_is_not_answered_with(self, client, monkeypatch, value):
        """The environment is not a promise: a stray value must not be shown as a commit."""
        monkeypatch.setenv("PETZY_BUILD_SHA", value)
        body = client.get("/api/version").get_json()
        assert body["known"] is False, value
        assert body["commit"] == "", value

    def test_it_needs_no_sign_in(self, client):
        """A person reporting a bug has no account yet, and that is the moment this is read."""
        assert client.get("/api/version").status_code == 200

    def test_it_is_in_the_reference(self, client):
        spec = client.get("/api/openapi.json").get_json()
        assert spec["paths"]["/api/version"]["get"]["security"] == []
