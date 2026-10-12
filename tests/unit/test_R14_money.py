from ticketing.payments import Charge, ChargeState


def test_R14_money_is_integer_minor_units() -> None:
    charge = Charge("ch", __import__("uuid").uuid4(), 1099, ChargeState.SUCCEEDED)
    assert isinstance(charge.amount_minor, int)
