from cache_vault.core import multi_link
from cache_vault.ui.clip_workflows import compose_text


def test_detect_multi_link_payload_preserves_order_and_trim():
    payload = multi_link.detect_multi_link_payload(
        "\n https://a.test/file1.zip \nhttps://b.test/file2.zip  \n"
    )
    assert payload is not None
    assert payload.raw_text == "https://a.test/file1.zip \nhttps://b.test/file2.zip"
    assert payload.urls == (
        "https://a.test/file1.zip",
        "https://b.test/file2.zip",
    )


def test_detect_multi_link_payload_requires_two_urls():
    assert multi_link.detect_multi_link_payload("https://only.one") is None


def test_markdown_links_formats_each_url():
    payload = multi_link.MultiLinkPayload(
        raw_text="https://a.test/x\nhttps://b.test/y",
        urls=("https://a.test/x", "https://b.test/y"),
    )
    out = multi_link.markdown_links(payload)
    assert "[a.test](https://a.test/x)" in out
    assert "[b.test](https://b.test/y)" in out


def test_compose_text_modes():
    parts = ["first", "second"]
    assert compose_text(parts, "newline") == "first\nsecond"
    assert compose_text(parts, "blank_line") == "first\n\nsecond"
    assert compose_text(parts, "numbered") == "1. first\n2. second"
    assert compose_text(parts, "markdown_bullets") == "- first\n- second"
