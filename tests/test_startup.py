from cache_vault.core import startup


def test_launch_command_includes_app_in_dev():
    cmd = startup.launch_command()
    assert "app.py" in cmd          # dev run launches app.py
    assert cmd.count('"') >= 2      # paths are quoted


def test_is_enabled_returns_bool_without_crashing():
    # Read-only registry probe — must never raise, even if the key is absent.
    assert isinstance(startup.is_enabled(), bool)


def test_app_name_constant():
    assert startup.APP_NAME == "CacheVault"
