from cache_vault.core import classify, models


def test_classify_url():
    r = classify.classify("https://github.com/anthropics/claude-code")
    assert r.classification == models.CLASS_LINK
    assert r.metadata["domain"] == "github.com"
    assert r.metadata["scheme"] == "https"


def test_classify_bare_domain():
    r = classify.classify("github.com/foo/bar")
    assert r.classification == models.CLASS_LINK


def test_command_beats_link():
    # A git clone is a command even though it contains a URL.
    r = classify.classify("git clone https://github.com/foo/bar.git")
    assert r.classification == models.CLASS_COMMAND
    assert r.metadata["shell"] == "Git"
    assert models.CLASS_LINK in r.tags  # url still tagged


def test_classify_powershell_command():
    r = classify.classify("winget install --id Git.Git -e")
    assert r.classification == models.CLASS_COMMAND
    assert r.metadata["shell"] == "PowerShell"


def test_classify_windows_path():
    r = classify.classify(r"C:\Users\KickA\Desktop\notes.txt")
    assert r.classification == models.CLASS_PATH
    assert r.metadata["file_name"] == "notes.txt"
    assert r.metadata["extension"] == "txt"


def test_classify_unc_path():
    r = classify.classify(r"\\server\share\folder\file.log")
    assert r.classification == models.CLASS_PATH


def test_classify_quoted_path():
    r = classify.classify('"C:\\Program Files\\App\\app.exe"')
    assert r.classification == models.CLASS_PATH


def test_classify_code():
    snippet = "def add(a, b):\n    return a + b\n"
    r = classify.classify(snippet)
    assert r.classification == models.CLASS_CODE
    assert r.metadata["probable_language"] == "python"


def test_classify_email():
    r = classify.classify("zerivonforge@gmail.com")
    assert r.classification == models.CLASS_EMAIL
    assert r.metadata["domain"] == "gmail.com"


def test_classify_phone():
    r = classify.classify("+1 (415) 555-2671")
    assert r.classification == models.CLASS_PHONE


def test_classify_plain():
    r = classify.classify("just some ordinary copied sentence here")
    assert r.classification == models.CLASS_PLAIN


def test_classify_empty():
    assert classify.classify("").classification == models.CLASS_PLAIN
    assert classify.classify(None).classification == models.CLASS_PLAIN
