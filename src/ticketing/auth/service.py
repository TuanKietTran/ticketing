import hashlib
import hmac
from secrets import token_urlsafe


def hash_secret(secret: str, salt: str = "ticketing") -> str:
    return hashlib.sha256(f"{salt}:{secret}".encode()).hexdigest()


def verify_secret(secret: str, expected_hash: str, salt: str = "ticketing") -> bool:
    return hmac.compare_digest(hash_secret(secret, salt), expected_hash)


def issue_session() -> str:
    return token_urlsafe(32)
