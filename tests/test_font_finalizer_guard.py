"""The Tk font finalizer must never call Tk from a background thread.

tkinter.font.Font.__del__ deletes its Tcl font, runs on whichever thread the
garbage collector happens to be on, and swallows every exception -- so calling
it off the main thread does not fail loudly, it blocks on the Tcl interpreter.
A clip render orphans well over a thousand fonts, so a GC pass on the refresh
worker thread can park that worker inside Tk and hang the refresh.
"""

from __future__ import annotations

import threading
import unittest

import customtkinter as ctk

from cache_vault.ui import font_patch


class TestFontPatchCompatibility(unittest.TestCase):
    def test_compatibility_check_passes_on_this_python(self):
        font_patch.verify_font_patch_compatibility()

    def test_compatibility_check_names_missing_attributes(self):
        class Bare:
            pass

        with self.assertRaises(font_patch.FontPatchIncompatibleError) as ctx:
            font_patch.verify_font_patch_compatibility(Bare)
        self.assertIn("__del__", str(ctx.exception))


class TestFinalizerGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        font_patch._uninstall_for_tests()

    def tearDown(self):
        font_patch._uninstall_for_tests()

    def test_install_is_idempotent(self):
        font_patch.install_main_thread_font_finalizer_guard()
        first = __import__("tkinter.font", fromlist=["Font"]).Font.__del__
        font_patch.install_main_thread_font_finalizer_guard()
        second = __import__("tkinter.font", fromlist=["Font"]).Font.__del__
        self.assertIs(first, second, "guard must not wrap itself twice")

    def test_off_thread_finalizer_does_not_call_tk(self):
        """The regression, reproduced exactly: the font is built on the main
        thread during a render, then becomes unreachable while a background
        thread is running, so CPython runs __del__ on that thread. Without the
        guard this calls into the Tcl interpreter from there."""
        font_patch.install_main_thread_font_finalizer_guard()

        calls = []
        done = threading.Event()

        holder = [ctk.CTkFont(size=41, weight="bold")]
        # Route any Tcl call the finalizer makes into `calls` instead of Tk.
        holder[0]._call = lambda *a, **k: calls.append(a)
        holder[0].delete_font = True

        def worker():
            try:
                # Dropping the last reference here runs __del__ on this thread.
                holder.clear()
            finally:
                done.set()

        t = threading.Thread(target=worker, name="font-guard-worker")
        t.start()
        t.join(timeout=30)
        self.assertTrue(done.is_set(), "worker thread did not finish")
        self.assertFalse(t.is_alive(), "worker thread hung in the finalizer")

        self.assertEqual(
            calls, [],
            "font finalizer must not issue Tcl calls off the main thread",
        )
        self.assertGreaterEqual(
            font_patch.skipped_finalizer_count(), 1,
            "the skipped delete should be counted",
        )

    def test_off_thread_finalizer_reaches_tk_without_the_guard(self):
        """Proves the guard is what prevents it: the identical drop with the
        stock finalizer does issue a Tcl "font delete" from the worker."""
        calls = []
        done = threading.Event()

        holder = [ctk.CTkFont(size=43, weight="bold")]
        holder[0]._call = lambda *a, **k: calls.append(a)
        holder[0].delete_font = True

        def worker():
            try:
                holder.clear()
            finally:
                done.set()

        t = threading.Thread(target=worker, name="font-unguarded-worker")
        t.start()
        t.join(timeout=30)
        self.assertTrue(done.is_set())

        self.assertTrue(
            any(a[:2] == ("font", "delete") for a in calls),
            "without the guard the off-thread finalizer should reach Tk; "
            f"got {calls}",
        )

    def test_main_thread_finalizer_still_deletes(self):
        """The guard must not disable normal cleanup on the main thread."""
        font_patch.install_main_thread_font_finalizer_guard()

        calls = []
        f = ctk.CTkFont(size=42)
        f._call = lambda *a, **k: calls.append(a)
        f.delete_font = True
        del f

        self.assertTrue(
            any(a[:2] == ("font", "delete") for a in calls),
            f"main-thread finalizer must still delete the Tcl font; got {calls}",
        )

    def test_guard_is_active_after_shell_import_path(self):
        """app.py and shell.py both install the guard before building UI."""
        font_patch.install_main_thread_font_finalizer_guard()
        import tkinter.font as tkfont
        self.assertIsNot(
            tkfont.Font.__del__, font_patch._ORIGINAL_DEL,
            "Font.__del__ should be the guarded wrapper once installed",
        )


if __name__ == "__main__":
    unittest.main()
