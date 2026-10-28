"""The ORM models and the migrated schema agree (no hand-made drift either way)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]


@pytest.mark.db
@pytest.mark.usefixtures("_migrated")
def test_models_match_migrations() -> None:
    env = {
        **os.environ,
        "MINDGRID_MIGRATION_DATABASE_URL": os.environ["MINDGRID_TEST_MIGRATION_DATABASE_URL"],
    }
    out = subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stdout + out.stderr
