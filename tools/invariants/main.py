import argparse
import asyncio
import json
from uuid import UUID

from sqlalchemy import text

from ticketing.db import make_engine, make_session_factory


def check(snapshot: dict[str, int]) -> None:
    if snapshot["sold"] + snapshot["held"] > snapshot["capacity"]:
        raise SystemExit("oversell invariant violated")
    if snapshot.get("duplicate_charges", 0):
        raise SystemExit("duplicate charge invariant violated")


async def check_database(event_id: UUID) -> dict[str, int]:
    engine = make_engine()
    sessions = make_session_factory(engine)
    async with sessions() as session:
        section = (
            await session.execute(
                text("SELECT capacity,held,sold FROM sections WHERE event_id=:event"),
                {"event": event_id},
            )
        ).first()
        if section is None:
            raise SystemExit("event inventory not found")
        counts = (
            await session.execute(
                text(
                    "SELECT count(*) FILTER (WHERE state='ticketed'), "
                    "count(*) FILTER (WHERE state IN ('failed','expired','cancelled')), "
                    "count(*) FILTER (WHERE state='paid') FROM orders WHERE event_id=:event"
                ),
                {"event": event_id},
            )
        ).one()
        duplicate_result = await session.execute(
            text(
                "SELECT count(*) FROM (SELECT order_id FROM ticket_sets GROUP BY order_id "
                "HAVING count(*) > 1) duplicate_sets"
            )
        )
        duplicates = duplicate_result.scalar_one()
        charge_result = await session.execute(
            text(
                "SELECT count(*) FROM charges c JOIN orders o ON o.id=c.order_id "
                "WHERE o.event_id=:event AND c.state='succeeded'"
            ),
            {"event": event_id},
        )
        charges = charge_result.scalar_one()
        leaked_result = await session.execute(
            text(
                "SELECT count(*) FROM holds h JOIN events e ON e.id=h.event_id "
                "WHERE h.event_id=:event AND h.status='active' AND h.expires_at <= now()"
            ),
            {"event": event_id},
        )
        leaked = leaked_result.scalar_one()
    await engine.dispose()
    result = {
        "capacity": section.capacity,
        "held": section.held,
        "sold": section.sold,
        "ticketed": counts[0],
        "terminal_nonwinners": counts[1],
        "paid_not_ticketed": counts[2],
        "duplicate_ticket_sets": duplicates,
        "successful_charges": charges,
        "leaked_holds": leaked,
    }
    check(result)
    if result["ticketed"] > result["capacity"] or result["duplicate_ticket_sets"]:
        raise SystemExit(f"ticket invariant violated: {result}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", nargs="?", help="JSON invariant snapshot")
    parser.add_argument("--event-id", type=UUID)
    args = parser.parse_args()
    if args.event_id:
        result = asyncio.run(check_database(args.event_id))
    else:
        if not args.snapshot:
            raise SystemExit("provide snapshot or --event-id")
        with open(args.snapshot, encoding="utf-8") as stream:
            result = json.load(stream)
        check(result)
    print(json.dumps(result, default=str, sort_keys=True))


if __name__ == "__main__":
    main()
