"""Which build is answering: the commit it was made from.

A bug report says what a person saw, and «what they saw» is a build. Without
this there is no way to tell a person on last week's code from one on today's,
and the first question in every report becomes «а у вас какая версия».

The commit is written into .env by the deploy workflow, which is already the
web container's env_file, so nothing carries it by hand. A run that was not
deployed by that workflow (a laptop, the local stand) has no commit to report
and says so rather than inventing one.
"""

import os

from flask import Blueprint, jsonify
from flask_pydantic_spec import Response

from web.app import api
from web.schemas import VersionResponse

version_bp = Blueprint("version", __name__)

COMMIT_KEY = "PETZY_BUILD_SHA"


def _clean(value: str | None) -> str:
    """A commit as one short hex string, or an empty one.

    Anything that is not a plain hex string is dropped rather than put in an
    answer and shown to somebody, where it would be read as a commit.
    """
    text = (value or "").strip()
    if len(text) >= 7 and all(c in "0123456789abcdefABCDEF" for c in text):
        return text.lower()
    return ""


@version_bp.route("/api/version", methods=["GET"])
@api.validate(
    resp=Response(HTTP_200=VersionResponse, HTTP_500=None),
    tags=["push"],
)
def version():
    """Which commit is answering.

    Both names are the same number: the full one to paste into a report, the
    first seven to say out loud. They are empty and ``known`` is false when the
    run was not started by the deploy workflow, since there is no commit to
    report and a wrong one would send whoever reads a bug report to the wrong
    place.
    """
    commit = _clean(os.environ.get(COMMIT_KEY))
    return jsonify({"commit": commit, "short": commit[:7], "known": bool(commit)})
