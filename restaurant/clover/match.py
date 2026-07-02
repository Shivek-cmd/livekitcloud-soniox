"""Cross-script menu matching with confidence scores and abstain.

Why this exists (PR 032): Soniox output has legitimate spelling variance —
matra differences (ਪਕੌੜਾ vs ਪਕੋੜਾ), loanword transliterations (ਮਿਕਸ vs ਮਿਸ਼ਰਿਤ),
and script choice (Gurmukhi vs Latin) vary call to call. Raw substring matching
against one canonical spelling either misses the real item or lets a courtesy
verb (ਕਰ ⊂ ਕਰੀ "curry") pick a random dish. This module matches in a folded
phonetic space, ignores function words, and returns None instead of guessing.

Pure in-process string ops — no dependencies, no I/O. The index is built once
per menu; per-query cost is dict lookups over ~61 items.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Normalization

_PUNCT_RE = re.compile(r"[।॥,.\-_/()!?:;'\"“”‘’&+*]")
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    t = _PUNCT_RE.sub(" ", (text or "").lower())
    return _WS_RE.sub(" ", t).strip()


# ---------------------------------------------------------------------------
# Transliteration (Gurmukhi + Devanagari → Latin approximation)

_GURMUKHI = {
    "ੳ": "u", "ਅ": "a", "ਆ": "aa", "ਇ": "i", "ਈ": "ii", "ਉ": "u", "ਊ": "uu",
    "ਏ": "e", "ਐ": "ai", "ਓ": "o", "ਔ": "au",
    "ਸ": "s", "ਹ": "h", "ਕ": "k", "ਖ": "kh", "ਗ": "g", "ਘ": "gh", "ਙ": "ng",
    "ਚ": "ch", "ਛ": "chh", "ਜ": "j", "ਝ": "jh", "ਞ": "ny",
    "ਟ": "t", "ਠ": "th", "ਡ": "d", "ਢ": "dh", "ਣ": "n",
    "ਤ": "t", "ਥ": "th", "ਦ": "d", "ਧ": "dh", "ਨ": "n",
    "ਪ": "p", "ਫ": "ph", "ਬ": "b", "ਭ": "bh", "ਮ": "m",
    "ਯ": "y", "ਰ": "r", "ਲ": "l", "ਵ": "v", "ੜ": "r",
    "ਸ਼": "sh", "ਖ਼": "kh", "ਗ਼": "g", "ਜ਼": "z", "ਫ਼": "f", "ਲ਼": "l",
    "ਾ": "a", "ਿ": "i", "ੀ": "i", "ੁ": "u", "ੂ": "u",
    "ੇ": "e", "ੈ": "ai", "ੋ": "o", "ੌ": "au",
    "੍": "", "ੰ": "n", "ਂ": "n", "ੱ": "", "ਃ": "", "਼": "",
    "੦": "0", "੧": "1", "੨": "2", "੩": "3", "੪": "4",
    "੫": "5", "੬": "6", "੭": "7", "੮": "8", "੯": "9",
}

_DEVANAGARI = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "ny",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
    "क़": "k", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f",
    "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
    "्": "", "ं": "n", "ँ": "n", "ः": "", "़": "",
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
}

_TRANSLIT = {**_GURMUKHI, **_DEVANAGARI}


def transliterate(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        elif ch.isascii():
            out.append(ch)
        # other scripts/symbols dropped
    return "".join(out)


# ---------------------------------------------------------------------------
# Phonetic key — folds STT spelling variance to a comparable skeleton.
# ਪਕੌੜਾ / ਪਕੋੜਾ / pakora → "pkr" ; ਪਲੈਟਰ / ਪਲੇਟਰ / platter → "pltr"

_FOLDS = (
    ("chh", "c"), ("ch", "c"), ("sh", "s"), ("kh", "k"), ("gh", "g"),
    ("jh", "j"), ("th", "t"), ("dh", "d"), ("ph", "f"), ("bh", "b"),
)
_SINGLES = (("x", "ks"), ("q", "k"), ("w", "v"), ("z", "j"), ("c", "k"), ("y", "i"))
_VOWELS = set("aeiou")


def phonetic_key(token: str) -> str:
    t = re.sub(r"[^a-z]", "", transliterate(token.lower()))
    if not t:
        return ""
    for old, new in _FOLDS:
        t = t.replace(old, new)
    for old, new in _SINGLES:
        t = t.replace(old, new)
    kept: list[str] = []
    for i, ch in enumerate(t):
        if ch in _VOWELS and i > 0:
            continue
        if kept and kept[-1] == ch:
            continue
        kept.append(ch)
    return "".join(kept)


# ---------------------------------------------------------------------------
# Stopwords — courtesy/function words that must never pick a dish.
# Removed from BOTH queries and item labels, so removal is symmetric-safe.

STOPWORDS: frozenset[str] = frozenset(
    {
        # English
        "a", "an", "the", "and", "or", "of", "to", "for", "with", "in", "on",
        "please", "can", "could", "would", "you", "i", "we", "me", "my", "us",
        "want", "like", "get", "give", "take", "have", "add", "order", "make",
        "do", "did", "some", "also", "just", "yes", "no", "ok", "okay", "sure",
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "extra", "pcs", "piece", "pieces", "serves", "that", "this",
        "it", "is", "your",
        # Romanized Punjabi/Hindi courtesy
        "ji", "haan", "han", "kar", "karo", "karde", "dedo", "de", "dey",
        "dio", "deyo", "mainu", "sanu", "chahida", "chahidi", "hai", "hain",
        "ek", "ik", "aur", "te", "bhi", "kuch", "zara", "thoda", "vich",
        # Gurmukhi
        "ਹਾਂ", "ਜੀ", "ਨਹੀਂ", "ਆਪਣੇ", "ਆਪਾਂ", "ਅਸੀਂ", "ਮੈਂ", "ਮੈਨੂੰ", "ਸਾਨੂੰ",
        "ਮੇਰੇ", "ਸਾਡੇ", "ਇੱਕ", "ਇਕ", "ਐਕ", "ਦੋ", "ਤਿੰਨ", "ਚਾਰ", "ਪੰਜ",
        "ਕਰ", "ਕਰੋ", "ਕਰਦੇ", "ਕਰਨਾ", "ਦਿਓ", "ਦਿਉ", "ਦੇਦੋ", "ਦੇ", "ਦਾ", "ਦੀ",
        "ਨੂੰ", "ਨਾਲ", "ਲਈ", "ਤੇ", "ਅਤੇ", "ਵੀ", "ਹੈ", "ਹਨ", "ਸੀ", "ਹੋਰ",
        "ਚਾਹੀਦਾ", "ਚਾਹੀਦੀ", "ਚਾਹੀਦੇ", "ਲੈ", "ਲਓ", "ਲਾਓ", "ਪਾ", "ਪਾਓ",
        "ਭੇਜ", "ਭੇਜੋ", "ਆਰਡਰ", "ਮੰਗਵਾ", "ਕੁਝ", "ਜ਼ਰਾ", "ਥੋੜਾ", "ਵਿੱਚ",
        # Devanagari
        "हाँ", "जी", "नहीं", "एक", "दो", "तीन", "कर", "करो", "करें", "दे",
        "दो", "दीजिए", "दें", "मुझे", "हमें", "मेरा", "हमारा", "चाहिए",
        "है", "हैं", "का", "की", "के", "को", "से", "में", "और", "भी",
        "कुछ", "ज़रा", "थोड़ा", "ऑर्डर",
    }
)


def content_tokens(text: str) -> list[str]:
    """Normalized tokens with stopwords, digits, and 1-char noise removed."""
    out: list[str] = []
    for tok in normalize(text).split():
        if len(tok) <= 1 or tok.isdigit() or tok in STOPWORDS:
            continue
        out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Confidence matcher
#
# Confidence is the F-measure of label coverage (how much of the item's label
# the query matched) and query coverage (how much of the query's content the
# label consumed). Both directions matter: "ਛੋਲੇ" fully matches the Chole
# label but only half of the query "ਛੋਲੇ ਭਟੂਰੇ" — the Combo alias that
# consumes both words must win.

EXACT_WEIGHT = 1.0
PHONETIC_WEIGHT = 0.85
PREFIX_WEIGHT = 0.75
UNIQUE_SINGLE_CONF = 0.65
DEFAULT_MIN_CONF = 0.55
_MIN_PHONETIC_KEY = 3  # 2-char keys collide too easily (ਕਰੀ/ਖੀਰ → "kr")


@dataclass(frozen=True)
class Match:
    key: str  # caller-supplied item key (e.g. clover_item_id)
    confidence: float
    matched_tokens: int
    exact_tokens: int
    label: str


class MatchIndex:
    """Prebuilt token/phonetic index over menu item labels.

    entries: (item_key, tie_break_name, [label, label, ...])
    Labels are the item name, speak_as, voice_line, and each alias.
    """

    def __init__(self, entries: list[tuple[str, str, list[str]]]):
        # per item: list of labels, each a list of (norm_token, phonetic_key)
        self._items: list[tuple[str, str, list[tuple[str, list[tuple[str, str]]]]]] = []
        self._key_df: dict[str, set[str]] = {}
        for item_key, name, labels in entries:
            prepared: list[tuple[str, list[tuple[str, str]]]] = []
            seen_labels: set[str] = set()
            for label in labels:
                toks = content_tokens(label)
                if not toks:
                    continue
                sig = " ".join(toks)
                if sig in seen_labels:
                    continue
                seen_labels.add(sig)
                pairs = [(t, phonetic_key(t)) for t in toks]
                prepared.append((label, pairs))
                for _, pk in pairs:
                    if pk:
                        self._key_df.setdefault(pk, set()).add(item_key)
            if prepared:
                self._items.append((item_key, name, prepared))

    def _key_unique_to(self, pk: str, item_key: str) -> bool:
        owners = self._key_df.get(pk)
        return owners is not None and owners == {item_key}

    @staticmethod
    def _token_weight(norm_tok: str, pk: str, q_norm: set[str], q_keys: set[str]) -> tuple[float, bool]:
        """(weight, is_exact) for one label token against the query tokens."""
        if norm_tok in q_norm:
            return EXACT_WEIGHT, True
        if pk and len(pk) >= 2 and pk in q_keys:
            return PHONETIC_WEIGHT, False
        # prefix tolerance: ਮਿਕਸ→"mks" vs mixed→"mksd"
        if pk and len(pk) >= _MIN_PHONETIC_KEY:
            for qk in q_keys:
                if len(qk) < _MIN_PHONETIC_KEY or abs(len(qk) - len(pk)) > 2:
                    continue
                if qk.startswith(pk) or pk.startswith(qk):
                    return PREFIX_WEIGHT, False
        return 0.0, False

    def best(self, query: str, *, min_conf: float = DEFAULT_MIN_CONF) -> Match | None:
        q_toks = content_tokens(query)
        if not q_toks:
            return None
        q_norm = set(q_toks)
        q_keys = {phonetic_key(t) for t in q_toks}
        q_keys.discard("")
        n_query = len(q_toks)

        candidates: list[Match] = []
        for item_key, name, labels in self._items:
            best_for_item: Match | None = None
            for label, pairs in labels:
                matched = 0
                exact = 0
                weight = 0.0
                matched_pairs: list[tuple[str, str, bool]] = []
                for norm_tok, pk in pairs:
                    w, is_exact = self._token_weight(norm_tok, pk, q_norm, q_keys)
                    if w <= 0:
                        continue
                    matched += 1
                    exact += int(is_exact)
                    weight += w
                    matched_pairs.append((norm_tok, pk, is_exact))
                if not matched:
                    continue

                n = len(pairs)
                label_cov = weight / n
                query_cov = min(matched, n_query) / n_query
                f_score = 2 * label_cov * query_cov / (label_cov + query_cov)

                confidence = 0.0
                if n == 1:
                    norm_tok, pk, is_exact = matched_pairs[0]
                    # single-token labels need exact text or a distinctive key
                    if is_exact or len(pk) >= _MIN_PHONETIC_KEY:
                        confidence = f_score
                elif matched >= 2 and (matched / n) >= 0.6:
                    confidence = f_score
                elif matched == 1:
                    norm_tok, pk, _ = matched_pairs[0]
                    distinctive = len(pk) >= _MIN_PHONETIC_KEY or len(norm_tok) >= 4
                    if distinctive and pk and self._key_unique_to(pk, item_key):
                        confidence = UNIQUE_SINGLE_CONF
                if confidence <= 0:
                    continue
                m = Match(item_key, round(confidence, 4), matched, exact, label)
                if best_for_item is None or (
                    (m.confidence, m.matched_tokens, m.exact_tokens)
                    > (best_for_item.confidence, best_for_item.matched_tokens, best_for_item.exact_tokens)
                ):
                    best_for_item = m
            if best_for_item is not None:
                candidates.append(best_for_item)

        if not candidates:
            return None
        # deterministic: confidence, matched tokens, exact tokens, shorter label, name
        name_by_key = {k: n for k, n, _ in self._items}
        candidates.sort(
            key=lambda m: (
                -m.confidence,
                -m.matched_tokens,
                -m.exact_tokens,
                len(m.label),
                name_by_key.get(m.key, ""),
            )
        )
        top = candidates[0]
        return top if top.confidence >= min_conf else None
