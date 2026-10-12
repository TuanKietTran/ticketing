import argparse
import asyncio
from uuid import UUID

from ticketing.db import make_engine, make_session_factory
from ticketing.deadletter import discard_dead_letter, list_dead_letters, replay_dead_letter


async def run(command: str, item_id: str | None, reason: str) -> None:
    engine = make_engine()
    sessions = make_session_factory(engine)
    async with sessions() as session:
        async with session.begin():
            if command == "list":
                print(await list_dead_letters(session))
            elif command == "replay":
                print(await replay_dead_letter(session, UUID(item_id)))
            else:
                print(await discard_dead_letter(session, UUID(item_id), reason))
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["list", "replay", "discard"])
    parser.add_argument("item_id", nargs="?")
    parser.add_argument("--reason", default="operator discard")
    args = parser.parse_args()
    asyncio.run(run(args.command, args.item_id, args.reason))


if __name__ == "__main__":
    main()
