"""Run all evals and print a pass/fail table (also pasted into the Devpost write-up)."""

from __future__ import annotations

from evals import leak_check


def main() -> int:
    return leak_check.run()


if __name__ == "__main__":
    raise SystemExit(main())
