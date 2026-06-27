#!/usr/bin/env python3
"""Re-apply speech policy to data/clover_voice_labels.json (keeps Clover IDs)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from restaurant.clover.seed_menu import menu_item_by_key
from restaurant.clover.voice_labels import apply_speech_to_label_entry

DEFAULT_PATH = Path("data/clover_voice_labels.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.path.is_file():
        print(f"Missing {args.path}", file=sys.stderr)
        return 1

    data = json.loads(args.path.read_text(encoding="utf-8"))
    by_key = menu_item_by_key()
    updated = 0

    for entry in data.get("items", []):
        before = (entry.get("voice_line"), entry.get("speech_mode"))
        apply_speech_to_label_entry(entry, by_key.get(entry.get("key", "")))
        after = (entry.get("voice_line"), entry.get("speech_mode"))
        if before != after:
            updated += 1

    data["speech_policy_version"] = 1
    print(f"Processed {len(data.get('items', []))} items; updated {updated} voice_line entries.")

    if args.dry_run:
        print("(dry-run — file not written)")
        return 0

    args.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
