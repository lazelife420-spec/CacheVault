import time
from unittest.mock import Mock
import pytest
import customtkinter as ctk

from cache_vault.core.multi_link import MultiLinkPayload
from cache_vault.ui.clip_workflows import MultiLinkPasteDialog, EditClipTextDialog

def test_multi_link_dialog_callbacks(tk_root):
    payload = MultiLinkPayload(
        raw_text="https://a.test\nhttps://b.test",
        urls=("https://a.test", "https://b.test")
    )
    on_separate = Mock()
    on_text_clip = Mock()
    on_copy_list = Mock()
    on_batch = Mock()

    # Test separate callback
    dialog = MultiLinkPasteDialog(
        tk_root,
        payload=payload,
        on_separate=on_separate,
        on_text_clip=on_text_clip,
        on_copy_list=on_copy_list,
        on_batch=on_batch
    )
    dialog._run(on_separate)
    assert on_separate.called

    # Test text clip callback
    dialog = MultiLinkPasteDialog(
        tk_root,
        payload=payload,
        on_separate=on_separate,
        on_text_clip=on_text_clip,
        on_copy_list=on_copy_list,
        on_batch=on_batch
    )
    dialog._run(on_text_clip)
    assert on_text_clip.called

    # Test copy list callback
    dialog = MultiLinkPasteDialog(
        tk_root,
        payload=payload,
        on_separate=on_separate,
        on_text_clip=on_text_clip,
        on_copy_list=on_copy_list,
        on_batch=on_batch
    )
    dialog._run(on_copy_list)
    assert on_copy_list.called

    # Test batch callback
    dialog = MultiLinkPasteDialog(
        tk_root,
        payload=payload,
        on_separate=on_separate,
        on_text_clip=on_text_clip,
        on_copy_list=on_copy_list,
        on_batch=on_batch
    )
    dialog._run(on_batch)
    assert on_batch.called

def test_edit_clip_text_dialog(tk_root):
    on_save = Mock()
    dialog = EditClipTextDialog(
        tk_root,
        title="Test Edit",
        initial_text="Hello World",
        on_save=on_save
    )
    dialog._save()
    tk_root.update_idletasks()
    assert on_save.call_count == 1
    assert on_save.call_args[0][0] == "Hello World"
    # destroy() withdraws immediately but defers actual teardown ~50ms so
    # CustomTkinter's own pending focus-restore callback (Windows
    # dark-titlebar workaround) doesn't race a torn-down textbox -- so the
    # window is hidden right away but winfo_exists() only goes false once
    # that deferred finalize runs.
    assert dialog.winfo_viewable() == 0
    deadline = time.time() + 1.0
    while time.time() < deadline and dialog.winfo_exists():
        tk_root.update()
        time.sleep(0.01)
    assert not dialog.winfo_exists()


def test_edit_clip_text_dialog_cancel_creates_nothing(tk_root):
    on_save = Mock()
    dialog = EditClipTextDialog(
        tk_root,
        title="Test Edit",
        initial_text="Unsaved change",
        on_save=on_save,
    )
    dialog.destroy()
    tk_root.update_idletasks()
    on_save.assert_not_called()


def test_edit_clip_text_dialog_save_is_single_shot(tk_root):
    on_save = Mock()
    dialog = EditClipTextDialog(
        tk_root,
        title="Duplicate as Editable Clip",
        initial_text="One copy only",
        on_save=on_save,
    )
    destroy = Mock()
    dialog.destroy = destroy

    dialog._save()
    dialog._save()

    on_save.assert_called_once_with("One copy only")
    destroy.assert_called_once()
    ctk.CTkToplevel.destroy(dialog)
