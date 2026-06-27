"""Build and update Clover voice label entries (speech + STT aliases)."""

from __future__ import annotations

from restaurant.clover.seed_menu import MENU_ITEMS, MODIFIER_GROUPS, MenuItemSpec, dollars_to_cents
from restaurant.clover.seed_menu import modifier_group_by_key
from restaurant.clover.speech_policy import resolve_item_speech, resolve_modifier_speech


def build_item_voice_entry(
    spec: MenuItemSpec,
    *,
    clover_item_id: str,
    group_ids: dict[str, str],
    mod_ids: dict[str, dict[str, str]],
) -> dict:
    voice_line, speech_mode = resolve_item_speech(spec)
    mod_spec = modifier_group_by_key()

    entry: dict = {
        "key": spec.key,
        "clover_item_id": clover_item_id,
        "clover_name": spec.name,
        "speak_as": spec.speak_as,
        "voice_line": voice_line,
        "speech_mode": speech_mode,
        "aliases": list(spec.aliases),
        "veg": spec.veg,
        "category_key": spec.category_key,
        "price_cents": dollars_to_cents(spec.price),
    }

    if spec.modifier_group_keys:
        entry["modifier_groups"] = []
        for gkey in spec.modifier_group_keys:
            gspec = mod_spec[gkey]
            gentry = {
                "key": gkey,
                "clover_modifier_group_id": group_ids[gkey],
                "name": gspec.name,
                "min_required": gspec.min_required,
                "max_allowed": gspec.max_allowed,
                "modifiers": [],
            }
            for m in gspec.modifiers:
                m_voice, m_mode = resolve_modifier_speech(m.name)
                gentry["modifiers"].append(
                    {
                        "key": m.key,
                        "clover_modifier_id": mod_ids[gkey][m.key],
                        "name": m.name,
                        "price_cents": dollars_to_cents(m.price),
                        "speak_as": m.speak_as,
                        "voice_line": m_voice,
                        "speech_mode": m_mode,
                        "aliases": list(m.aliases),
                    }
                )
            entry["modifier_groups"].append(gentry)

    return entry


def apply_speech_to_label_entry(entry: dict, spec: MenuItemSpec | None = None) -> dict:
    """Merge voice_line/speech_mode into an existing label entry (keeps Clover IDs)."""
    if spec is None:
        from restaurant.clover.seed_menu import menu_item_by_key

        spec = menu_item_by_key().get(entry.get("key", ""))

    if spec:
        voice_line, speech_mode = resolve_item_speech(spec)
        entry["speak_as"] = spec.speak_as
        entry["voice_line"] = voice_line
        entry["speech_mode"] = speech_mode
    else:
        voice_line, speech_mode = resolve_item_speech(
            MenuItemSpec(
                key=entry.get("key", "unknown"),
                name=entry.get("clover_name", entry.get("name", "")),
                price=0,
                category_key=entry.get("category_key", ""),
                speak_as=entry.get("speak_as", ""),
                aliases=tuple(entry.get("aliases") or ()),
                veg=bool(entry.get("veg", True)),
            )
        )
        entry["voice_line"] = voice_line
        entry["speech_mode"] = speech_mode

    for group in entry.get("modifier_groups") or []:
        for mod in group.get("modifiers") or []:
            m_voice, m_mode = resolve_modifier_speech(mod.get("name", ""))
            mod["voice_line"] = m_voice
            mod["speech_mode"] = m_mode

    return entry


def build_all_voice_label_items(
    item_ids: dict[str, str],
    group_ids: dict[str, str],
    mod_ids: dict[str, dict[str, str]],
) -> list[dict]:
    return [
        build_item_voice_entry(spec, clover_item_id=item_ids[spec.key], group_ids=group_ids, mod_ids=mod_ids)
        for spec in MENU_ITEMS
    ]
