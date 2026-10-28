"""Client profiles: server URL, key id and the path of the private key file. The private
key stays in its own file, readable by its owner only; the profile never holds it."""

import json
import os
import stat
from pathlib import Path

from pydantic import BaseModel, Field

from mindgrid.platform.apikeys.client import KeyCredentials

from . import config as remote_config

NAME = r"^[a-z0-9][a-z0-9_-]{0,31}$"


class Profile(BaseModel):
    name: str = Field(pattern=NAME)
    server: str = Field(description="Base URL, e.g. https://mindgrid.example.com")
    key_id: str = Field(pattern=r"^mgk_[A-Za-z0-9_-]{8,64}$")
    key_file: str

    def credentials(self) -> KeyCredentials:
        path = Path(self.key_file).expanduser()
        if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise PermissionError(f"{path} is readable by others: chmod 600 it first")
        return KeyCredentials.from_pem(self.key_id, path.read_text(encoding="utf-8"))


def _file() -> Path:
    return remote_config.config_dir() / "profiles.json"


def write_private(path: Path, text: str) -> None:
    """Write a file only its owner can read (folders owner-only too)."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(text)
    path.chmod(0o600)


def load_all() -> dict[str, Profile]:
    path = _file()
    if not path.exists():
        return {}
    raw: dict[str, dict[str, str]] = json.loads(path.read_text(encoding="utf-8"))
    return {name: Profile.model_validate({**value, "name": name}) for name, value in raw.items()}


def save(profile: Profile) -> None:
    profiles = load_all() | {profile.name: profile}
    body = {n: p.model_dump(exclude={"name"}) for n, p in sorted(profiles.items())}
    write_private(_file(), json.dumps(body, indent=2) + "\n")


def get(name: str = "") -> Profile:
    wanted = name or remote_config.get_settings().profile
    found = load_all().get(wanted)
    if found is None:
        raise LookupError(f"no client profile {wanted!r}: run `mindgrid login` first")
    return found
