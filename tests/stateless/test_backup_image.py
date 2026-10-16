"""backup/Dockerfile runs the backup as a user of its own, not root."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "backup" / "Dockerfile"


def _instructions() -> list[str]:
    lines = (line.strip() for line in DOCKERFILE.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def _user_instructions() -> list[tuple[int, str]]:
    """(position, user) of each USER instruction, in file order."""
    instructions = _instructions()
    return [
        (position, line.split(None, 1)[1].strip())
        for position, line in enumerate(instructions)
        if line.split(None, 1)[0].upper() == "USER"
    ]


def test_the_backup_does_not_run_as_root():
    users = _user_instructions()
    assert users, "backup/Dockerfile has no USER: the backup would run as root"
    assert users[-1][1].split(":")[0] not in ("root", "0")


def test_the_user_is_created_before_the_image_switches_to_it():
    users = _user_instructions()
    assert users, "backup/Dockerfile has no USER"
    position, user = users[-1]
    name = user.split(":")[0]
    created = any("useradd" in line and name in line.split() for line in _instructions()[:position])
    assert created, f"no useradd for {name} before USER {name}: the container could not start"
