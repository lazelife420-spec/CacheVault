from __future__ import annotations

import json

import pytest

from cache_vault.core import command_center as cc
from cache_vault.core.command_center import (
    ACTION_LOCK_VAULT,
    ACTION_OPEN_QUICK_PASTE,
    ACTION_RUN_MACRO,
    ACTION_SAVE_CLIPBOARD_TO_SAFE,
    ACTION_TOGGLE_CAPTURE,
    CommandActionDispatcher,
    CommandRunLog,
    HotkeyAction,
    HotkeyActionStore,
    REG_ACTIVE,
    REG_CONFLICT,
    REG_DISABLED,
    REG_FAILED,
    REG_INVALID,
    REG_RESERVED,
    REG_UNAVAILABLE,
    RESULT_BLOCKED,
    RESULT_FAILED,
    RESULT_OK,
    compute_status_rows,
    diagnose_action_hotkey,
    registration_status_for,
)


@pytest.fixture
def store(tmp_path):
    return HotkeyActionStore(tmp_path / "command_center.json")


@pytest.fixture
def runlog(tmp_path):
    return CommandRunLog(tmp_path / "command_runlog.json")


# --- store -------------------------------------------------------------------
def test_store_roundtrip_and_upsert(store):
    assert store.load_all() == []
    a = HotkeyAction(name="Quick Paste", hotkey="ctrl+alt+v",
                     action_type=ACTION_OPEN_QUICK_PASTE)
    store.upsert(a)
    loaded = store.load_all()
    assert len(loaded) == 1
    assert loaded[0].name == "Quick Paste"
    assert store.get(a.id) is not None

    a.name = "Renamed"
    store.upsert(a)
    assert len(store.load_all()) == 1
    assert store.get(a.id).name == "Renamed"

    assert store.delete(a.id) is True
    assert store.load_all() == []
    assert store.delete("missing") is False


def test_store_ignores_unknown_fields(store, tmp_path):
    (tmp_path / "command_center.json").write_text(
        json.dumps({"version": 1, "actions": [
            {"id": "x", "name": "n", "action_type": ACTION_LOCK_VAULT, "bogus": 1},
        ]}),
        encoding="utf-8",
    )
    actions = store.load_all()
    assert len(actions) == 1
    assert actions[0].id == "x"


# --- conflict / reserved detection ------------------------------------------
def test_diagnose_invalid_specs():
    kind, _ = diagnose_action_hotkey("", win32_available=True)
    assert kind == REG_INVALID
    kind, _ = diagnose_action_hotkey("ctrl+alt", win32_available=True)  # no main key
    assert kind == REG_INVALID


def test_diagnose_conflict_with_other_action():
    other = HotkeyAction(id="a", name="Open Vault", hotkey="ctrl+alt+v",
                         action_type=ACTION_OPEN_QUICK_PASTE)
    kind, msg = diagnose_action_hotkey(
        "ctrl+alt+v", self_id="b", other_actions=[other], win32_available=True,
    )
    assert kind == REG_CONFLICT
    assert "Open Vault" in msg


def test_diagnose_conflict_ignores_self():
    me = HotkeyAction(id="a", hotkey="ctrl+alt+v")
    kind, _ = diagnose_action_hotkey(
        "ctrl+alt+v", self_id="a", other_actions=[me], win32_available=True,
    )
    assert kind == "ok"


def test_diagnose_reserved_system_shortcut():
    kind, _ = diagnose_action_hotkey(
        "ctrl+shift+v", reserved_specs={"ctrl+shift+v"}, win32_available=True,
    )
    assert kind == REG_RESERVED


def test_diagnose_unavailable_without_win32():
    kind, _ = diagnose_action_hotkey("ctrl+alt+v", win32_available=False)
    assert kind == REG_UNAVAILABLE


# --- registration status -----------------------------------------------------
def test_registration_status_disabled():
    a = HotkeyAction(hotkey="ctrl+alt+v", enabled=False,
                     action_type=ACTION_OPEN_QUICK_PASTE)
    status, _ = registration_status_for(
        a, other_actions=[], reserved_specs=set(), win32_available=True,
    )
    assert status == REG_DISABLED


def test_registration_status_active_when_os_registered():
    a = HotkeyAction(hotkey="ctrl+alt+v", action_type=ACTION_OPEN_QUICK_PASTE)
    status, _ = registration_status_for(
        a, other_actions=[], reserved_specs=set(), win32_available=True,
        os_registered=True,
    )
    assert status == REG_ACTIVE


def test_registration_status_failed_reason_recorded():
    a = HotkeyAction(hotkey="ctrl+alt+v", action_type=ACTION_OPEN_QUICK_PASTE)
    status, message = registration_status_for(
        a, other_actions=[], reserved_specs=set(), win32_available=True,
        os_registered=False,
    )
    assert status == REG_FAILED
    assert message  # a human reason is stored


def test_registration_status_conflict_beats_os():
    other = HotkeyAction(id="o", name="Other", hotkey="ctrl+alt+v")
    a = HotkeyAction(id="a", hotkey="ctrl+alt+v", action_type=ACTION_OPEN_QUICK_PASTE)
    status, _ = registration_status_for(
        a, other_actions=[other], reserved_specs=set(), win32_available=True,
        os_registered=True,
    )
    assert status == REG_CONFLICT


# --- dispatcher --------------------------------------------------------------
def _dispatcher(store, runlog, handlers, **kw):
    return CommandActionDispatcher(store, runlog, handlers, app_version="9.9", **kw)


def test_dispatch_runs_handler_and_logs(store, runlog):
    calls = []
    a = store.upsert(HotkeyAction(name="QP", hotkey="ctrl+alt+v",
                                  action_type=ACTION_OPEN_QUICK_PASTE))
    d = _dispatcher(store, runlog, {ACTION_OPEN_QUICK_PASTE: lambda act: calls.append(act)})
    res = d.run(a, trigger_type="hotkey", trigger_value="ctrl+alt+v")
    assert res.ok and res.result == RESULT_OK
    assert len(calls) == 1
    log = runlog.recent()
    assert len(log) == 1
    assert log[0].result == RESULT_OK
    assert log[0].app_version == "9.9"
    assert log[0].trigger_value == "Ctrl+Alt+V"
    # run stats updated
    assert store.get(a.id).run_count == 1
    assert store.get(a.id).last_run_at is not None


def test_dispatch_disabled_action_does_not_run(store, runlog):
    calls = []
    a = store.upsert(HotkeyAction(name="QP", hotkey="ctrl+alt+v", enabled=False,
                                  action_type=ACTION_OPEN_QUICK_PASTE))
    d = _dispatcher(store, runlog, {ACTION_OPEN_QUICK_PASTE: lambda act: calls.append(act)})
    res = d.run(a)
    assert not res.ok and res.result == RESULT_BLOCKED
    assert calls == []
    assert runlog.recent() == []  # disabled runs are not logged as noise


def test_dispatch_pause_resume_capture(store, runlog):
    state = {"paused": False}

    def toggle(_a):
        state["paused"] = not state["paused"]
        return {"message": "Capture: Paused" if state["paused"] else "Capture: On"}

    a = store.upsert(HotkeyAction(name="Pause", hotkey="ctrl+alt+d",
                                  action_type=ACTION_TOGGLE_CAPTURE))
    d = _dispatcher(store, runlog, {ACTION_TOGGLE_CAPTURE: toggle})
    res = d.run(a)
    assert res.ok and state["paused"] is True
    assert "Paused" in res.message


def test_dispatch_failure_records_reason(store, runlog):
    def boom(_a):
        raise RuntimeError("clipboard empty")

    a = store.upsert(HotkeyAction(name="Save", hotkey="ctrl+alt+s",
                                  action_type=ACTION_SAVE_CLIPBOARD_TO_SAFE,
                                  target="default"))
    d = _dispatcher(store, runlog, {ACTION_SAVE_CLIPBOARD_TO_SAFE: boom})
    res = d.run(a)
    assert not res.ok and res.result == RESULT_FAILED
    assert "clipboard empty" in res.error
    assert runlog.recent()[0].result == RESULT_FAILED
    assert store.get(a.id).last_run_failed is True
    assert store.get(a.id).run_count == 0


def test_dispatch_blocked_when_locked(store, runlog):
    calls = []
    a = store.upsert(HotkeyAction(name="QP", hotkey="ctrl+alt+v",
                                  action_type=ACTION_OPEN_QUICK_PASTE))
    d = _dispatcher(store, runlog, {ACTION_OPEN_QUICK_PASTE: lambda act: calls.append(act)},
                    is_locked=lambda: True)
    res = d.run(a)
    assert not res.ok and res.result == RESULT_BLOCKED
    assert calls == []
    assert runlog.recent()[0].error == "vault_locked"


def test_lock_vault_allowed_when_locked(store, runlog):
    calls = []
    a = store.upsert(HotkeyAction(name="Lock", hotkey="ctrl+alt+l",
                                  action_type=ACTION_LOCK_VAULT))
    d = _dispatcher(store, runlog, {ACTION_LOCK_VAULT: lambda act: calls.append(act)},
                    is_locked=lambda: True)
    res = d.run(a)
    assert res.ok and len(calls) == 1


def test_dispatch_unimplemented_action_is_not_faked(store, runlog):
    a = store.upsert(HotkeyAction(name="Export", hotkey="ctrl+alt+e",
                                  action_type="export_selected"))
    d = _dispatcher(store, runlog, {})
    res = d.run(a)
    assert not res.ok and res.result == RESULT_FAILED
    assert "not available" in res.error.lower()


def test_dry_run_does_not_invoke_handler_or_bump_count(store, runlog):
    calls = []
    a = store.upsert(HotkeyAction(name="QP", hotkey="ctrl+alt+v",
                                  action_type=ACTION_OPEN_QUICK_PASTE))
    d = _dispatcher(store, runlog, {ACTION_OPEN_QUICK_PASTE: lambda act: calls.append(act)})
    res = d.run(a, dry_run=True)
    assert res.ok and calls == []
    assert store.get(a.id).run_count == 0
    assert runlog.recent()[0].dry_run is True


def test_destructive_action_requires_confirmation(store, runlog):
    # Simulate a destructive action by patching its spec for the test.
    ran = []
    a = store.upsert(HotkeyAction(name="Danger", hotkey="ctrl+alt+k",
                                  action_type=ACTION_LOCK_VAULT))
    spec = cc.ACTION_SPECS[ACTION_LOCK_VAULT]
    cc.ACTION_SPECS[ACTION_LOCK_VAULT] = cc.ActionSpec(
        spec.key, spec.label, implemented=True, needs_confirmation=True,
    )
    try:
        d = _dispatcher(
            store, runlog, {ACTION_LOCK_VAULT: lambda act: ran.append(act)},
            confirm=lambda act: False,
        )
        res = d.run(a)
        assert not res.ok and res.result == RESULT_BLOCKED
        assert ran == []
        assert runlog.recent()[0].error == "cancelled"
    finally:
        cc.ACTION_SPECS[ACTION_LOCK_VAULT] = spec


def test_destructive_action_runs_when_confirmed(store, runlog):
    ran = []
    a = store.upsert(HotkeyAction(name="Danger", hotkey="ctrl+alt+k",
                                  action_type=ACTION_LOCK_VAULT))
    spec = cc.ACTION_SPECS[ACTION_LOCK_VAULT]
    cc.ACTION_SPECS[ACTION_LOCK_VAULT] = cc.ActionSpec(
        spec.key, spec.label, implemented=True, needs_confirmation=True,
    )
    try:
        d = _dispatcher(
            store, runlog, {ACTION_LOCK_VAULT: lambda act: ran.append(act)},
            confirm=lambda act: True,
        )
        res = d.run(a)
        assert res.ok and res.result == RESULT_OK
        assert len(ran) == 1
    finally:
        cc.ACTION_SPECS[ACTION_LOCK_VAULT] = spec


def test_destructive_action_fails_closed_without_confirm_handler(store, runlog):
    # No confirm callback wired at all: a destructive/needs-confirmation action
    # must never run unguarded, regardless of what the (missing) confirm would say.
    ran = []
    a = store.upsert(HotkeyAction(name="Danger", hotkey="ctrl+alt+k",
                                  action_type=ACTION_LOCK_VAULT))
    spec = cc.ACTION_SPECS[ACTION_LOCK_VAULT]
    cc.ACTION_SPECS[ACTION_LOCK_VAULT] = cc.ActionSpec(
        spec.key, spec.label, implemented=True, needs_confirmation=True,
    )
    try:
        d = _dispatcher(store, runlog, {ACTION_LOCK_VAULT: lambda act: ran.append(act)})
        res = d.run(a)
        assert not res.ok and res.result == RESULT_FAILED
        assert ran == []
        assert runlog.recent()[0].error == "confirmation_unavailable"
    finally:
        cc.ACTION_SPECS[ACTION_LOCK_VAULT] = spec


def test_non_destructive_action_runs_without_confirm_handler(store, runlog):
    calls = []
    a = store.upsert(HotkeyAction(name="QP", hotkey="ctrl+alt+v",
                                  action_type=ACTION_OPEN_QUICK_PASTE))
    d = _dispatcher(store, runlog, {ACTION_OPEN_QUICK_PASTE: lambda act: calls.append(act)})
    res = d.run(a)
    assert res.ok and len(calls) == 1


def test_run_macro_target_passed_to_handler(store, runlog):
    seen = {}
    a = store.upsert(HotkeyAction(name="Sig", hotkey="ctrl+alt+m",
                                  action_type=ACTION_RUN_MACRO, target="macro-123"))

    def run_macro(act):
        seen["target"] = act.target
        return {"clip_ids": ["c1"], "safe_target": "sig-safe"}

    d = _dispatcher(store, runlog, {ACTION_RUN_MACRO: run_macro})
    res = d.run(a)
    assert res.ok and seen["target"] == "macro-123"
    entry = runlog.recent()[0]
    assert entry.clip_ids == ["c1"]
    assert entry.safe_target == "sig-safe"


# --- run log -----------------------------------------------------------------
def test_runlog_caps_entries(tmp_path):
    log = CommandRunLog(tmp_path / "rl.json", cap=3)
    for i in range(5):
        log.append(cc.RunLogEntry(command_name=f"c{i}"))
    entries = log.recent(100)
    assert len(entries) == 3


# --- demo fixture ------------------------------------------------------------
def test_demo_actions_have_no_clipboard_content():
    actions = cc.demo_actions()
    assert actions
    # Demo data may only contain action definitions, never clip bodies/previews.
    forbidden = {"content", "body", "preview", "secret", "clipboard"}
    for a in actions:
        keys = set(a.to_dict().keys())
        assert keys.isdisjoint(forbidden)


def test_seed_demo_actions_writes_store(store):
    seeded = cc.seed_demo_actions(store)
    assert seeded
    assert len(store.load_all()) == len(seeded)


# --- registration state is runtime-only (not persisted) ----------------------
def test_registration_state_not_persisted(store, tmp_path):
    a = HotkeyAction(name="QP", hotkey="ctrl+alt+v",
                     action_type=ACTION_OPEN_QUICK_PASTE)
    a.registration_status = REG_ACTIVE
    a.registration_error = "Active \u00b7 Ctrl+Alt+V"
    store.upsert(a)

    raw = json.loads((tmp_path / "command_center.json").read_text(encoding="utf-8"))
    keys = set(raw["actions"][0].keys())
    assert "registration_status" not in keys
    assert "registration_error" not in keys
    # to_dict drops them too, so no display strings ever reach disk.
    assert "registration_status" not in a.to_dict()
    assert "registration_error" not in a.to_dict()
    # Reloading yields the in-memory default, never the persisted display string.
    assert store.get(a.id).registration_error == ""


def test_from_dict_roundtrip_preserves_identity_without_throwaway():
    a = HotkeyAction(name="x", hotkey="ctrl+alt+v",
                     action_type=ACTION_OPEN_QUICK_PASTE)
    b = HotkeyAction.from_dict(a.to_dict())
    assert b.id == a.id  # not regenerated by a throwaway instance
    assert b.created_at == a.created_at
    assert b.updated_at == a.updated_at
    assert b.name == a.name and b.hotkey == a.hotkey


def test_runlog_entry_from_dict_roundtrip():
    e = cc.RunLogEntry(command_name="c", action_type=ACTION_LOCK_VAULT,
                       clip_ids=["a", "b"])
    e2 = cc.RunLogEntry.from_dict(e.to_dict())
    assert e2.id == e.id
    assert e2.command_name == "c"
    assert e2.clip_ids == ["a", "b"]


# --- shared status helper ----------------------------------------------------
def test_compute_status_rows_covers_states():
    active = HotkeyAction(id="a", name="A", hotkey="ctrl+alt+v",
                          action_type=ACTION_OPEN_QUICK_PASTE)
    disabled = HotkeyAction(id="b", name="B", hotkey="ctrl+alt+d", enabled=False,
                            action_type=ACTION_OPEN_QUICK_PASTE)
    reserved = HotkeyAction(id="c", name="C", hotkey="ctrl+shift+v",
                            action_type=ACTION_OPEN_QUICK_PASTE)
    failed = HotkeyAction(id="d", name="D", hotkey="ctrl+alt+f",
                          action_type=ACTION_OPEN_QUICK_PASTE)
    rows = compute_status_rows(
        [active, disabled, reserved, failed],
        reserved_specs={"ctrl+shift+v"},
        win32_available=True,
        registered_ids={500},               # only 'active' accepted by the OS
        hotkey_id_by_action={"a": 500, "d": 501},  # 'd' mapped but not registered
    )
    by_id = {r.action.id: r.status for r in rows}
    assert by_id["a"] == REG_ACTIVE
    assert by_id["b"] == REG_DISABLED
    assert by_id["c"] == REG_RESERVED
    assert by_id["d"] == REG_FAILED


def test_compute_status_rows_unavailable_without_win32():
    a = HotkeyAction(id="a", hotkey="ctrl+alt+v",
                     action_type=ACTION_OPEN_QUICK_PASTE)
    rows = compute_status_rows([a], reserved_specs=set(), win32_available=False)
    assert rows[0].status == REG_UNAVAILABLE


def test_duplicate_hotkey_marks_both_conflict():
    a = HotkeyAction(id="a", name="A", hotkey="ctrl+alt+v",
                     action_type=ACTION_OPEN_QUICK_PASTE)
    b = HotkeyAction(id="b", name="B", hotkey="ctrl+alt+v",
                     action_type=ACTION_LOCK_VAULT)
    rows = compute_status_rows(
        [a, b], reserved_specs=set(), win32_available=True,
        registered_ids=set(), hotkey_id_by_action={},
    )
    statuses = {r.action.id: r.status for r in rows}
    assert statuses["a"] == REG_CONFLICT
    assert statuses["b"] == REG_CONFLICT
