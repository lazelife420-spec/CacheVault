"""BUG-5 regression: stop() must post WM_QUIT to release the hook thread.

These tests never install a real low-level keyboard hook. They drive a fake
``_user32`` so the stop/message-post contract is verified without touching
Win32 or risking a hung message loop.
"""

from cache_vault.core import macro_shortcut_listener as msl
from cache_vault.core.macro_shortcut_listener import WM_QUIT, TextShortcutListener


class _FakeUser32:
    def __init__(self):
        self.unhooked = []
        self.posted = []

    def UnhookWindowsHookEx(self, hook_id):
        self.unhooked.append(hook_id)
        return 1

    def PostThreadMessageW(self, thread_id, msg, wparam, lparam):
        self.posted.append((thread_id, msg, wparam, lparam))
        return 1


def _listener():
    return TextShortcutListener(on_match=lambda *a, **k: None)


def test_stop_posts_wm_quit_to_hook_thread(monkeypatch):
    fake = _FakeUser32()
    monkeypatch.setattr(msl, "_user32", fake)

    listener = _listener()
    listener._hook_id = 4242
    listener._thread_id = 9001

    listener.stop()

    assert fake.unhooked == [4242]
    assert fake.posted == [(9001, WM_QUIT, 0, 0)]
    assert listener._hook_id is None
    assert listener._thread_id is None


def test_stop_is_idempotent_and_safe_without_hook(monkeypatch):
    fake = _FakeUser32()
    monkeypatch.setattr(msl, "_user32", fake)

    listener = _listener()
    # Never started: no hook, no thread id. stop() must be a no-op, not crash.
    listener.stop()

    assert fake.unhooked == []
    assert fake.posted == []


def test_stop_joins_worker_thread(monkeypatch):
    import threading

    fake = _FakeUser32()
    monkeypatch.setattr(msl, "_user32", fake)

    # A thread that exits on its own; stop() should join it cleanly.
    stop_evt = threading.Event()
    worker = threading.Thread(target=stop_evt.wait, daemon=True)
    worker.start()
    stop_evt.set()

    listener = _listener()
    listener._hook_id = 1
    listener._thread_id = 123
    listener._thread = worker

    listener.stop()

    assert listener._thread is None
    assert not worker.is_alive()
