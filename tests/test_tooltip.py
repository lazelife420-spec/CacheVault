from __future__ import annotations

from cache_vault.ui import guide_copy
from cache_vault.ui.tooltip import TooltipManager


class FakeTip:
    def __init__(self, text: str):
        self.text = text
        self.destroyed = False
        self.destroy_calls = 0
        self.geometry_value = ""

    def destroy(self) -> None:
        self.destroy_calls += 1
        self.destroyed = True

    def winfo_exists(self) -> int:
        return 0 if self.destroyed else 1

    def winfo_width(self) -> int:
        return 180

    def winfo_height(self) -> int:
        return 42

    def geometry(self, value: str) -> None:
        self.geometry_value = value


class FakeWidget:
    def __init__(self, *, x: int = 100, y: int = 100):
        self.bindings = {}
        self.callbacks = {}
        self.cancelled = set()
        self.next_token = 0
        self.x = x
        self.y = y

    def after(self, _delay_ms: int, callback):
        self.next_token += 1
        token = f"after-{self.next_token}"
        self.callbacks[token] = callback
        return token

    def after_cancel(self, token) -> None:
        self.cancelled.add(token)

    def bind(self, sequence: str, func, add: str | None = None):
        self.bindings.setdefault(sequence, []).append((func, add))

    def emit(self, sequence: str) -> None:
        for func, _add in self.bindings.get(sequence, []):
            func(None)

    def run_after(self, token: str) -> None:
        if token not in self.cancelled:
            self.callbacks[token]()

    def winfo_exists(self) -> int:
        return 1

    def winfo_rootx(self) -> int:
        return self.x

    def winfo_rooty(self) -> int:
        return self.y

    def winfo_width(self) -> int:
        return 80

    def winfo_height(self) -> int:
        return 24

    def winfo_screenwidth(self) -> int:
        return 800

    def winfo_screenheight(self) -> int:
        return 600


class HelperTooltipManager(TooltipManager):
    def __init__(self):
        super().__init__(delay_ms=750)
        self.created: list[FakeTip] = []

    def _create_tip(self, _widget, text: str):
        tip = FakeTip(text)
        self.created.append(tip)
        return tip


def test_delayed_show_cancels_on_leave():
    manager = HelperTooltipManager()
    widget = FakeWidget()

    manager.bind(widget, "Quiet help")
    widget.emit("<Enter>")
    token = manager.state.pending_token
    widget.emit("<Leave>")

    assert token in widget.cancelled
    assert manager.state.active_tip is None
    widget.run_after(token)
    assert manager.created == []


def test_only_one_tooltip_exists():
    manager = HelperTooltipManager()
    first = FakeWidget()
    second = FakeWidget()

    manager.show(first, "First")
    first_tip = manager.state.active_tip
    manager.show(second, "Second")

    assert first_tip.destroyed is True
    assert manager.state.active_tip.text == "Second"
    assert len([tip for tip in manager.created if not tip.destroyed]) == 1


def test_hide_on_click_and_right_click():
    manager = HelperTooltipManager()
    widget = FakeWidget()
    manager.bind(widget, "Click hides")

    manager.show(widget, "Click hides")
    widget.emit("<Button-1>")
    assert manager.state.active_tip is None

    manager.show(widget, "Click hides")
    widget.emit("<Button-3>")
    assert manager.state.active_tip is None


def test_hide_on_page_change():
    manager = HelperTooltipManager()
    widget = FakeWidget()

    manager.show(widget, "Screen help")
    manager.hide()

    assert manager.state.active_tip is None


def test_hide_when_vault_lock_activates():
    manager = HelperTooltipManager()
    widget = FakeWidget()

    manager.show(widget, "Allowed unlocked help")
    manager.set_locked(True)

    assert manager.state.locked is True
    assert manager.state.active_tip is None


def test_no_tooltip_content_leaks_while_locked():
    manager = HelperTooltipManager()
    widget = FakeWidget()

    manager.set_locked(True)
    manager.schedule(widget, "secret clip body hash device metadata")

    assert manager.state.pending_token is None
    assert manager.state.active_tip is None
    assert manager.created == []


def test_context_menu_suppresses_pending_tooltip():
    manager = HelperTooltipManager()
    widget = FakeWidget()

    manager.before_menu_open()
    manager.schedule(widget, "Menu should suppress this")

    assert manager.state.pending_token is None
    assert manager.state.active_tip is None
    assert manager.created == []
    manager.after_menu_close()


def test_tooltip_text_registry_contains_no_forbidden_claims():
    assert guide_copy.guide_copy_has_no_forbidden_claims()


def test_hide_active_skips_destroy_when_already_gone():
    """Regression test for a native tk86t.dll access-violation crash.

    If the tip's parent hierarchy is torn down elsewhere (e.g. a sidebar
    rebuild during navigation), the Toplevel can already be Tcl-destroyed
    before a later <Configure>/<FocusOut>/<Unmap>-triggered hide runs.
    Destroying it again must not happen.
    """
    manager = HelperTooltipManager()
    widget = FakeWidget()

    manager.show(widget, "Fragile tip")
    tip = manager.state.active_tip
    tip.destroy()
    assert tip.destroy_calls == 1

    manager.hide_active()

    assert tip.destroy_calls == 1


def test_hide_active_reentrant_call_does_not_double_destroy():
    """A destroy() call that reenters hide_tooltip() must not race itself."""
    manager = HelperTooltipManager()
    widget = FakeWidget()

    manager.show(widget, "Reentrant tip")
    tip = manager.state.active_tip

    original_destroy = tip.destroy

    def reentrant_destroy() -> None:
        original_destroy()
        # Simulate a nested hide triggered while this destroy is unwinding.
        manager.hide_active()

    tip.destroy = reentrant_destroy
    manager.hide_active()

    assert tip.destroy_calls == 1
