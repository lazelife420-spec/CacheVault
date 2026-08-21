"""FilterNav's "Sidebar Options" overflow control must not crash.

Found by the post-canonical dirty-tree salvage audit (Gate E1): a stranded
uncommitted fix from before the Gate 5F canonicalization contained the
resolution to a defect that was, at the time this test was written, live in
canonical ``master`` -- ``FilterNav._show_sidebar_menu`` calls ``tk.Menu(...)``
while ``tk`` is not bound anywhere in its own scope, its class, or the
module. ``tkinter`` is used elsewhere in this file, but only via a *local*
``import tkinter as tk`` inside ``SidebarRow.__init__`` -- a different class,
whose local import does not extend to ``FilterNav``'s methods. This is not a
static-analysis-only concern: the crash was reproduced live, via the real
button's own command callback, against unmodified canonical code, and is
recorded verbatim by ``pytest.raises`` below rather than merely inferred from
reading the source.

The overflow button ("Sidebar Options" tooltip) is a real, always-visible
control in ``FilterNav.__init__`` -- clicking it in the shipped app hits
this exact path.
"""

from __future__ import annotations

from unittest import mock

import pytest

from cache_vault.core.settings import Settings
from cache_vault.ui.filters import FilterNav
from tests.tk_support import probe_tk_ui

OK, REASON = probe_tk_ui()


def _make_filter_nav(tk_root):
    return FilterNav(tk_root, on_select=lambda _key: None, settings=Settings())


@pytest.mark.skipif(not OK, reason=REASON)
def test_show_sidebar_menu_constructs_the_menu_without_crashing(tk_root):
    """Direct call to the method the overflow button invokes.

    ``popup_menu`` (which posts the real OS-level menu via ``tk_popup``) is
    patched -- consistent with how the rest of this suite exercises menu
    construction (see test_sidebar_context.py) -- so this test proves menu
    *construction* succeeds without depending on platform popup behavior.
    The crash under audit happens at ``tk.Menu(self, tearoff=0)``, strictly
    before ``popup_menu`` is ever reached, so patching it does not hide the
    defect this test exists to catch.
    """
    nav = _make_filter_nav(tk_root)
    nav.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    with mock.patch("cache_vault.ui.clip_context.popup_menu") as popup:
        nav._show_sidebar_menu()

    popup.assert_called_once()
    nav.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_sidebar_options_button_invoke_reaches_the_real_path_without_crashing(tk_root):
    """Runtime UI check: trigger the actual overflow button, not the method
    directly, proving the real click path (button -> command callback ->
    _show_sidebar_menu -> tk.Menu(...)) survives end to end."""
    nav = _make_filter_nav(tk_root)
    nav.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    assert nav._overflow_btn.cget("command") == nav._show_sidebar_menu, (
        "the overflow button must be wired directly to _show_sidebar_menu "
        "for this to be a faithful reproduction of the real UI path"
    )

    with mock.patch("cache_vault.ui.clip_context.popup_menu") as popup:
        nav._overflow_btn.invoke()

    popup.assert_called_once()
    nav.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_canonical_defect_reproduces_as_a_nameerror_when_the_fix_is_absent(tk_root, monkeypatch):
    """Pin the exact failure mode the historical fix resolves.

    This does not rely on the module's current import state -- it removes
    ``tk`` from ``filters`` module globals for the duration of the call (via
    monkeypatch, auto-restored) to prove the specific defect this gate fixes
    is ``NameError: name 'tk' is not defined`` at ``tk.Menu(...)``, not some
    other failure a passing test could be masking.
    """
    from cache_vault.ui import filters as filters_mod

    nav = _make_filter_nav(tk_root)
    nav.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    monkeypatch.delattr(filters_mod, "tk", raising=False)
    with pytest.raises(NameError, match="tk"):
        nav._show_sidebar_menu()

    nav.destroy()
