"""Vault Macros — setup wizard, Macro Safes, smart filters, and classification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cache_vault.core import models
from cache_vault.core.editable_copies import receipts_dir
from cache_vault.core.settings import Settings
from cache_vault.core.vault_macros import (
    MACRO_FILTER_ALL,
    MACRO_FILTER_BROKEN,
    MACRO_FILTER_DISABLED,
    MACRO_FILTER_FAVORITES,
    MACRO_FILTER_HOTKEY_CONFLICTS,
    MACRO_FILTER_NO_TRIGGER,
    MACRO_FILTER_RECENTLY_USED,
    Macro,
    MacroSafeRegistry,
    MacroStore,
    OUTPUT_CLIPBOARD_PASTE,
    SMART_CODE_SNIPPET,
    SMART_EMAIL_TEMPLATE,
    SMART_LINK,
    TRIGGER_HOTKEY,
    TRIGGER_MENU_ONLY,
    TRIGGER_TEXT_SHORTCUT,
    SetupChoices,
    apply_macro_filter,
    complete_macro_setup,
    create_from_template,
    export_macros_proof_pack,
    has_hotkey_conflict,
    suggest_smart_type,
)


@pytest.fixture
def macro_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    settings = Settings()
    store = MacroStore(tmp_path / "CacheVault" / "macros.json")
    registry = MacroSafeRegistry(settings)
    return settings, store, registry, tmp_path


def test_setup_creates_starter_safes_once(macro_env):
    settings, _store, registry, _tmp = macro_env
    r1 = complete_macro_setup(settings, choices=SetupChoices())
    assert r1["ok"]
    assert len(r1["created_safes"]) == 6
    assert settings.vault_macros_setup_completed
    r2 = complete_macro_setup(settings, choices=SetupChoices(create_starter_safes=True))
    assert r2["created_safes"] == []


def test_setup_does_not_overwrite_user_macro_safes(macro_env):
    settings, _store, registry, _tmp = macro_env
    settings.user_macro_safes = [{
        "id": "email-templates",
        "name": "My Custom Email Safe",
        "builtin": False,
        "created_at": models.now_iso(),
    }]
    complete_macro_setup(settings)
    user = registry._user_safes()
    custom = [s for s in user if s.id == "email-templates"]
    assert custom and custom[0].name == "My Custom Email Safe"


def test_smart_filters_categorize(macro_env):
    settings, store, registry, _tmp = macro_env
    macros = [
        Macro(id="1", name="fav", favorite=True, body="x"),
        Macro(id="2", name="off", enabled=False, body="y"),
        Macro(id="3", name="used", body="z", last_used_at="2026-06-17T00:00:00+00:00"),
        Macro(id="4", name="code", smart_type=SMART_CODE_SNIPPET, body="def a(): pass"),
    ]
    store.save_all(macros)
    loaded = store.load_all()
    ctx = {"registry": registry, "all_macros": loaded, "settings": settings}
    assert len(apply_macro_filter(loaded, MACRO_FILTER_FAVORITES, registry=registry, settings=settings)) == 1
    assert len(apply_macro_filter(loaded, MACRO_FILTER_DISABLED, registry=registry, settings=settings)) == 1
    assert apply_macro_filter(loaded, MACRO_FILTER_RECENTLY_USED, registry=registry, settings=settings)[0].id == "3"
    assert len(apply_macro_filter(loaded, "macro:type:code_snippet", registry=registry, settings=settings)) == 1


def test_hotkey_conflict_filter(macro_env):
    settings, store, registry, _tmp = macro_env
    macros = [
        Macro(id="a", name="a", body="1", trigger_type=TRIGGER_HOTKEY, trigger_value="ctrl+shift+m"),
        Macro(id="b", name="b", body="2", trigger_type=TRIGGER_HOTKEY, trigger_value="ctrl+shift+m"),
    ]
    store.save_all(macros)
    loaded = store.load_all()
    conflicts = apply_macro_filter(loaded, MACRO_FILTER_HOTKEY_CONFLICTS, registry=registry, settings=settings)
    assert len(conflicts) == 2
    assert has_hotkey_conflict(loaded[0], registry=registry, all_macros=loaded, settings=settings)


def test_no_trigger_filter(macro_env):
    settings, store, registry, _tmp = macro_env
    m = Macro(id="x", name="empty trigger", body="hi", trigger_type=TRIGGER_HOTKEY, trigger_value="")
    store.save_all([m])
    loaded = store.load_all()
    rows = apply_macro_filter(loaded, MACRO_FILTER_NO_TRIGGER, registry=registry, settings=settings)
    assert len(rows) == 1


def test_disabled_filter(macro_env):
    settings, store, registry, _tmp = macro_env
    store.save_all([Macro(id="d", name="d", body="x", enabled=False)])
    loaded = store.load_all()
    assert len(apply_macro_filter(loaded, MACRO_FILTER_DISABLED, registry=registry, settings=settings)) == 1


def test_recently_used_filter(macro_env):
    settings, store, registry, _tmp = macro_env
    store.save_all([
        Macro(id="old", name="old", body="a", last_used_at="2026-06-01T00:00:00+00:00"),
        Macro(id="new", name="new", body="b", last_used_at="2026-06-17T00:00:00+00:00"),
    ])
    loaded = store.load_all()
    recent = apply_macro_filter(loaded, MACRO_FILTER_RECENTLY_USED, registry=registry, settings=settings)
    assert recent[0].id == "new"


def test_smart_classification_suggestions():
    from cache_vault.core.vault_macros import SMART_COMMAND
    assert suggest_smart_type("https://example.com") == SMART_LINK
    assert suggest_smart_type("def foo():\n    pass") == SMART_CODE_SNIPPET
    assert suggest_smart_type("git status") == SMART_COMMAND


def test_templates_create_valid_records(macro_env):
    settings, store, registry, _tmp = macro_env
    macro = create_from_template("email_signature", registry=registry)
    assert macro.name
    assert macro.body
    assert macro.safe_id
    store.upsert(macro)
    assert store.get(macro.id) is not None


def test_receipts_for_setup_and_template(macro_env, monkeypatch):
    settings, store, registry, tmp_path = macro_env
    receipts: list[dict] = []

    def capture(action: str, payload: dict) -> None:
        receipts.append({"action": action, **payload})

    complete_macro_setup(settings, record_receipt=capture)
    assert any(r["action"] == "vault_macros_setup_completed" for r in receipts)

    from cache_vault.core.macro_receipts import record_macro_receipt
    from cache_vault.core.events import EventLog
    from cache_vault.core.storage import VaultStorage

    vault = __import__("cache_vault.core.vault", fromlist=["Vault"]).Vault(
        storage=VaultStorage(":memory:"), settings=settings,
    )
    record_macro_receipt(
        vault.events,
        action="macro_template_created",
        event_type=models.EVENT_MACRO_TEMPLATE_CREATED,
        macro_id="abc",
        template_id="blank",
        smart_type=SMART_CODE_SNIPPET,
    )
    files = list(receipts_dir().glob("macro_template_created-*.json"))
    assert files
    body = json.loads(files[0].read_text(encoding="utf-8"))
    assert "content" not in body
    assert "body" not in body


def test_sensitive_macro_content_not_in_receipt(macro_env):
    settings, store, registry, tmp_path = macro_env
    from cache_vault.core.events import EventLog
    from cache_vault.core.macro_receipts import record_macro_receipt
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    vault = Vault(storage=VaultStorage(":memory:"), settings=settings)
    record_macro_receipt(
        vault.events,
        action="macro_smart_type_assigned",
        event_type=models.EVENT_MACRO_SMART_TYPE_ASSIGNED,
        macro_id="secret-macro",
        smart_type=SMART_EMAIL_TEMPLATE,
        extra={"body": "should-not-appear", "password": "nope"},
    )
    files = list(receipts_dir().glob("macro_smart_type_assigned-*.json"))
    assert files
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert "body" not in data
    assert "password" not in data


def test_export_manifest_includes_macro_metadata(macro_env, tmp_path):
    settings, store, registry, _tmp = macro_env
    macro = Macro(
        id="m1", name="Export me", body="hello macro",
        safe_id="macro-safe", smart_type=SMART_EMAIL_TEMPLATE,
        trigger_type=TRIGGER_TEXT_SHORTCUT, trigger_value=";sig",
        output_mode=OUTPUT_CLIPBOARD_PASTE,
    )
    manifest = export_macros_proof_pack([macro], registry, tmp_path / "macro-proof.json")
    assert manifest["includes_macro_body"] is True
    item = manifest["items"][0]
    assert item["macro_id"] == "m1"
    assert item["safe_id"] == "macro-safe"
    assert item["smart_type"] == SMART_EMAIL_TEMPLATE
    assert item["trigger_type"] == TRIGGER_TEXT_SHORTCUT
    assert item["includes_macro_body"] is True


def test_broken_filter_empty_body(macro_env):
    settings, store, registry, _tmp = macro_env
    store.save_all([Macro(id="b", name="broken", body="", trigger_type=TRIGGER_MENU_ONLY)])
    loaded = store.load_all()
    broken = apply_macro_filter(loaded, MACRO_FILTER_BROKEN, registry=registry, settings=settings)
    assert len(broken) == 1


def test_all_macros_filter(macro_env):
    settings, store, registry, _tmp = macro_env
    store.save_all([Macro(id="1", name="a", body="x"), Macro(id="2", name="b", body="y")])
    loaded = store.load_all()
    assert len(apply_macro_filter(loaded, MACRO_FILTER_ALL, registry=registry, settings=settings)) == 2
