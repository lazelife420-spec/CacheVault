"""Every runtime-evaluated annotation in cache_vault.ui must resolve.

Found by the post-canonical dirty-tree salvage audit (Gate E3): several
functions/methods in shell.py, clip_context.py, and mobile_dialogs.py
reference type names (``Any``, ``Clip``, ``Path``) that are used bare in
annotations but never imported into the module's own namespace. Because
these modules all have ``from __future__ import annotations`` (PEP 563),
every annotation is stored as a lazy string and is never evaluated during
normal execution -- so the file imports fine and the app runs fine. But this
codebase does rely on real annotation resolution elsewhere:
``cache_vault/modules/settings_schema.py`` calls
``typing.get_type_hints(settings_cls)`` to validate its settings schema, so
``get_type_hints`` succeeding is not a hypothetical concern for this
project, just one these specific symbols currently fail.

"The file imports successfully" is not proof these annotations are correct
-- these tests call the actual resolution mechanism instead, exactly the
one this codebase already depends on for Settings.

Scope note: an exhaustive get_type_hints() sweep (not just a grep-based
guess) found every failure in all three files traces to exactly three
missing names -- Any, Clip, Path -- and nothing else. clip_context.py's
open_home_card_menu (a separate, unrelated candidate: whether to promote a
function-local `from .filters import ...` to module scope) has zero
annotation dependency on any of this -- its own parameter/return
annotations (str, str | None, int, int, None) already resolve cleanly
today, confirmed here too, which is why that change is excluded from this
gate as import-organization-only, not a defect.
"""

from __future__ import annotations

import typing

import pytest


# --- shell.py ----------------------------------------------------------------

def test_on_clip_double_click_annotation_resolves():
    from cache_vault.ui.shell import CacheVaultApp
    hints = typing.get_type_hints(CacheVaultApp._on_clip_double_click)
    assert "clip" in hints


@pytest.mark.parametrize("method_name", [
    # A representative sample of the 27 _sidebar_*/report_*/dispatch_*
    # methods the exhaustive sweep found using a bare `Any` annotation --
    # not all 27, since they all share the identical root cause and a
    # single missing import fixes every one of them at once.
    "_dispatch_sidebar_command",
    "_sidebar_open",
    "_sidebar_refresh",
    "_sidebar_select_all_visible",
    "_report_clear_all_clips_result",
    "_report_permanent_delete_result",
])
def test_sidebar_command_methods_any_annotation_resolves(method_name):
    from cache_vault.ui.shell import CacheVaultApp
    method = getattr(CacheVaultApp, method_name)
    hints = typing.get_type_hints(method)
    assert "ctx" in hints or "results" in hints or hints  # any hint resolved at all


def test_shell_every_any_annotated_method_resolves():
    """The exhaustive check, not just the sample above: every method the
    original sweep found failing must now succeed."""
    import inspect
    from cache_vault.ui.shell import CacheVaultApp

    failed = []
    for name, member in inspect.getmembers(CacheVaultApp, predicate=inspect.isfunction):
        try:
            typing.get_type_hints(member)
        except Exception as exc:  # noqa: BLE001 - we want to report every failure
            failed.append((name, exc))
    assert failed == [], f"annotation(s) failed to resolve: {failed}"


# --- clip_context.py -----------------------------------------------------------

def test_add_single_item_clip_annotation_resolves():
    from cache_vault.ui import clip_context
    hints = typing.get_type_hints(clip_context._add_single_item)
    assert "clips" in hints


def test_find_receipt_file_path_annotation_resolves():
    from cache_vault.ui import clip_context
    hints = typing.get_type_hints(clip_context._find_receipt_file)
    assert "return" in hints


def test_open_home_card_menu_has_no_annotation_defect_either_way():
    """Confirms the NAV-import question is unrelated to annotation
    correctness: this function's own annotations already resolve today,
    regardless of whether open_home_card_menu's import is module-level or
    function-local -- the reason that change is out of this gate's scope."""
    from cache_vault.ui import clip_context
    hints = typing.get_type_hints(clip_context.open_home_card_menu)
    assert hints == {
        "label": str,
        "filter_key": str | None,
        "x_root": int,
        "y_root": int,
        "return": type(None),
    }


def test_clip_context_every_annotated_function_resolves():
    import inspect
    from cache_vault.ui import clip_context

    failed = []
    for name, member in inspect.getmembers(clip_context, predicate=inspect.isfunction):
        if member.__module__ != clip_context.__name__:
            continue
        try:
            typing.get_type_hints(member)
        except Exception as exc:  # noqa: BLE001
            failed.append((name, exc))
    assert failed == [], f"annotation(s) failed to resolve: {failed}"


# --- mobile_dialogs.py ---------------------------------------------------------

def test_pair_android_dialog_init_any_annotation_resolves():
    """create_pairing_offer: Callable[[], Any] | None -- Any appears inside
    a Callable[...] type expression, not as a bare `: Any` parameter
    annotation; a plain grep for `: Any\\b` misses this shape, which is
    exactly why this gate verifies with the real mechanism instead."""
    from cache_vault.ui.mobile_dialogs import PairAndroidDialog
    hints = typing.get_type_hints(PairAndroidDialog.__init__)
    assert "create_pairing_offer" in hints


def test_mobile_dialogs_every_annotated_function_resolves():
    import inspect
    from cache_vault.ui import mobile_dialogs

    failed = []
    for name, obj in inspect.getmembers(mobile_dialogs):
        if name.startswith("__"):
            continue
        if inspect.isfunction(obj) and getattr(obj, "__module__", None) == mobile_dialogs.__name__:
            try:
                typing.get_type_hints(obj)
            except Exception as exc:  # noqa: BLE001
                failed.append((name, exc))
        elif inspect.isclass(obj) and obj.__module__ == mobile_dialogs.__name__:
            for mname, m in inspect.getmembers(obj, predicate=inspect.isfunction):
                try:
                    typing.get_type_hints(m)
                except Exception as exc:  # noqa: BLE001
                    failed.append((f"{name}.{mname}", exc))
    assert failed == [], f"annotation(s) failed to resolve: {failed}"
