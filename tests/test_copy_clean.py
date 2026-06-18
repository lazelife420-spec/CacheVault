from dataclasses import replace

from cache_vault.core import copy_clean, models
from cache_vault.core.models import Clip
from cache_vault.ui.receipt_ledger import ReceiptRow


def _clip(content: str, **kw) -> Clip:
    return Clip(
        content=content,
        preview=content,
        content_hash=models.content_hash(content),
        **kw,
    )


def test_copy_clean_plain_text_collapses_whitespace_without_mutating():
    clip = _clip(" hello   world \n\n second   line ")
    before = replace(clip)

    out = copy_clean.format_clip(clip, copy_clean.COPY_PLAIN_TEXT)

    assert out == "hello world\nsecond line"
    assert clip == before


def test_copy_clean_url_title_markdown_and_sms():
    clip = _clip(
        "https://example.com/a?x=1",
        title="Example Page",
        classification=models.CLASS_LINK,
    )

    assert copy_clean.format_clip(clip, copy_clean.COPY_TITLE_LINK) == (
        "Example Page\nhttps://example.com/a?x=1"
    )
    assert copy_clean.format_clip(clip, copy_clean.COPY_LINK_ONLY) == (
        "https://example.com/a?x=1"
    )
    assert copy_clean.format_clip(clip, copy_clean.COPY_MARKDOWN) == (
        "[Example Page](https://example.com/a?x=1)"
    )
    assert copy_clean.format_clip(clip, copy_clean.COPY_SMS) == (
        "Example Page: https://example.com/a?x=1"
    )


def test_copy_clean_email_format_uses_honest_fallback():
    clip = _clip("Body text only", classification=models.CLASS_PLAIN)

    out = copy_clean.format_clip(clip, copy_clean.COPY_EMAIL)

    assert out.startswith("Subject: Body text only")
    assert "Body text only" in out
    assert copy_clean.format_clip(clip, copy_clean.COPY_LINK_ONLY) is None


def test_copy_clean_phone_and_email_address_are_direct_known_fields():
    phone = _clip("Call me at (555) 123-4567", classification=models.CLASS_PHONE)
    email = _clip("me@example.com", classification=models.CLASS_EMAIL)

    assert copy_clean.format_clip(phone, copy_clean.COPY_PHONE) == "(555) 123-4567"
    assert copy_clean.format_clip(email, copy_clean.COPY_EMAIL_ADDRESS) == "me@example.com"


def test_copy_clean_file_path_only_for_path_clip(tmp_path):
    file_path = tmp_path / "receipt.txt"
    file_path.write_text("x", encoding="utf-8")
    clip = _clip(str(file_path), classification=models.CLASS_PATH)
    text = _clip(str(file_path), classification=models.CLASS_PLAIN)

    assert copy_clean.format_clip(clip, copy_clean.COPY_FILE_PATH) == str(file_path)
    assert copy_clean.format_clip(text, copy_clean.COPY_FILE_PATH) is None


def test_copy_clean_receipt_summary_is_metadata_only():
    row = ReceiptRow(
        receipt_id="r1",
        timestamp="2026-01-01T00:00:00+00:00",
        action_raw="captured",
        action_label="Captured Clip",
        item_label="Text clip",
        content_type="TEXT",
        result="Success",
        proof_hash="abc123",
        clip_id="clip-1",
        preview="secret body should not appear",
    )

    out = copy_clean.receipt_summary(row)

    assert "Captured Clip" in out
    assert "abc123" in out
    assert "secret body" not in out


def test_available_actions_are_honest_by_type():
    link = _clip("https://example.com", classification=models.CLASS_LINK)
    text = _clip("hello", classification=models.CLASS_PLAIN)
    mobile = _clip(
        "sent from phone",
        classification=models.CLASS_PLAIN,
        capture_mode=models.CAPTURE_MOBILE_SHARE,
    )

    assert copy_clean.COPY_MARKDOWN in copy_clean.available_clip_actions(link)
    assert copy_clean.COPY_MARKDOWN not in copy_clean.available_clip_actions(text)
    assert copy_clean.COPY_SOURCE_SUMMARY in copy_clean.available_clip_actions(mobile)
    assert copy_clean.COPY_ADDRESS not in copy_clean.available_clip_actions(text)


def test_copy_clean_no_forbidden_claims():
    assert copy_clean.no_forbidden_copy_clean_claims("Copy as Markdown")
    assert not copy_clean.no_forbidden_copy_clean_claims("cloud sync")
