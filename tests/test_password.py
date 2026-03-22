from utils.password import hash_password, verify_password


def test_hash_returns_string():
    assert isinstance(hash_password("secret"), str)


def test_hash_is_not_plaintext():
    assert hash_password("secret") != "secret"


def test_hash_is_bcrypt_format():
    assert hash_password("secret").startswith("$2")


def test_different_passwords_produce_different_hashes():
    assert hash_password("abc") != hash_password("xyz")


def test_same_password_produces_different_hashes_due_to_salt():
    assert hash_password("secret") != hash_password("secret")


def test_verify_correct_password_returns_true():
    hashed = hash_password("correct")
    assert verify_password("correct", hashed) is True


def test_verify_wrong_password_returns_false():
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_verify_empty_password_against_nonempty_hash_returns_false():
    hashed = hash_password("notempty")
    assert verify_password("", hashed) is False


def test_verify_is_consistent_across_calls():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True
    assert verify_password("mypassword", hashed) is True
