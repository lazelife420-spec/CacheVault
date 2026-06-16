from cache_vault.core import pathutil


def test_is_local_path_drive_and_unc():
    assert pathutil.is_local_path(r"C:\Users\KickA\Desktop\notes.txt")
    assert pathutil.is_local_path(r"D:\folder")
    assert pathutil.is_local_path(r"\\server\share\file.log")
    assert pathutil.is_local_path('"C:\\Program Files\\App\\app.exe"')  # quoted


def test_is_local_path_rejects_urls_and_text():
    assert not pathutil.is_local_path("https://example.com/file.txt")
    assert not pathutil.is_local_path("file:///C:/x")
    assert not pathutil.is_local_path("just some copied sentence")
    assert not pathutil.is_local_path("git status")
    assert not pathutil.is_local_path("")


def test_target_and_parent_exist(tmp_path):
    f = tmp_path / "sub" / "f.txt"
    f.parent.mkdir()
    f.write_text("x", encoding="utf-8")
    assert pathutil.target_exists(str(f))
    assert pathutil.parent_exists(str(f))

    missing = tmp_path / "sub" / "gone.txt"
    assert not pathutil.target_exists(str(missing))
    assert pathutil.parent_exists(str(missing))  # parent dir still there

    missing_parent = tmp_path / "nope" / "gone.txt"
    assert not pathutil.target_exists(str(missing_parent))
    assert not pathutil.parent_exists(str(missing_parent))


def test_open_and_reveal_refuse_non_paths():
    assert pathutil.open_path("https://example.com") is False
    assert pathutil.open_path("plain text") is False
    assert pathutil.reveal_in_explorer("https://example.com") is False
