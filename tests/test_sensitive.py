from cache_vault.core import sensitive


def test_detect_openai_style_key():
    r = sensitive.detect("sk-abc123DEF456ghi789JKL012mno345")
    assert r.is_sensitive


def test_detect_github_pat():
    r = sensitive.detect("ghp_" + "a" * 36)
    assert r.is_sensitive


def test_detect_jwt():
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123def456ghiJKL"
    assert sensitive.detect(token).is_sensitive


def test_detect_private_key():
    blob = "-----BEGIN RSA PRIVATE KEY-----\nMIIBureallylong\n-----END RSA PRIVATE KEY-----"
    assert sensitive.detect(blob).is_sensitive


def test_detect_assignment():
    assert sensitive.detect("password=hunter2longenough").is_sensitive
    assert sensitive.detect("API_KEY: 9f8e7d6c5b4a3210").is_sensitive


def test_detect_credit_card_luhn():
    # A valid Luhn number (Visa test number).
    assert sensitive.detect("4111 1111 1111 1111").is_sensitive
    # A 16-digit number that fails Luhn is not flagged as a card...
    assert not sensitive.detect("1234 5678 9012 3456").is_sensitive


def test_detect_otp():
    assert sensitive.detect("482913").is_sensitive


def test_detect_recovery_code():
    assert sensitive.detect("Your recovery code is: ABCD-EFGH").is_sensitive


def test_detect_high_entropy():
    assert sensitive.detect("Xa9Qm2Lp7Vz4Bt6Nc1Wd8Re3").is_sensitive


def test_plain_text_not_sensitive():
    assert not sensitive.detect("the quick brown fox jumps over").is_sensitive
    assert not sensitive.detect("https://example.com/page").is_sensitive


def test_masked_preview_hides_secret():
    secret = "sk-abc123DEF456ghi789"
    masked = sensitive.masked_preview(secret)
    assert "abc123" not in masked
    assert "•" in masked
    assert "sensitive" in masked.lower()


def test_compute_expiry_in_future():
    from datetime import datetime, timezone
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = sensitive.compute_expiry(10, base=base)
    assert out.startswith("2026-01-01T00:10:00")
