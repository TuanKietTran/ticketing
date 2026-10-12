from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ticketing.auth import hash_secret, verify_secret
from ticketing.waitingroom import WaitingRoom


def test_secret_comparison_and_fair_admission() -> None:
    digest = hash_secret("key")
    assert verify_secret("key", digest)
    assert not verify_secret("wrong", digest)
    room = WaitingRoom()
    first, second = uuid4(), uuid4()
    assert room.enqueue(first) == 1
    assert room.enqueue(second) == 2
    admitted = room.admit(1)
    assert admitted[0].buyer_id == first
    assert room.valid(admitted[0].token)
    assert not room.valid(admitted[0].token, datetime.now(UTC) + timedelta(seconds=61))
