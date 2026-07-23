"""Clover Hosted Checkout webhook verification + payload parse (P3)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any

logger = logging.getLogger("clover-hco-webhook")


def hco_webhook_secret() -> str | None:
    secret = (os.getenv("CLOVER_HCO_WEBHOOK_SECRET") or "").strip()
    return secret or None


def verify_clover_signature(
    *,
    raw_body: bytes,
    signature_header: str | None,
    secret: str | None = None,
) -> bool:
    """Validate Clover-Signature: t=<unix>,v1=<hmac_sha256_hex>.

    Signed payload = ``{t}.{raw_body}`` per Clover HCO webhook docs.
    If no secret is configured, verification is skipped (dev only) and returns True
    only when ``CLOVER_HCO_WEBHOOK_SECRET`` is empty AND
    ``CLOVER_HCO_WEBHOOK_ALLOW_UNSIGNED=1``.
    """
    sec = (secret if secret is not None else hco_webhook_secret()) or ""
    if not sec:
        allow = (os.getenv("CLOVER_HCO_WEBHOOK_ALLOW_UNSIGNED") or "").strip().lower()
        if allow in ("1", "true", "yes", "on"):
            logger.warning("HCO webhook accepted without signature (unsigned allowed)")
            return True
        logger.warning("HCO webhook rejected — no CLOVER_HCO_WEBHOOK_SECRET configured")
        return False

    header = (signature_header or "").strip()
    if not header:
        return False

    parts: dict[str, str] = {}
    for chunk in header.split(","):
        chunk = chunk.strip()
        if "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        parts[k.strip()] = v.strip()

    ts = parts.get("t")
    v1 = parts.get("v1")
    if not ts or not v1:
        return False

    try:
        body_text = raw_body.decode("utf-8")
    except UnicodeDecodeError:
        body_text = raw_body.decode("utf-8", errors="replace")

    signed = f"{ts}.{body_text}".encode("utf-8")
    digest = hmac.new(sec.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, v1)


def parse_hco_webhook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize HCO webhook fields (Status / Id / Data / …).

    Expected (from Clover docs):
      Status: APPROVED | DECLINED
      Type: PAYMENT
      Id: payment UUID
      Data: checkout session UUID
      MerchantId, Message, Created Time
    """
    # Accept both Title-Case (docs) and snake/camel variants.
    def _get(*keys: str) -> Any:
        for k in keys:
            if k in payload and payload[k] is not None:
                return payload[k]
        lower = {str(k).lower(): v for k, v in payload.items()}
        for k in keys:
            if k.lower() in lower:
                return lower[k.lower()]
        return None

    status = str(_get("Status", "status") or "").strip().upper()
    payment_id = str(_get("Id", "id", "paymentId", "payment_id") or "").strip()
    checkout_session_id = str(
        _get("Data", "data", "checkoutSessionId", "checkout_session_id") or ""
    ).strip()
    merchant_id = str(_get("MerchantId", "merchantId", "merchant_id") or "").strip() or None
    message = _get("Message", "message")
    msg = str(message).strip() if message is not None else None
    type_ = str(_get("Type", "type") or "").strip().upper() or None

    return {
        "status": status,
        "payment_id": payment_id or None,
        "checkout_session_id": checkout_session_id or None,
        "merchant_id": merchant_id,
        "message": msg,
        "type": type_,
    }
