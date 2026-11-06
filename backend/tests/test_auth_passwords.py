from app.auth.passwords import hash_password, verify_password


def test_hash_differs_from_password_and_between_calls():
    h1, h2 = hash_password("secret-pw"), hash_password("secret-pw")
    assert h1 != "secret-pw" and "secret-pw" not in h1
    assert h1 != h2
    assert h1.startswith("$argon2id$")


def test_verify_true_and_false():
    h = hash_password("secret-pw")
    assert verify_password("secret-pw", h) is True
    assert verify_password("other", h) is False


def test_verify_malformed_or_empty_hash_is_false():
    for bad in ("", "not-a-hash", "$argon2id$garbage", "x" * 200):
        assert verify_password("secret-pw", bad) is False
