from ticketing.waitingroom import WaitingRoom


def test_R7_waiting_room_is_bounded_by_admission_count() -> None:
    room = WaitingRoom()
    from uuid import uuid4
    for _ in range(10):
        room.enqueue(uuid4())
    assert len(room.admit(3)) == 3
