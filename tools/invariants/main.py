import argparse
import json


def check(snapshot: dict[str, int]) -> None:
    if snapshot["sold"] + snapshot["held"] > snapshot["capacity"]:
        raise SystemExit("oversell invariant violated")
    if snapshot.get("duplicate_charges", 0):
        raise SystemExit("duplicate charge invariant violated")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", help="JSON invariant snapshot")
    args = parser.parse_args()
    with open(args.snapshot, encoding="utf-8") as stream:
        snapshot = json.load(stream)
    check(snapshot)
    print("invariants: ok")


if __name__ == "__main__":
    main()
