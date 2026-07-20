"""Clover menu sync, local cache, and voice-friendly lookup."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from restaurant.clover.client import CloverClient
from restaurant.clover.match import DEFAULT_MIN_CONF, MatchIndex
from restaurant.clover.match import normalize as match_normalize
from restaurant.clover.models import CachedMenuItem, CachedModifier, CachedModifierGroup
from restaurant.clover.seed_menu import CATEGORIES
from restaurant.clover.speech_policy import resolve_speech_from_label
from restaurant.tenants.store import Tenant, mark_menu_synced

logger = logging.getLogger("menu-match")


def _legacy_match_enabled() -> bool:
    return os.getenv("MENU_MATCH_LEGACY", "").strip().lower() in ("1", "true", "yes")


def _min_match_conf() -> float:
    try:
        return float(os.getenv("MENU_MATCH_MIN_CONF", str(DEFAULT_MIN_CONF)))
    except ValueError:
        return DEFAULT_MIN_CONF

_CATEGORY_KEY_NAMES = {c.key: c.name for c in CATEGORIES}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _load_voice_labels(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["clover_item_id"]: item for item in data.get("items", [])}


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
        self._match_index: MatchIndex | None = None

    def _get_match_index(self) -> MatchIndex:
        if self._match_index is None:
            self._match_index = MatchIndex(
                [
                    (
                        i.clover_item_id,
                        i.name,
                        [i.name, i.speak_as, i.voice_line, *i.aliases],
                    )
                    for i in self._items
                ]
            )
        return self._match_index

    @property
    def item_count(self) -> int:
        return len(self._items)

    def all_items(self) -> list[CachedMenuItem]:
        """Public snapshot of every cached item (order preserved)."""
        return list(self._items)

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
    def load(cls, path: Path, *, voice_labels_path: Path | None = None) -> "MenuCache":
        data = json.loads(path.read_text(encoding="utf-8"))
        if voice_labels_path is None:
            sibling = path.parent / "clover_voice_labels.json"
            voice_labels_path = sibling if sibling.is_file() else None
        voice_by_id = (
            _load_voice_labels(voice_labels_path) if voice_labels_path and voice_labels_path.is_file() else {}
        )
        items = []
        for raw in data.get("items", []):
            iid = raw.get("clover_item_id", "")
            voice = voice_by_id.get(iid) or {}
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
            label_source = voice if voice else raw
            voice_line, speech_mode = resolve_speech_from_label(label_source)
            speak_as = voice.get("speak_as") or raw.get("speak_as") or raw.get("name", "")
            aliases = list(voice.get("aliases") or raw.get("aliases") or [])
            if voice.get("voice_line"):
                voice_line = voice["voice_line"]
            if voice.get("speech_mode"):
                speech_mode = voice["speech_mode"]
            items.append(
                CachedMenuItem(
                    clover_item_id=iid,
                    name=raw.get("name") or voice.get("clover_name") or "Unknown",
                    speak_as=speak_as,
                    voice_line=voice.get("voice_line") or raw.get("voice_line") or voice_line,
                    speech_mode=voice.get("speech_mode") or raw.get("speech_mode") or speech_mode,
                    price_cents=raw["price_cents"],
                    veg=raw.get("veg", True),
                    available=raw.get("available", True),
                    category_id=raw.get("category_id", ""),
                    category_name=raw.get("category_name", ""),
                    aliases=aliases,
                    modifier_groups=mod_groups,
                )
            )
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

    def find_item(self, query: str) -> CachedMenuItem | None:
        scored = self.find_item_scored(query)
        return scored[0] if scored else None

    def find_item_scored(self, query: str) -> tuple[CachedMenuItem, float] | None:
        """Best menu item for free-form caller text, with match confidence.

        Returns None (abstains) when nothing matches confidently — callers
        must treat that as "ask the customer", never as "pick something".
        """
        if _legacy_match_enabled():
            hit = self._find_item_legacy(query)
            return (hit, 1.0) if hit else None

        q = match_normalize(query)
        if not q:
            return None

        for item in self._items:
            if q in (
                match_normalize(item.name),
                match_normalize(item.speak_as),
                match_normalize(item.voice_line),
            ) or any(match_normalize(a) == q for a in item.aliases):
                return item, 1.0

        match = self._get_match_index().best(q, min_conf=_min_match_conf())
        if match is None:
            logger.info("MENU_MATCH abstain query=%r", query)
            return None
        item = self._by_id[match.key]
        logger.info(
            "MENU_MATCH query=%r -> %r conf=%.2f label=%r",
            query,
            item.name,
            match.confidence,
            match.label,
        )
        return item, match.confidence

    def _find_item_legacy(self, query: str) -> CachedMenuItem | None:
        """Pre-PR-032 matcher — kept behind MENU_MATCH_LEGACY=1 for rollback."""
        q = _norm(query)
        if not q:
            return None

        for item in self._items:
            if _norm(item.name) == q or _norm(item.speak_as) == q or _norm(item.voice_line) == q:
                return item

        for item in self._items:
            if q in _norm(item.name) or q in _norm(item.speak_as) or q in _norm(item.voice_line):
                return item
            for alias in item.aliases:
                if q in _norm(alias) or _norm(alias) in q:
                    return item

        tokens = q.split()
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
        return best if best_score > 0 else None

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

    def items_by_name_contains(self, needle: str, *, limit: int = 10) -> list[CachedMenuItem]:
        q = _norm(needle)
        if not q:
            return []
        out = [i for i in self._items if i.available and q in _norm(i.name)]
        return out[:limit]
