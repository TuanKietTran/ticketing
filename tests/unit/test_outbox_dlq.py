from datetime import UTC, datetime, timedelta

from ticketing.deadletter import DeadLetterQueue
from ticketing.outbox import Outbox


def test_poison_message_dead_letters_and_replay_is_once() -> None:
    dlq = DeadLetterQueue()
    outbox = Outbox(dlq, max_attempts=2)
    outbox.append("email", {"order_id": "1"})
    calls = 0

    def poison(topic, payload):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise RuntimeError("poison")

    now = datetime.now(UTC)
    outbox.dispatch(poison, now)
    outbox.dispatch(poison, now + timedelta(seconds=5))
    assert outbox.pending == 0
    assert dlq.depth == 1
    item = dlq.list()[0]
    dlq.replay(item.id, lambda payload: None)
    dlq.replay(item.id, lambda payload: (_ for _ in ()).throw(RuntimeError("must not run")))
    assert item.status == "replayed"
    assert calls == 2
