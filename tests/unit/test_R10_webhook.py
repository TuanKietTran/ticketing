import asyncio

from ticketing.payments import MockPSP


def test_R10_signature_timestamp_replay_hardening() -> None:
    async def run() -> None:
        psp = MockPSP()
        signature, raw = psp.signed_webhook("e", {"ok": True}, "100")
        assert psp.verify(raw, signature, "100", 100)
        assert not psp.verify(raw, signature, "100", 1000)
    asyncio.run(run())
