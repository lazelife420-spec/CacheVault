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
    assert on_save.called
    assert on_save.call_args[0][0] == "Hello World"
    dialog.destroy()
