"""Clover menu sync, local cache, and voice-friendly lookup."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from restaurant.clover.client import CloverClient
from restaurant.clover.models import CachedMenuItem, CachedModifier, CachedModifierGroup
from restaurant.clover.seed_menu import CATEGORIES
from restaurant.clover.speech_policy import resolve_speech_from_label
from restaurant.tenants.store import Tenant, mark_menu_synced

_CATEGORY_KEY_NAMES = {c.key: c.name for c in CATEGORIES}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


# Single-token queries that must never fuzzy-match a menu item.
_BLOCKED_QUERY_TOKENS = frozenset({
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "a", "an", "of", "x",
    "ਇੱਕ", "ਐਕ", "ਦੋ", "ਤਿੰਨ",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
})


def _query_blocked(q: str) -> bool:
    if not q:
        return True
    if q in _BLOCKED_QUERY_TOKENS:
        return True
    if len(q) <= 2:
        return True
    return False


def _load_voice_labels(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["clover_item_id"]: item for item in data.get("items", [])}


def _overlay_voice_labels(items: list[CachedMenuItem], labels_path: Path) -> None:
    """Merge latest voice_labels aliases without a full Clover resync."""
    by_id = {i.clover_item_id: i for i in items}
    for entry in _load_voice_labels(labels_path).values():
        iid = entry.get("clover_item_id")
        if not iid:
            continue
        item = by_id.get(iid)
        if not item:
            continue
        extra = entry.get("aliases") or []
        if extra:
            item.aliases = list(dict.fromkeys(list(item.aliases) + extra))


def _voice_modifier_groups(voice_item: dict | None) -> list[CachedModifierGroup]:
    if not voice_item:
        return []
    groups: list[CachedModifierGroup] = []
    for g in voice_item.get("modifier_groups") or []:
        mods = [
            CachedModifier(
                clover_modifier_id=m["clover_modifier_id"],
                name=m["name"],
                price_cents=m.get("price_cents") or 0,
                speak_as=m.get("speak_as"),
                voice_line=m.get("voice_line") or m["name"],
                speech_mode=m.get("speech_mode") or "english",
                aliases=list(m.get("aliases") or []),
            )
            for m in g.get("modifiers") or []
        ]
        groups.append(
            CachedModifierGroup(
                clover_modifier_group_id=g["clover_modifier_group_id"],
                name=g["name"],
                min_required=g.get("min_required") or 0,
                max_allowed=g.get("max_allowed") or 1,
                modifiers=mods,
            )
        )
    return groups


class MenuCache:
    def __init__(self, items: list[CachedMenuItem], *, tenant_id: str, synced_at: str):
        self.tenant_id = tenant_id
        self.synced_at = synced_at
        self._items = items
        self._by_id = {i.clover_item_id: i for i in items}

    @property
    def item_count(self) -> int:
        return len(self._items)

    @classmethod
    def sync_from_clover(cls, tenant: Tenant) -> "MenuCache":
        client = CloverClient(
            base_url=tenant.clover_base_url,
            merchant_id=tenant.clover_merchant_id,
            token=tenant.clover_api_token,
        )

        categories = {c["id"]: c for c in client.fetch_all("categories")}
        item_category: dict[str, tuple[str, str]] = {}
        for cat in categories.values():
            try:
                for raw_item in client.fetch_all(f"categories/{cat['id']}/items"):
                    iid = raw_item.get("id")
                    if iid:
                        item_category[iid] = (cat["id"], cat.get("name") or "Other")
            except Exception:
                continue

        voice_by_id = _load_voice_labels(Path(tenant.voice_labels_path))
        cached: list[CachedMenuItem] = []

        for raw in client.fetch_all("items"):
            iid = raw["id"]
            voice = voice_by_id.get(iid)
            cat_id, cat_name = item_category.get(iid, ("", ""))
            if not cat_name and voice:
                cat_name = _CATEGORY_KEY_NAMES.get(voice.get("category_key", ""), "Other")
            elif not cat_name:
                cat_name = "Other"

            price_cents = raw.get("price") or (voice.get("price_cents") if voice else 0) or 0
            voice_line, speech_mode = resolve_speech_from_label(voice or {"name": raw.get("name", "")})
            cached.append(
                CachedMenuItem(
                    clover_item_id=iid,
                    name=raw.get("name") or (voice.get("clover_name") if voice else "Unknown"),
                    speak_as=(voice.get("speak_as") if voice else None) or raw.get("name", ""),
                    voice_line=voice_line,
                    speech_mode=speech_mode,
                    price_cents=price_cents,
                    veg=bool(voice.get("veg")) if voice else True,
                    available=bool(raw.get("available", True)) and not bool(raw.get("hidden", False)),
                    category_id=cat_id,
                    category_name=cat_name,
                    aliases=list(voice.get("aliases") or []) if voice else [],
                    modifier_groups=_voice_modifier_groups(voice),
                )
            )

        synced_at = datetime.now(timezone.utc).isoformat()
        cache = cls(cached, tenant_id=tenant.tenant_id, synced_at=synced_at)
        cache.save(tenant.cache_path())
        mark_menu_synced(tenant.tenant_id)
        return cache

    @classmethod
    def load(cls, path: Path) -> "MenuCache":
        data = json.loads(path.read_text(encoding="utf-8"))
        items = []
        for raw in data.get("items", []):
            mod_groups = []
            for g in raw.get("modifier_groups") or []:
                mods = [
                    CachedModifier(
                        clover_modifier_id=m["clover_modifier_id"],
                        name=m["name"],
                        price_cents=m.get("price_cents") or 0,
                        speak_as=m.get("speak_as"),
                        voice_line=m.get("voice_line") or m["name"],
                        speech_mode=m.get("speech_mode") or "english",
                        aliases=list(m.get("aliases") or []),
                    )
                    for m in g.get("modifiers") or []
                ]
                mod_groups.append(
                    CachedModifierGroup(
                        clover_modifier_group_id=g["clover_modifier_group_id"],
                        name=g["name"],
                        min_required=g.get("min_required") or 0,
                        max_allowed=g.get("max_allowed") or 1,
                        modifiers=mods,
                    )
                )
            voice_line, speech_mode = resolve_speech_from_label(raw)
            items.append(
                CachedMenuItem(
                    clover_item_id=raw["clover_item_id"],
                    name=raw["name"],
                    speak_as=raw["speak_as"],
                    voice_line=raw.get("voice_line") or voice_line,
                    speech_mode=raw.get("speech_mode") or speech_mode,
                    price_cents=raw["price_cents"],
                    veg=raw.get("veg", True),
                    available=raw.get("available", True),
                    category_id=raw.get("category_id", ""),
                    category_name=raw.get("category_name", ""),
                    aliases=list(raw.get("aliases") or []),
                    modifier_groups=mod_groups,
                )
            )
        _overlay_voice_labels(items, path.parent / "clover_voice_labels.json")
        return cls(
            items,
            tenant_id=data.get("tenant_id", ""),
            synced_at=data.get("synced_at", ""),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tenant_id": self.tenant_id,
            "synced_at": self.synced_at,
            "item_count": len(self._items),
            "items": [
                {
                    "clover_item_id": i.clover_item_id,
                    "name": i.name,
                    "speak_as": i.speak_as,
                    "voice_line": i.voice_line,
                    "speech_mode": i.speech_mode,
                    "price_cents": i.price_cents,
                    "veg": i.veg,
                    "available": i.available,
                    "category_id": i.category_id,
                    "category_name": i.category_name,
                    "aliases": i.aliases,
                    "modifier_groups": [
                        {
                            "clover_modifier_group_id": g.clover_modifier_group_id,
                            "name": g.name,
                            "min_required": g.min_required,
                            "max_allowed": g.max_allowed,
                            "modifiers": [
                                {
                                    "clover_modifier_id": m.clover_modifier_id,
                                    "name": m.name,
                                    "price_cents": m.price_cents,
                                    "speak_as": m.speak_as,
                                    "voice_line": m.voice_line,
                                    "speech_mode": m.speech_mode,
                                    "aliases": m.aliases,
                                }
                                for m in g.modifiers
                            ],
                        }
                        for g in i.modifier_groups
                    ],
                }
                for i in self._items
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def find_item_strict(self, query: str) -> CachedMenuItem | None:
        """Exact menu match only — safe for auto-add (no fuzzy token scoring)."""
        q = _norm(query)
        if _query_blocked(q):
            return None

        for item in self._items:
            if _norm(item.name) == q or _norm(item.speak_as) == q or _norm(item.voice_line) == q:
                return item

        for item in self._items:
            for alias in item.aliases:
                a = _norm(alias)
                if not a or _query_blocked(a):
                    continue
                if a == q or q == a:
                    return item
                if len(a) >= 4 and (a in q or q in a):
                    return item
        return None

    def find_item(self, query: str) -> CachedMenuItem | None:
        q = _norm(query)
        if _query_blocked(q):
            return None

        strict = self.find_item_strict(query)
        if strict:
            return strict

        for item in self._items:
            if q in _norm(item.name) or q in _norm(item.speak_as) or q in _norm(item.voice_line):
                return item
            for alias in item.aliases:
                a = _norm(alias)
                if len(q) >= 4 and (q in a or a in q):
                    return item

        tokens = [t for t in q.split() if t not in _BLOCKED_QUERY_TOKENS and len(t) > 2]
        if not tokens:
            return None
        best: CachedMenuItem | None = None
        best_score = 0
        for item in self._items:
            hay = (
                _norm(item.name)
                + " "
                + _norm(item.speak_as)
                + " "
                + _norm(item.voice_line)
                + " "
                + " ".join(item.aliases)
            )
            score = sum(1 for t in tokens if t in hay)
            if score > best_score:
                best_score = score
                best = item
        # Require majority of meaningful tokens to match (avoids single-token false positives).
        if best_score < max(2, len(tokens)):
            return None
        return best

    def search(self, query: str, *, limit: int = 8) -> list[CachedMenuItem]:
        q = _norm(query)
        if not q:
            return []

        scored: list[tuple[int, CachedMenuItem]] = []
        for item in self._items:
            hay = " ".join(
                [_norm(item.name), _norm(item.speak_as), _norm(item.voice_line), _norm(item.category_name)]
                + [_norm(a) for a in item.aliases]
            )
            if q in hay:
                scored.append((100, item))
                continue
            tokens = [t for t in q.split() if len(t) > 2]
            score = sum(2 for t in tokens if t in hay)
            if score:
                scored.append((score, item))

        scored.sort(key=lambda x: (-x[0], x[1].name))
        seen: set[str] = set()
        out: list[CachedMenuItem] = []
        for _, item in scored:
            if item.clover_item_id in seen:
                continue
            seen.add(item.clover_item_id)
            out.append(item)
            if len(out) >= limit:
                break
        return out

    def get_by_id(self, clover_item_id: str) -> CachedMenuItem | None:
        return self._by_id.get(clover_item_id)

    def catalog(self) -> dict:
        """Full menu grouped by category, JSON-serializable for the web menu panel."""
        groups: dict[str, list[dict]] = {}
        order: list[str] = []
        for it in self._items:
            cat = it.category_name or "Other"
            if cat not in groups:
                groups[cat] = []
                order.append(cat)
            groups[cat].append(
                {
                    "id": it.clover_item_id,
                    "name": it.name,
                    "voice_line": it.voice_line,
                    "price": round(it.price_dollars, 2),
                    "veg": it.veg,
                    "available": it.available,
                    "has_spice": any(g.name == "Spice Level" for g in it.modifier_groups),
                    "options": [g.name for g in it.modifier_groups],
                }
            )
        return {
            "tenant_id": self.tenant_id,
            "synced_at": self.synced_at,
            "item_count": len(self._items),
            "categories": [{"name": c, "items": groups[c]} for c in order],
        }

    def list_by_category(self, category_query: str, *, limit: int = 10) -> list[CachedMenuItem]:
        q = _norm(category_query)
        out = [
            i for i in self._items
            if q in _norm(i.category_name) or q in _norm(i.category_name).replace("&", "and")
        ]
        return out[:limit]
