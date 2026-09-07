from qabank.security import check_rate_limit, token_matches


def test_token_requires_nonempty_exact_match():
    assert token_matches("secret", "secret")
    assert not token_matches("secret", "wrong")
    assert not token_matches("", "")


def test_rate_limit_recovers_after_window():
    allowed, timestamps, retry_after = check_rate_limit(
        [90.0, 95.0], max_requests=2, window_seconds=20, now=100.0
    )
    assert not allowed
    assert retry_after == 11

    allowed, timestamps, retry_after = check_rate_limit(
        timestamps, max_requests=2, window_seconds=20, now=111.0
    )
    assert allowed
    assert retry_after == 0
