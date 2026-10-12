from uuid import uuid4

from fastapi.testclient import TestClient

from ticketing.app import create_app


def test_hold_checkout_pay_flow_is_retry_safe() -> None:
    client = TestClient(create_app())
    event_id, buyer_id = uuid4(), uuid4()
    seed = client.post(f"/admin/events/{event_id}/inventory", json={"capacity": 1})
    assert seed.status_code == 200
    response = client.post(
        f"/events/{event_id}/holds",
        headers={"Idempotency-Key": "hold-1"},
        json={"buyer_id": str(buyer_id), "quantity": 1},
    )
    assert response.status_code == 201
    assert client.post(
        f"/events/{event_id}/holds",
        headers={"Idempotency-Key": "hold-1"},
        json={"buyer_id": str(buyer_id), "quantity": 1},
    ).json() == response.json()
    hold_id = response.json()["hold_id"]
    order_response = client.post(
        f"/holds/{hold_id}/checkout", headers={"Idempotency-Key": "checkout-1"}
    )
    assert order_response.status_code == 201
    order_id = order_response.json()["order_id"]
    paid = client.post(f"/orders/{order_id}/pay", headers={"Idempotency-Key": "pay-1"})
    assert paid.json()["state"] == "paid"
