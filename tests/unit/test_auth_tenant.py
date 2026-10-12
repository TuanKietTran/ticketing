from ticketing.auth import constant_time_equal, hash_api_key


def test_auth_tenant_secret_comparison() -> None:
    digest = hash_api_key("organizer-key")
    assert constant_time_equal(digest, digest)
    assert not constant_time_equal(digest, hash_api_key("other-key"))
