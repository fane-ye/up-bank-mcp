import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))


@pytest.fixture(autouse=True)
def up_pat(monkeypatch):
    monkeypatch.setenv("UP_PAT", "up:yeah:testtoken")
