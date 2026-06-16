import tomllib
from pathlib import Path

from cache_vault import __version__
from cache_vault.build_meta import windows_version_tuple


def test_windows_version_tuple_pads_to_four_parts():
    assert windows_version_tuple("0.1.2") == (0, 1, 2, 0)
    assert windows_version_tuple("0.1.3-rc1") == (0, 1, 3, 0)


def test_package_version_matches_pyproject():
    with Path("pyproject.toml").open("rb") as fh:
        pyproject_version = tomllib.load(fh)["project"]["version"]
    assert pyproject_version == __version__
