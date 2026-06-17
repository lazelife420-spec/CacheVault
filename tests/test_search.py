from cache_vault.core import models, search


def _seed(vault):
    vault.settings.block_sensitive_auto_capture = False
    vault.capture("https://github.com/anthropics", source_app="chrome.exe")
    vault.capture("def hello():\n    return 'hi'", source_app="cursor.exe")
    vault.capture("git status", source_app="WindowsTerminal.exe")
    vault.capture("sk-abc123DEF456ghi789JKL0", source_app="cursor.exe")


def test_parse_type_token():
    q = search.parse("type:link github")
    assert q.type_filter == models.CLASS_LINK
    assert q.text == "github"


def test_parse_source_and_sensitive():
    q = search.parse("source:cursor sensitive:true")
    assert q.source == "cursor"
    assert q.sensitive is True
    assert q.text == ""


def test_parse_pinned():
    assert search.parse("pinned:true").pinned is True
    assert search.parse("pinned:false").pinned is False


def test_unknown_token_is_free_text():
    q = search.parse("foo:bar baz")
    assert q.text == "foo:bar baz"


def test_search_free_text(vault):
    _seed(vault)
    results = vault.list_clips(search.parse("github"))
    assert len(results) == 1
    assert "github" in results[0].content


def test_search_by_classification(vault):
    _seed(vault)
    results = vault.list_clips(search.parse("type:command"))
    assert len(results) == 1
    assert results[0].classification == models.CLASS_COMMAND


def test_search_by_source(vault):
    _seed(vault)
    results = vault.list_clips(search.parse("source:cursor"))
    sources = {c.source_app for c in results}
    assert sources == {"cursor.exe"}


def test_search_sensitive_only(vault):
    _seed(vault)
    results = vault.list_clips(search.parse("sensitive:true"))
    assert len(results) == 1
    assert results[0].is_sensitive


def test_search_all_includes_recently_removed(vault):
    from cache_vault.core.storage import FILTER_SEARCH_ALL

    clip = vault.capture("findme anywhere")
    vault.remove_from_history(clip.id)
    # Normal All Clips filter hides removed items.
    assert not vault.list_clips(search.parse("findme", "all"))
    # Global search includes Recently Removed.
    found = vault.list_clips(search.parse("findme", FILTER_SEARCH_ALL))
    assert len(found) == 1
    assert found[0].id == clip.id
