"""
Seed Bizbull sandbox Clover inventory from restaurant/clover/seed_menu.py.

Creates categories, modifier groups, items, associations, and writes
data/clover_voice_labels.json for Phase 8b voice cache.

Usage:
    python scripts/clover_sandbox_seed.py --dry-run
    python scripts/clover_sandbox_seed.py --confirm
    python scripts/clover_sandbox_seed.py --confirm --force   # if items already exist
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from restaurant.clover.client import CloverClient
from restaurant.clover.seed_menu import (
    CATEGORIES,
    MENU_ITEMS,
    MODIFIER_GROUPS,
    RESTAURANT_LABEL,
    modifier_group_by_key,
)
from restaurant.clover.voice_labels import build_all_voice_label_items

VOICE_LABELS_PATH = Path("data/clover_voice_labels.json")


def _safe_print(text: str) -> None:
    sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


def _batch_post(client: CloverClient, resource: str, elements: list[dict]) -> None:
    if not elements:
        return
    client.post(client.merchant_path(f"/{resource}"), {"elements": elements})


def seed_modifier_groups(client: CloverClient | None, *, dry_run: bool) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    group_ids: dict[str, str] = {}
    mod_ids: dict[str, dict[str, str]] = {}

    for spec in MODIFIER_GROUPS:
        if dry_run:
            gid = f"dry-{spec.key}"
            group_ids[spec.key] = gid
            mod_ids[spec.key] = {m.key: f"dry-{spec.key}-{m.key}" for m in spec.modifiers}
            _safe_print(f"  [dry-run] modifier group {spec.name} ({len(spec.modifiers)} options)")
            continue

        created = client.post(
            client.merchant_path("/modifier_groups"),
            {
                "name": spec.name,
                "minRequired": spec.min_required,
                "maxAllowed": spec.max_allowed,
            },
        )
        gid = created["id"]
        group_ids[spec.key] = gid
        mod_ids[spec.key] = {}

        for mod in spec.modifiers:
            m = client.post(
                client.merchant_path(f"/modifier_groups/{gid}/modifiers"),
                {"name": mod.name, "price": dollars_to_cents(mod.price)},
            )
            mod_ids[spec.key][mod.key] = m["id"]

        _safe_print(f"  modifier group {spec.name}: {gid} ({len(spec.modifiers)} options)")

    return group_ids, mod_ids


def seed_categories(client: CloverClient | None, *, dry_run: bool) -> dict[str, str]:
    cat_ids: dict[str, str] = {}
    for spec in CATEGORIES:
        if dry_run:
            cat_ids[spec.key] = f"dry-cat-{spec.key}"
            _safe_print(f"  [dry-run] category {spec.name}")
            continue
        created = client.post(
            client.merchant_path("/categories"),
            {"name": spec.name, "sortOrder": spec.sort_order},
        )
        cat_ids[spec.key] = created["id"]
        _safe_print(f"  category {spec.name}: {created['id']}")
    return cat_ids


def seed_items(
    client: CloverClient | None,
    *,
    dry_run: bool,
    group_ids: dict[str, str],
) -> dict[str, str]:
    item_ids: dict[str, str] = {}
    group_lookup = modifier_group_by_key()

    for spec in MENU_ITEMS:
        body = {
            "name": spec.name,
            "price": dollars_to_cents(spec.price),
            "available": True,
            "hidden": False,
        }
        if spec.description:
            body["alternateName"] = spec.description[:255]

        if dry_run:
            iid = f"dry-item-{spec.key}"
            item_ids[spec.key] = iid
            _safe_print(f"  [dry-run] item {spec.name} ${spec.price:.2f}")
            continue

        created = client.post(client.merchant_path("/items"), body)
        iid = created["id"]
        item_ids[spec.key] = iid
        _safe_print(f"  item {spec.name}: {iid}")

        links: list[dict] = []
        for gkey in spec.modifier_group_keys:
            if gkey not in group_ids:
                raise SystemExit(f"Item {spec.key} references unknown modifier group {gkey}")
            links.append({"item": {"id": iid}, "modifierGroup": {"id": group_ids[gkey]}})
        _batch_post(client, "item_modifier_groups", links)

    return item_ids


def link_category_items(
    client: CloverClient | None,
    *,
    dry_run: bool,
    cat_ids: dict[str, str],
    item_ids: dict[str, str],
) -> None:
    elements: list[dict] = []
    for spec in MENU_ITEMS:
        elements.append(
            {
                "category": {"id": cat_ids[spec.category_key]},
                "item": {"id": item_ids[spec.key]},
            }
        )

    if dry_run:
        _safe_print(f"  [dry-run] would link {len(elements)} category↔item associations")
        return

    batch_size = 50
    for i in range(0, len(elements), batch_size):
        _batch_post(client, "category_items", elements[i : i + batch_size])
    _safe_print(f"  linked {len(elements)} category↔item associations")


def write_voice_labels(
    *,
    dry_run: bool,
    item_ids: dict[str, str],
    group_ids: dict[str, str],
    mod_ids: dict[str, dict[str, str]],
) -> None:
    items_out = build_all_voice_label_items(item_ids, group_ids, mod_ids)

    payload = {
        "restaurant": RESTAURANT_LABEL,
        "source": "restaurant/clover/seed_menu.py",
        "item_count": len(items_out),
        "items": items_out,
    }

    if dry_run:
        _safe_print(f"  [dry-run] would write {VOICE_LABELS_PATH} ({len(items_out)} items)")
        return

    VOICE_LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    VOICE_LABELS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _safe_print(f"  wrote {VOICE_LABELS_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Clover sandbox with Bizbull menu")
    parser.add_argument("--dry-run", action="store_true", help="Print plan only")
    parser.add_argument("--confirm", action="store_true", help="Required to write to Clover")
    parser.add_argument("--force", action="store_true", help="Seed even if items already exist")
    args = parser.parse_args()

    if not args.dry_run and not args.confirm:
        raise SystemExit("Pass --dry-run or --confirm")

    dry_run = args.dry_run
    client: CloverClient | None = None if dry_run else CloverClient.from_env()

    if not dry_run:
        assert client is not None
        existing = client.fetch_all("items")
        if existing and not args.force:
            raise SystemExit(
                f"Sandbox already has {len(existing)} items. "
                "Run clover_sandbox_cleanup.py --confirm first, or pass --force."
            )

    _safe_print(f"=== Clover seed: {RESTAURANT_LABEL} ===")
    _safe_print(f"Categories: {len(CATEGORIES)} | Modifier groups: {len(MODIFIER_GROUPS)} | Items: {len(MENU_ITEMS)}")

    _safe_print("\n--- Modifier groups ---")
    group_ids, mod_ids = seed_modifier_groups(client, dry_run=dry_run)

    _safe_print("\n--- Categories ---")
    cat_ids = seed_categories(client, dry_run=dry_run)

    _safe_print("\n--- Items ---")
    item_ids = seed_items(client, dry_run=dry_run, group_ids=group_ids)

    _safe_print("\n--- Category links ---")
    link_category_items(client, dry_run=dry_run, cat_ids=cat_ids, item_ids=item_ids)

    _safe_print("\n--- Voice labels ---")
    write_voice_labels(dry_run=dry_run, item_ids=item_ids, group_ids=group_ids, mod_ids=mod_ids)

    _safe_print("\nDone. Run: python scripts/clover_sandbox_probe.py --checkout --create-order")


if __name__ == "__main__":
    main()
