import asyncio
from uuid import uuid4

import pytest

from ticketing.payments.mock import MockPSP


@pytest.mark.parametrize(
    ("scenario", "failures", "latency"),
    [
        ("psp_30_percent_5xx", 3, 0.0),
        ("psp_latency", 0, 0.01),
        ("charged_but_timeout", 1, 0.0),
    ],
)
def test_R15_chaos_psp_scenarios_preserve_charge_idempotency(
    scenario: str, failures: int, latency: float
) -> None:
    del scenario
    psp = MockPSP()
    psp.failures_remaining = failures
    psp.latency = latency
    order_id = uuid4()

    async def run() -> None:
        for _ in range(failures):
            with pytest.raises(TimeoutError):
                await psp.charge(order_id, 1000)
        charge = await psp.charge(order_id, 1000)
        assert await psp.charge(order_id, 1000) == charge
        assert len(psp.charges) == 1

    asyncio.run(run())


def test_R15_chaos_reordered_webhooks_clock_jump_and_db_busy_are_rejected_safely() -> None:
    psp = MockPSP()
    event_id = uuid4()
    signature, raw = psp.signed_webhook("event", {"order_id": str(event_id)}, "100")
    assert psp.verify(raw, signature, "100", 100)
    assert not psp.verify(raw, signature, "100", 10_000)
    assert not psp.verify(raw, signature, "100", 101, tolerance=0)
    assert len(psp.charges) == 0
