import sys
from pathlib import Path

import pytest

# Make the repo root importable so ``import cache_vault`` works regardless of
# where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cache_vault.core.settings import Settings  # noqa: E402
from cache_vault.core.storage import VaultStorage  # noqa: E402
from cache_vault.core.vault import Vault  # noqa: E402


@pytest.fixture
def storage():
    s = VaultStorage(":memory:")
    yield s
    s.close()


@pytest.fixture
def vault():
    # In-memory DB + default settings that never touch disk.
    v = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    yield v
    v.close()
